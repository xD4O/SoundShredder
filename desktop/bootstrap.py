"""Dependency-free local setup manager for Windows and macOS standalone apps."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def default_home(system=None):
    if (system or sys.platform) == "darwin":
        return Path.home() / "Library" / "Application Support" / "SoundShredder"
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SoundShredder"


HOME = Path(os.environ.get("SOUNDSHREDDER_DESKTOP_HOME", str(default_home())))
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(temporary, path)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def acquire_lock(home):
    home.mkdir(parents=True, exist_ok=True)
    handle = (home / "desktop.lock").open("a+b")
    # Windows locks prevent reads of the held byte, so inspect length, not contents.
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


class Manager:
    def __init__(self, home=HOME, root=ROOT, *, system=None, machine=None):
        self.home, self.root = Path(home), Path(root)
        self.system = system or sys.platform
        self.machine = machine or platform.machine()
        self.mac = self.system == "darwin"
        self.home.mkdir(parents=True, exist_ok=True)
        self.guard = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        self.status = "idle"
        self.message = "Choose how you want to process your sound."
        self.progress = 0
        self.process = None
        self.url = None
        self.stopping = False
        self.device = (read_json(self.home / "settings.json", {}) or {}).get("device", "cpu")
        if self.mac:
            self.device = "cpu"
        self.nvidia = not self.mac and bool(shutil.which("nvidia-smi"))
        self.log = self.home / "setup.log"

    def required_space(self, device):
        return 3 if self.mac else (14 if device == "cuda" else 4)

    def runtime_python(self, runtime):
        return runtime / ("bin/python3.11" if self.mac else "python.exe")

    def python_command(self, python):
        return [str(python), *(["-I"] if self.mac else [])]

    def environment(self, python=None):
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONNOUSERSITE": "1", "PIP_NO_CACHE_DIR": "1"}
        if self.mac and python:
            cert = Path(python).parent.parent / "lib/python3.11/site-packages/pip/_vendor/certifi/cacert.pem"
            if cert.exists():
                env["SSL_CERT_FILE"] = str(cert)
        return env

    def state(self):
        with self.guard:
            if self.status == "ready" and self.process and self.process.poll() is not None:
                self.status, self.message, self.url = "error", "The app stopped. Retry to reopen it. See diagnostics for details.", None
            return dict(status=self.status, message=self.message, progress=self.progress,
                        url=self.url, device=self.device, nvidia=self.nvidia,
                        platform=self.system, machine=self.machine, home=str(self.home),
                        free_gib=round(shutil.disk_usage(self.home).free / 1024**3, 1),
                        required_gib={device: self.required_space(device) for device in ("cpu", "cuda")})

    def update(self, status, message, progress):
        with self.guard:
            self.status, self.message, self.progress = status, message, progress

    def start(self, device):
        if device not in {"cpu", "cuda"}:
            raise ValueError("Choose CPU or NVIDIA GPU.")
        if self.mac and device != "cpu":
            raise ValueError("This Mac build uses CPU. NVIDIA CUDA and Apple Metal are not supported.")
        with self.guard:
            if self.status in {"installing", "starting", "ready"}:
                raise ValueError("Setup or the app is already running.")
            self.status, self.message, self.progress = "installing", "Preparing your private runtime…", 5
            self.device = device
        threading.Thread(target=self.setup, daemon=True).start()

    def run(self, args, *, timeout=3600):
        with self.log.open("ab") as log:
            log.write(("\n" + " ".join(map(str, args)) + "\n").encode("utf-8"))
            result = subprocess.run(args, cwd=self.root, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=FLAGS, timeout=timeout, env=self.environment(args[0]))
        if result.returncode:
            raise RuntimeError("Setup could not finish. Check your connection and free disk space, then retry. Details are in diagnostics.")

    def prepare_runtime(self, device):
        if self.mac:
            if self.machine not in {"arm64", "x86_64"}:
                raise ValueError("Use the Apple Silicon or Intel Mac download for your processor.")
            bundle = read_json(self.root / "desktop" / "platform.json", {}) or {}
            if bundle.get("machine") != self.machine:
                raise ValueError("This app is for a different Mac processor. Download the matching Mac package.")
            runtime = self.home / "runtimes" / ("py311-macos-" + self.machine + "-cpu")
            if not self.runtime_python(runtime).exists():
                shutil.copytree(self.root / "python", runtime, dirs_exist_ok=True, symlinks=True)
            site = runtime / "lib/python3.11/site-packages"
            site.mkdir(parents=True, exist_ok=True)
            # -I excludes user packages; this private .pth follows relocated app bundles.
            (site / "soundshredder-app.pth").write_text(str(self.root) + "\n", encoding="utf-8")
            return runtime
        runtime = self.home / "runtimes" / ("py313-" + device)
        if not (runtime / "python.exe").exists():
            shutil.copytree(self.root / "python", runtime, dirs_exist_ok=True)
        # _pth isolates the embedded interpreter from system Python and global packages.
        (runtime / "python313._pth").write_text(
            "python313.zip\n.\nLib/site-packages\n" + str(self.root) + "\n", encoding="utf-8")
        return runtime

    def setup(self):
        try:
            if self.mac and platform.mac_ver()[0] and int(platform.mac_ver()[0].split(".")[0]) < 12:
                raise RuntimeError("SoundShredder requires macOS 12 Monterey or newer.")
            if shutil.disk_usage(self.home).free < 100 * 1024**2:
                raise RuntimeError("Free some disk space before opening SoundShredder.")
            runtime = self.prepare_runtime(self.device)
            python = str(self.runtime_python(runtime))
            requirements = self.root / "desktop" / "requirements.txt"
            bandit = next((self.root / "desktop" / "wheels").glob("bandit_infer-*.whl"))
            fingerprint = hashlib.sha256(requirements.read_bytes() + bandit.read_bytes()).hexdigest()
            marker = runtime / "ready.json"
            ready = read_json(marker, {}) or {}
            if ready.get("requirements") != fingerprint:
                required = self.required_space(self.device)
                if shutil.disk_usage(self.home).free < required * 1024**3:
                    raise RuntimeError(f"Keep at least {required} GiB free for setup, plus space for models and sessions.")
                flavor = "cu128" if self.device == "cuda" else "cpu"
                torch_version = ("2.2.2" if self.machine == "x86_64" else "2.8.0") if self.mac else f"2.8.0+{flavor}"
                index = "https://pypi.org/simple" if self.mac else "https://download.pytorch.org/whl/" + flavor
                pip = [*self.python_command(python), "-m", "pip", "--isolated", "install", "--no-cache-dir",
                       "--disable-pip-version-check", "--only-binary=:all:"]
                self.update("installing", "Downloading the NVIDIA engine (about 3.2 GB)…" if self.device == "cuda" else "Downloading the CPU audio engine…", 20)
                self.run([*pip, f"torch=={torch_version}", "--index-url", index])
                self.update("installing", "Installing audio tools. No terminal or extra installers needed…", 55)
                self.run([*pip, "--index-url", "https://pypi.org/simple",
                          "-r", str(requirements), str(bandit),
                          f"torch=={torch_version}"])
            self.update("starting", "Checking your audio engine…", 85)
            try:
                self.run([*self.python_command(python), "-c", "import torch,numpy,bandit_infer,fastapi,uvicorn,soundfile,scipy,imageio_ffmpeg,multipart; "
                          "torch.from_numpy(numpy.zeros(1,dtype=numpy.float32)).numpy()"], timeout=120)
            except Exception:
                marker.unlink(missing_ok=True)
                raise
            write_json(marker, {"requirements": fingerprint})
            write_json(self.home / "settings.json", {"device": self.device})
            self.update("starting", "Opening your SoundShredder workspace…", 95)
            self.launch(python)
        except Exception as exc:
            with self.log.open("a", encoding="utf-8") as log:
                log.write(f"\n{type(exc).__name__}: {exc}\n")
            self.update("error", str(exc), 0)

    def launch(self, python):
        port = free_port()
        url = f"http://127.0.0.1:{port}"
        with (self.home / "app.log").open("ab") as log:
            self.process = subprocess.Popen([*self.python_command(python), "-m", "uvicorn", "soundshredder.server:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=self.root, stdout=log, stderr=subprocess.STDOUT, creationflags=FLAGS,
                env={**self.environment(python), "SOUNDSHREDDER_DATA": str(self.home / "data")})
        for _ in range(120):
            if self.process.poll() is not None:
                raise RuntimeError("The app could not start. Open diagnostics and retry.")
            try:
                with urllib.request.urlopen(url + "/api/system", timeout=2) as response:
                    if json.load(response).get("name") == "SoundShredder":
                        with self.guard:
                            self.url = url
                        self.update("ready", "Your sound workspace is ready.", 100)
                        return
            except (OSError, ValueError):
                time.sleep(.5)
        self.process.terminate()
        raise RuntimeError("The app took too long to start. See diagnostics and retry.")

    def diagnostics(self):
        parts = ["SoundShredder desktop setup", "Device: " + self.device, "Status: " + self.status]
        for name in ("setup.log", "app.log"):
            path = self.home / name
            if path.exists():
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 20000))
                    parts += ["\n" + name, stream.read().decode("utf-8", errors="replace")]
        return "\n".join(parts)

    def stop_app(self):
        if self.status in {"installing", "starting"}:
            raise ValueError("Wait for setup to finish before closing SoundShredder.")
        if self.process and self.process.poll() is None:
            with urllib.request.urlopen(self.url + "/api/system", timeout=5) as response:
                if json.load(response).get("active_jobs"):
                    raise ValueError("Finish or cancel audio processing in the workspace before closing.")
            self.process.terminate()
            self.process.wait(timeout=10)

    def change_engine(self):
        self.stop_app()
        self.process, self.url = None, None
        self.update("idle", "Choose a different audio engine. Existing sessions are kept.", 0)

    def stop(self):
        self.stop_app()
        self.stopping = True


def handler_for(manager):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send(self, status, content, content_type="application/json"):
            body = json.dumps(content).encode() if content_type == "application/json" else content
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def permitted(self, auth=False):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send(403, {"error": "Invalid host."})
                return False
            if auth and not secrets.compare_digest(self.headers.get("X-Setup-Token", "").encode(), manager.token.encode()):
                self.send(403, {"error": "Open setup from the SoundShredder shortcut."})
                return False
            if self.command == "POST" and self.headers.get("Origin") not in {None, f"http://127.0.0.1:{self.server.server_port}"}:
                self.send(403, {"error": "Invalid origin."})
                return False
            return True

        def do_GET(self):
            if not self.permitted(auth=self.path.startswith("/api/")):
                return
            if self.path == "/api/state":
                self.send(200, manager.state())
            elif self.path == "/api/diagnostics":
                self.send(200, {"text": manager.diagnostics()})
            else:
                assets = {"/": ("desktop/setup.html", "text/html; charset=utf-8"),
                          "/font.ttf": ("static/fonts/SpaceGrotesk-Variable.ttf", "font/ttf"),
                          "/higgsfield.svg": ("static/higgsfield-mark.svg", "image/svg+xml"),
                          "/icon.svg": ("static/icon.svg", "image/svg+xml")}
                if self.path not in assets:
                    return self.send(404, {"error": "Not found."})
                name, mime = assets[self.path]
                self.send(200, (manager.root / name).read_bytes(), mime)

        def do_POST(self):
            if not self.permitted(auth=True):
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 1024:
                    raise ValueError("Invalid request size.")
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("Expected an object.")
                if self.path == "/api/start":
                    manager.start(payload.get("device"))
                elif self.path == "/api/change-engine":
                    manager.change_engine()
                elif self.path == "/api/stop":
                    manager.stop()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                else:
                    return self.send(404, {"error": "Not found."})
                self.send(200, {"ok": True})
            except (ValueError, OSError) as exc:
                self.send(400, {"error": str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    lock = acquire_lock(HOME)
    if lock is None:
        for _ in range(30):
            existing = read_json(HOME / "desktop.json", {}) or {}
            if existing.get("url"):
                if not args.no_browser:
                    webbrowser.open(existing["url"])
                return
            time.sleep(.1)
        return
    manager = Manager()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(manager))
    url = f"http://127.0.0.1:{server.server_port}/#{manager.token}"
    write_json(HOME / "desktop.json", {"url": url, "pid": os.getpid()})
    if not args.no_browser:
        webbrowser.open(url)
    # Returning users only wait for the health check, not another download.
    if (HOME / "settings.json").exists():
        manager.start(manager.device)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        lock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        HOME.mkdir(parents=True, exist_ok=True)
        (HOME / "launcher-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "SoundShredder could not open. See launcher-error.log in " + str(HOME), "SoundShredder", 0x10)
        elif sys.platform == "darwin":
            subprocess.run(["/usr/bin/osascript", "-e",
                            'display alert "SoundShredder could not open" message "See launcher-error.log in ~/Library/Application Support/SoundShredder for details." as critical'],
                           check=False)
        raise
