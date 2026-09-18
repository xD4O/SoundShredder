"""Dependency-free local setup manager for Windows and macOS standalone apps."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer

ROOT = Path(__file__).resolve().parent.parent


class LocalServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer calls getfqdn here, which can stall offline/VPN Mac launches.
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


def default_home(system=None):
    if (system or sys.platform) == "darwin":
        return Path.home() / "Library" / "Application Support" / "SoundShredder"
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SoundShredder"


HOME = Path(os.environ.get("SOUNDSHREDDER_DESKTOP_HOME", str(default_home())))
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SetupCancelled(Exception):
    """An explicit request to stop setup, without removing saved sessions."""


def read_json(path, default=None):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def write_json(path, value):
    # Readers/antivirus can briefly hold Windows files open during a relaunch.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream)
    try:
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(.025 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def local_request(url, *, token=None, payload=None, timeout=3):
    """Local lifecycle requests must never use a proxy or follow redirects."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http" or parts.hostname != "127.0.0.1" or not parts.port or parts.username or parts.password:
        raise ValueError("Invalid local application address.")
    headers = {"X-Setup-Token": token} if token else {}
    data = json.dumps(payload).encode() if payload is not None else None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(urllib.request.Request(url, data=data, headers=headers), timeout=timeout) as response:
        body = response.read(65537)
    if len(body) > 65536:
        raise ValueError("Invalid local response.")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("Invalid local response.")
    return value


def existing_instance(home):
    home = home.resolve()
    saved = read_json(home / "desktop.json", {})
    try:
        parts = urllib.parse.urlsplit(saved.get("url", ""))
        if parts.path != "/" or parts.query or not parts.fragment or not isinstance(saved.get("pid"), int):
            return None
        base = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        state = local_request(base + "/api/state", token=parts.fragment, timeout=.8)
        # v1.1.0 also returns home/status; accept its authenticated setup endpoint.
        if not state.get("home") or Path(state["home"]).resolve() != home or state.get("status") not in {"idle", "installing", "starting", "cancelling", "ready", "error"}:
            return None
        return dict(base=base, token=parts.fragment, saved=saved, state=state)
    except (OSError, ValueError, TypeError):
        return None


def claim_instance(home, timeout=12):
    deadline = time.monotonic() + timeout
    while True:
        lock = acquire_lock(home)
        if lock is not None:
            return lock, None  # stale metadata alone never prevents a new launch
        existing = existing_instance(home)
        if existing:
            return None, existing
        if time.monotonic() >= deadline:
            raise RuntimeError("SoundShredder is still closing or its setup manager is not responding. Wait a moment and reopen it. If needed, close the previous SoundShredder process in Activity Monitor or Task Manager; your sessions are retained.")
        time.sleep(.2)


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
        self.guard = threading.RLock()
        self.actions = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.status = "idle"
        self.message = "Choose how you want to process your sound."
        self.progress = 0
        self.process = None
        self.command = None
        self.url = None
        self.stopping = False
        self.device = (read_json(self.home / "settings.json", {}) or {}).get("device", "cpu")
        if self.mac or self.device not in {"cpu", "cuda"}:
            self.device = "cpu"
        self.nvidia = not self.mac and bool(shutil.which("nvidia-smi"))
        self.log = self.home / "setup.log"
        self.cancel_event = threading.Event()
        self.finished = threading.Event()
        self.finished.set()
        self.worker = None
        self.setup_started = None
        self.last_activity = time.monotonic()
        self.activity = ""
        self.download = None
        self.download_started = None
        self.interrupted = self.home / "setup-interrupted.json"
        if self.interrupted.exists():
            self.message = "Previous setup did not finish. Select Set up to repair it. Your sessions are kept."
        self.refresh_storage()

    def refresh_storage(self):
        # State polling must not wait for a disk probe while holding its lock.
        try:
            free = shutil.disk_usage(self.home).free
        except OSError:
            free = None
        with self.guard:
            self.free_gib = round(free / 1024**3, 1) if free is not None else None
        return free

    def check_cancelled(self):
        if self.cancel_event.is_set() or self.stopping:
            raise SetupCancelled()

    def required_space(self, device):
        return 3 if self.mac else (14 if device == "cuda" else 4)

    def runtime_python(self, runtime):
        return runtime / ("bin/python3.11" if self.mac else "python.exe")

    def python_command(self, python):
        # Imports must not add __pycache__ files to a signed, installed app bundle.
        return [str(python), "-B", *(["-I"] if self.mac else [])]

    def environment(self, python=None):
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONNOUSERSITE": "1", "PIP_NO_CACHE_DIR": "1",
               "PYTHONDONTWRITEBYTECODE": "1"}
        if self.mac and python and not (env.get("SSL_CERT_FILE") or env.get("SSL_CERT_DIR")):
            cert = Path(python).parent.parent / "lib/python3.11/site-packages/pip/_vendor/certifi/cacert.pem"
            if cert.exists():
                env["SSL_CERT_FILE"] = str(cert)
        return env

    def state(self):
        with self.guard:
            if self.status == "ready" and self.process and self.process.poll() is not None:
                self.status, self.message, self.url = "error", "The app stopped. Retry to reopen it. See diagnostics for details.", None
            now = time.monotonic()
            return dict(name="SoundShredder Desktop", pid=os.getpid(), status="closing" if self.stopping else self.status, message=self.message, progress=self.progress,
                        url=self.url, device=self.device, nvidia=self.nvidia,
                        platform=self.system, machine=self.machine, home=str(self.home),
                        models_home=os.environ.get("SOUNDSHREDDER_MODEL_HOME"),
                        free_gib=self.free_gib, activity=self.activity, download=self.download,
                        elapsed_seconds=int(now - self.setup_started) if self.setup_started else 0,
                        quiet_seconds=int(now - self.last_activity),
                        can_cancel=self.status in {"installing", "starting"},
                        required_gib={device: self.required_space(device) for device in ("cpu", "cuda")})

    def update(self, status, message, progress):
        with self.guard:
            if self.cancel_event.is_set() and status in {"installing", "starting", "ready"}:
                raise SetupCancelled()
            self.status, self.message, self.progress = status, message, progress
            self.activity, self.last_activity = message, time.monotonic()
            self.download, self.download_started = None, None

    def start(self, device):
        if device not in {"cpu", "cuda"}:
            raise ValueError("Choose CPU or NVIDIA GPU.")
        if self.mac and device != "cpu":
            raise ValueError("This Mac build uses CPU. NVIDIA CUDA and Apple Metal are not supported.")
        with self.guard:
            if self.stopping:
                raise ValueError("SoundShredder is closing. Reopen the installed application.")
            if (self.status in {"installing", "starting", "cancelling", "ready"}
                    or (self.worker and self.worker.is_alive()) or (self.command and self.command.poll() is None)):
                raise ValueError("Setup or the app is already running.")
            self.cancel_event.clear()
            self.finished.clear()
            self.status, self.message, self.progress = "installing", "Preparing your private runtime…", 5
            self.device = device
            self.worker = threading.Thread(target=self.setup, daemon=True)
            self.worker.start()

    def cancel_setup(self):
        with self.guard:
            if self.status == "cancelling":
                return
            if self.status not in {"installing", "starting"}:
                raise ValueError("There is no setup to cancel.")
            self.cancel_event.set()
            self.status, self.message = "cancelling", "Stopping setup safely… Your sessions are kept."

    def record_output(self, output):
        with self.guard:
            self.last_activity = time.monotonic()
            for line in output.splitlines():
                match = re.fullmatch(r"Progress (\d+) of (\d+)", line.strip())
                if match:
                    received, total = map(int, match.groups())
                    if not self.download or received < self.download["received"] or received == 0:
                        self.download_started = self.last_activity
                    seconds = max(.25, self.last_activity - self.download_started)
                    self.download = dict(received=received, total=total, bytes_per_second=int(received / seconds))
                elif match := re.match(r"\s*(Downloading|Collecting|Using cached) ([\w.+-]+)", line):
                    package = match[2].split("-")[0][:60]
                    self.activity = ("Downloading " if match[1] == "Downloading" else "Preparing ") + package + "…"
                    self.download, self.download_started = None, None
                elif "Installing collected packages" in line:
                    self.activity = "Installing downloaded packages…"
                    self.download, self.download_started = None, None
                elif "Retrying" in line:
                    self.activity = "Connection interrupted. Retrying the download…"
                elif "Successfully installed" in line:
                    self.activity = "Packages installed."
                    self.download, self.download_started = None, None

    @staticmethod
    def stop_command(command):
        if command and command.poll() is None:
            try:
                command.terminate()
            except ProcessLookupError:
                pass  # A simultaneous close or natural exit already stopped it.
            try:
                command.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    command.kill()
                except ProcessLookupError:
                    pass
                command.wait(timeout=3)

    def run(self, args, *, timeout=3600, idle_timeout=600):
        self.check_cancelled()
        with self.log.open("ab") as log:
            log.write(("\n" + " ".join(map(str, args)) + "\n").encode("utf-8"))
            log.flush()
            offset = log.tell()
            with self.guard:
                self.check_cancelled()
                self.command = subprocess.Popen(args, cwd=self.root, stdout=log, stderr=subprocess.STDOUT,
                                                creationflags=FLAGS, env=self.environment(args[0]))
                command = self.command
                self.last_activity = time.monotonic()
            started = time.monotonic()
            try:
                with self.log.open("rb") as reader:
                    reader.seek(offset)
                    pending = ""
                    while True:
                        self.check_cancelled()
                        chunk = reader.read(65536)
                        if chunk:
                            pending += chunk.decode("utf-8", errors="replace").replace("\r", "\n")
                            lines, _, pending = pending.rpartition("\n")
                            self.record_output(lines)
                            pending = pending[-2048:]
                        if command.poll() is not None:
                            tail = reader.read(65536).decode("utf-8", errors="replace")
                            if pending or tail:
                                self.record_output(pending + tail)
                            break
                        now = time.monotonic()
                        if now - started >= timeout:
                            raise RuntimeError("This setup step took too long and was stopped. Check setup details, then retry.")
                        if now - self.last_activity >= idle_timeout:
                            raise RuntimeError("The installer stopped reporting activity and was stopped. Check your connection and free space, then retry.")
                        self.cancel_event.wait(.2)
            finally:
                try:
                    self.stop_command(command)
                finally:
                    with self.guard:
                        if command.poll() is not None:
                            self.command = None
        self.check_cancelled()
        if command.returncode:
            raise RuntimeError("Setup could not finish. Check your connection and free disk space, then retry. Details are in diagnostics.")

    def runtime_path(self, device):
        name = "py311-macos-" + self.machine + "-cpu" if self.mac else "py313-" + device
        return self.home / "runtimes" / name

    def repair_interrupted_runtime(self, runtime):
        if not any((runtime / name).exists() for name in (".copy-incomplete", ".setup-incomplete")):
            return
        expected = self.home.resolve() / "runtimes"
        if (runtime.parent.resolve() != expected or runtime.resolve().parent != expected
                or runtime.is_symlink() or getattr(runtime, "is_junction", lambda: False)()):
            raise RuntimeError("The engine folder is redirected. Choose a normal local profile folder before repairing setup.")
        self.update("installing", "Repairing an interrupted engine install…", 5)
        self.check_cancelled()
        # Only this marked, bounded engine cache is removed; sessions live in data.
        shutil.rmtree(runtime)
        self.check_cancelled()

    def copy_runtime_file(self, source, target):
        self.check_cancelled()
        result = shutil.copy2(source, target)
        self.check_cancelled()
        return result

    def prepare_runtime(self, device):
        runtime = self.runtime_path(device)
        if self.mac:
            if self.machine not in {"arm64", "x86_64"}:
                raise ValueError("Use the Apple Silicon or Intel Mac download for your processor.")
            bundle = read_json(self.root / "desktop" / "platform.json", {}) or {}
            if bundle.get("machine") != self.machine:
                raise ValueError("This app is for a different Mac processor. Download the matching Mac package.")
        self.repair_interrupted_runtime(runtime)
        if not self.runtime_python(runtime).exists():
            runtime.mkdir(parents=True, exist_ok=True)
            (runtime / ".copy-incomplete").touch()
            shutil.copytree(self.root / "python", runtime, dirs_exist_ok=True, symlinks=self.mac,
                            copy_function=self.copy_runtime_file)
            (runtime / ".copy-incomplete").unlink()
        if self.mac:
            site = runtime / "lib/python3.11/site-packages"
            site.mkdir(parents=True, exist_ok=True)
            # -I excludes user packages; this private .pth follows relocated app bundles.
            (site / "soundshredder-app.pth").write_text(str(self.root) + "\n", encoding="utf-8")
            return runtime
        # _pth isolates the embedded interpreter from system Python and global packages.
        (runtime / "python313._pth").write_text(
            "python313.zip\n.\nLib/site-packages\n" + str(self.root) + "\n", encoding="utf-8")
        return runtime

    def setup(self):
        self.finished.clear()
        self.setup_started = self.last_activity = time.monotonic()
        try:
            write_json(self.interrupted, {"device": self.device})
            self.check_cancelled()
            if self.mac and platform.mac_ver()[0] and int(platform.mac_ver()[0].split(".")[0]) < 12:
                raise RuntimeError("SoundShredder requires macOS 12 Monterey or newer.")
            free = self.refresh_storage()
            if free is None:
                raise RuntimeError("Could not check free space. Check the installation folder is available, then retry.")
            if free < 100 * 1024**2:
                raise RuntimeError("Free some disk space before opening SoundShredder.")
            requirements = self.root / "desktop" / "requirements.txt"
            requirements_bytes = requirements.read_bytes()
            bandit = next((self.root / "desktop" / "wheels").glob("bandit_infer-*.whl"), None)
            if bandit is None:
                raise RuntimeError("Bundled audio installer files are missing. Reinstall SoundShredder; your sessions are kept.")
            fingerprint = hashlib.sha256(requirements_bytes + bandit.read_bytes()).hexdigest()
            runtime = self.runtime_path(self.device)
            marker = runtime / "ready.json"
            ready = read_json(marker, {}) or {}
            install = (ready.get("requirements") != fingerprint or not self.runtime_python(runtime).exists()
                       or any((runtime / name).exists() for name in (".copy-incomplete", ".setup-incomplete")))
            if install and free < self.required_space(self.device) * 1024**3:
                raise RuntimeError(f"Keep at least {self.required_space(self.device)} GiB free for setup, plus space for models and sessions.")
            runtime = self.prepare_runtime(self.device)
            python = str(self.runtime_python(runtime))
            self.check_cancelled()
            dirty = runtime / ".setup-incomplete"
            if install:
                dirty.touch()
                marker.unlink(missing_ok=True)
                required = self.required_space(self.device)
                if shutil.disk_usage(self.home).free < required * 1024**3:
                    raise RuntimeError(f"Keep at least {required} GiB free for setup, plus space for models and sessions.")
                flavor = "cu128" if self.device == "cuda" else "cpu"
                torch_version = ("2.2.2" if self.machine == "x86_64" else "2.8.0") if self.mac else f"2.8.0+{flavor}"
                index = "https://pypi.org/simple" if self.mac else "https://download.pytorch.org/whl/" + flavor
                pip = [*self.python_command(python), "-m", "pip", "--isolated", "install", "--no-cache-dir",
                       "--disable-pip-version-check", "--only-binary=:all:", "--progress-bar", "raw",
                       "--timeout", "20", "--retries", "3"]
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
            except SetupCancelled:
                raise
            except Exception:
                marker.unlink(missing_ok=True)
                dirty.touch()
                raise
            self.check_cancelled()
            write_json(marker, {"requirements": fingerprint})
            dirty.unlink(missing_ok=True)
            write_json(self.home / "settings.json", {"device": self.device})
            self.update("starting", "Opening your SoundShredder workspace…", 95)
            self.launch(python)
            self.interrupted.unlink(missing_ok=True)
        except SetupCancelled:
            self.close_process(self.process, grace=3)
            self.process, self.url = None, None
            self.update("idle", "Setup canceled. Select Set up to resume or repair it. Your sessions are kept.", 0)
        except Exception as exc:
            # A failed readiness check must not leave a second workspace behind
            # when the user retries. No audio jobs are accepted during setup.
            self.close_process(self.process, grace=3)
            self.process, self.url = None, None
            with self.log.open("a", encoding="utf-8") as log:
                log.write(f"\n{type(exc).__name__}: {exc}\n")
            self.update("error", str(exc), 0)
        finally:
            self.refresh_storage()
            self.finished.set()

    def launch(self, python, *, timeout=120):
        port = free_port()
        url = f"http://127.0.0.1:{port}"
        with (self.home / "app.log").open("ab") as log:
            with self.guard:
                self.check_cancelled()
                self.process = subprocess.Popen([*self.python_command(python), str(self.root / "desktop/serve.py"), str(port)],
                    cwd=self.root, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, creationflags=FLAGS,
                    env={**self.environment(python), "SOUNDSHREDDER_DATA": str(self.home / "data")})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.check_cancelled()
            if self.process.poll() is not None:
                raise RuntimeError("The app could not start. Open diagnostics and retry.")
            try:
                if local_request(url + "/api/system", timeout=2).get("name") == "SoundShredder":
                    with self.guard:
                        self.url = url
                    self.update("ready", "Your sound workspace is ready.", 100)
                    return
            except (OSError, ValueError):
                self.cancel_event.wait(.5)
        self.close_process(self.process, grace=3)
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

    def stop_app(self, *, closing=False, cancel_setup=False):
        if self.status in {"installing", "starting", "cancelling"}:
            if not cancel_setup:
                raise ValueError("Wait for setup to finish or cancel setup before closing SoundShredder.")
            self.cancel_setup()
            if not self.finished.wait(10):
                raise ValueError("Setup is still stopping. Please wait a moment, then close again.")
        if self.process and self.process.poll() is None:
            if local_request(self.url + "/api/system", timeout=5).get("active_jobs"):
                raise ValueError("Finish or cancel audio processing in the workspace before closing.")
            if closing:
                self.stopping = True
            self.close_process(self.process)

    @staticmethod
    def close_process(process, *, grace=15):
        if process and process.poll() is None:
            # EOF requests graceful server shutdown, including audio-worker cleanup.
            if getattr(process, "stdin", None):
                process.stdin.close()
            else:
                process.terminate()
            try:
                process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    def cleanup(self):
        with self.guard:
            self.stopping = True
            self.cancel_event.set()
            command, process = self.command, self.process
        self.stop_command(command)
        self.close_process(process)
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=8)

    def reopen(self):
        state = self.state()
        if state["status"] == "error" and self.process is not None and self.process.poll() is not None:
            self.start(self.device)
        return self.state()

    def change_engine(self):
        self.stop_app()
        self.process, self.url = None, None
        self.update("idle", "Choose a different audio engine. Existing sessions are kept.", 0)

    def stop(self, *, cancel_setup=False):
        self.stop_app(closing=True, cancel_setup=cancel_setup)
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
                with manager.actions:
                    if self.path == "/api/start":
                        manager.start(payload.get("device"))
                    elif self.path == "/api/reopen":
                        return self.send(200, manager.reopen())
                    elif self.path == "/api/change-engine":
                        manager.change_engine()
                    elif self.path == "/api/cancel-setup":
                        manager.cancel_setup()
                    elif self.path == "/api/stop":
                        manager.stop(cancel_setup=payload.get("cancel_setup") is True)
                        # Flush the acknowledgement before shutdown can let the
                        # owning process exit and abandon this daemon handler.
                        try:
                            self.send(200, {"ok": True})
                            self.wfile.flush()
                        except ConnectionError:
                            pass  # The requester may already have closed its UI.
                        finally:
                            threading.Thread(target=self.server.shutdown, daemon=True).start()
                        return
                    else:
                        return self.send(404, {"error": "Not found."})
                self.send(200, {"ok": True})
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                self.send(400, {"error": str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--home", type=Path, default=HOME)
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--quit", action="store_true")
    parser.add_argument("--reopen-only", action="store_true")
    parser.add_argument("--hosted", action="store_true", help="Keep the native Mac host attached to the manager")
    parser.add_argument("--exclusive", action="store_true", help="Require ownership of this manager for a desktop shell")
    args = parser.parse_args()
    home = args.home.resolve()
    lock, existing = claim_instance(home)
    if existing:
        if args.exclusive:
            raise RuntimeError("Another SoundShredder standalone is running. Close it from its setup page or menu-bar Quit control, then retry. Your engine and sessions are kept.")
        if args.quit:
            local_request(existing["base"] + "/api/stop", token=existing["token"], payload={})
            return
        state = existing["state"]
        try:
            state = local_request(existing["base"] + "/api/reopen", token=existing["token"], payload={})
        except urllib.error.HTTPError as exc:
            if exc.code != 404:  # Compatibility with an already-running v1.1.0 manager.
                raise
        target = existing["saved"]["url"]
        if not args.setup and state.get("status") == "ready":
            candidate = state.get("url", "")
            try:
                if local_request(candidate + "/api/system").get("name") == "SoundShredder":
                    target = candidate
            except (OSError, ValueError):
                pass
        if not args.no_browser:
            webbrowser.open(target)
        if args.hosted:
            # A native host may attach to an existing manager; stay until it closes.
            while existing_instance(home):
                time.sleep(.5)
        return
    if args.quit or args.reopen_only:
        lock.close()
        return
    manager = Manager(home=home)
    server = LocalServer(("127.0.0.1", 0), handler_for(manager))
    url = f"http://127.0.0.1:{server.server_port}/#{manager.token}"
    try:
        write_json(home / "desktop.json", {"url": url, "pid": os.getpid()})
        if not args.no_browser:
            webbrowser.open(url)
        if (home / "settings.json").exists() and not manager.interrupted.exists():
            manager.start(manager.device)
        if args.hosted:
            def host_closed():
                # The Windows CRT cannot select stdin; use the same pipe observer
                # as the workspace so a crashed desktop shell cannot orphan it.
                sys.path.insert(0, str(ROOT))
                from desktop.lifetime import wait_for_owner
                wait_for_owner()
                manager.cleanup()
                server.shutdown()
            threading.Thread(target=host_closed, daemon=True).start()
        server.serve_forever()
    finally:
        manager.cleanup()
        server.server_close()
        saved = read_json(home / "desktop.json", {})
        if saved.get("pid") == os.getpid():
            (home / "desktop.json").unlink(missing_ok=True)
        lock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        HOME.mkdir(parents=True, exist_ok=True)
        (HOME / "launcher-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        if sys.platform == "win32" and "--no-browser" not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "SoundShredder could not open. See launcher-error.log in " + str(HOME), "SoundShredder", 0x10)
        elif sys.platform == "darwin" and not any(flag in sys.argv for flag in ("--quit", "--reopen-only", "--no-browser")):
            subprocess.run(["/usr/bin/osascript", "-e",
                            'display alert "SoundShredder could not open" message "See launcher-error.log in ~/Library/Application Support/SoundShredder for details." as critical'],
                           check=False)
        raise
