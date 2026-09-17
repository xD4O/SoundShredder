"""Stage the shared UI, Python and pinned engine inputs for Electron packaging."""
from __future__ import annotations

import hashlib
import html
import json
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "artifacts/electron"


def main():
    sys.path.insert(0, str(ROOT))
    from scripts import build_mac_standalone as mac
    from scripts import build_windows_standalone as windows
    from soundshredder import __version__

    if sys.platform not in {"win32", "darwin"}:
        raise SystemExit("Build on Windows or macOS for the target platform.")
    stage = WORK / "backend"
    # Only replace this tool's explicitly bounded build staging folder.
    if stage.exists():
        if stage.is_symlink() or stage.resolve().parent != WORK.resolve():
            raise RuntimeError("Unexpected Electron staging path")
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for folder in ("soundshredder", "static"):
        shutil.copytree(ROOT / folder, stage / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    desktop = stage / "desktop"
    desktop.mkdir()
    for name in ("bootstrap.py", "serve.py", "lifetime.py", "setup.html", "icon-256.png"):
        shutil.copy2(ROOT / "desktop" / name, desktop / name)
    wheel_cache = WORK / "wheels"
    wheel_cache.mkdir(exist_ok=True)
    bandit = next(line for line in (ROOT / "requirements.txt").read_text().splitlines() if line.startswith("bandit-infer"))
    marker = wheel_cache / "source.txt"
    if not marker.exists() or marker.read_text() != bandit or not list(wheel_cache.glob("bandit_infer-*.whl")):
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-cache-dir", "--wheel-dir", str(wheel_cache), bandit], check=True)
        marker.write_text(bandit)
    wheels = desktop / "wheels"
    wheels.mkdir()
    shutil.copy2(next(wheel_cache.glob("bandit_infer-*.whl")), wheels)
    if sys.platform == "darwin":
        machine = platform.machine()
        if machine not in mac.RUNTIMES:
            raise RuntimeError("Unsupported Mac architecture")
        source, url, digest = mac.python_archive(machine)
        with tarfile.open(source) as archive:
            archive.extractall(stage, filter="data")
        (desktop / "platform.json").write_text(json.dumps({"machine": machine, "python_source": url, "python_sha256": digest}))
        requirements = mac.requirements_for(machine)
        guide = "MACOS.md"
        png = (desktop / "icon-256.png").read_bytes()
        (WORK / "SoundShredder.icns").write_bytes(b"icns" + struct.pack(">I", len(png) + 16) + b"ic08" + struct.pack(">I", len(png) + 8) + png)
    else:
        source = WORK / f"python-{windows.PYTHON_VERSION}-embed-amd64.zip"
        if not source.exists():
            urllib.request.urlretrieve(f"https://www.python.org/ftp/python/{windows.PYTHON_VERSION}/{source.name}", source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != windows.PYTHON_SHA256:
            raise RuntimeError("Python checksum mismatch")
        runtime = stage / "python"
        with zipfile.ZipFile(source) as archive:
            archive.extractall(runtime)
        subprocess.run([sys.executable, "-m", "pip", "download", "pip==25.3", "--only-binary=:all:", "--no-deps", "-d", str(wheel_cache)], check=True)
        with zipfile.ZipFile(next(wheel_cache.glob("pip-*.whl"))) as archive:
            archive.extractall(runtime / "Lib/site-packages")
        (runtime / "python313._pth").write_text("python313.zip\n.\nLib/site-packages\n..\n", encoding="utf-8")
        requirements = "\n".join(line for line in (ROOT / "requirements.txt").read_text().splitlines() if not line.startswith("bandit-infer")) + "\n"
        guide = "WINDOWS.md"
    (desktop / "requirements.txt").write_text(requirements, encoding="utf-8")
    shutil.copy2(ROOT / "electron/docs" / guide, stage / "INSTALLATION.md")
    text = (stage / "INSTALLATION.md").read_text(encoding="utf-8")
    # Offline documentation opens in the system browser without a Markdown editor.
    (stage / "INSTALLATION.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>SoundShredder installation guide</title><style>body{max-width:900px;margin:50px auto;padding:0 24px;'
        'background:#080c13;color:#e8f4f2;font:16px/1.7 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}</style>'
        '<pre>' + html.escape(text) + '</pre></html>', encoding="utf-8")
    package = json.loads((ROOT / "electron/package.json").read_text())
    assert package["version"] == __version__, "Electron and engine versions must match"
    print(json.dumps({"backend": str(stage), "version": __version__, "platform": sys.platform, "architecture": platform.machine(), "guide": guide}))


if __name__ == "__main__":
    main()
