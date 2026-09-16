"""Build a per-user Windows EXE installer with private embedded Python."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "artifacts" / "standalone"
STAGE = WORK / "SoundShredder"
PYTHON_VERSION = "3.13.15"
PYTHON_SHA256 = "d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"
CSC = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")


def build():
    sys.path.insert(0, str(ROOT))
    from soundshredder import __version__
    if sys.platform != "win32" or not CSC.exists():
        raise SystemExit("Build on 64-bit Windows with the .NET Framework C# compiler.")
    WORK.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir(exist_ok=True)
    archive = WORK / f"python-{PYTHON_VERSION}-embed-amd64.zip"
    if not archive.exists():
        urllib.request.urlretrieve(f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{archive.name}", archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PYTHON_SHA256:
        raise RuntimeError("Embedded Python does not match the official SHA-256.")
    runtime = STAGE / "python"
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(runtime)
    for folder in ("soundshredder", "static", "desktop"):
        shutil.copytree(ROOT / folder, STAGE / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("README.md", "ROADMAP.md", "requirements.txt"):
        shutil.copy2(ROOT / name, STAGE / name)
    shutil.copy2(ROOT / "desktop" / "WINDOWS-README.md", STAGE / "README.md")
    wheels = STAGE / "desktop" / "wheels"
    wheels.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "pip==25.3", "--only-binary=:all:", "--no-deps", "-d", str(wheels)], check=True)
    bandit = next(line for line in (ROOT / "requirements.txt").read_text().splitlines() if line.startswith("bandit-infer"))
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), bandit], check=True)
    with zipfile.ZipFile(next(wheels.glob("pip-*.whl"))) as z:
        z.extractall(runtime / "Lib" / "site-packages")
    (runtime / "python313._pth").write_text("python313.zip\n.\nLib/site-packages\n..\n", encoding="utf-8")
    requirements = "\n".join(line for line in (ROOT / "requirements.txt").read_text().splitlines() if not line.startswith("bandit-infer")) + "\n"
    (STAGE / "desktop" / "requirements.txt").write_text(requirements, encoding="utf-8")
    compile_args = [str(CSC), "/nologo", "/target:winexe", "/platform:x64", "/win32icon:" + str(ROOT / "desktop" / "icon.ico"), "/reference:System.Windows.Forms.dll", "/reference:System.IO.Compression.dll", "/reference:System.IO.Compression.FileSystem.dll"]
    launcher = WORK / "Launcher.cs"
    launcher.write_text((ROOT / "desktop/Launcher.cs").read_text().replace("@VERSION@", __version__), encoding="utf-8")
    subprocess.run([*compile_args, "/out:" + str(STAGE / "SoundShredder.exe"), str(launcher)], check=True)
    payload = WORK / "payload.zip"
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(STAGE.rglob("*")):
            relative = path.relative_to(STAGE)
            allowed = relative.parts[0] in {"soundshredder", "static", "desktop", "python", "README.md", "ROADMAP.md", "requirements.txt", "SoundShredder.exe"}
            if path.is_file() and allowed and "__pycache__" not in relative.parts and path.suffix != ".pyc":
                z.write(path, path.relative_to(STAGE).as_posix())
    installer = WORK / f"SoundShredder-Setup-{__version__}-Windows.exe"
    subprocess.run([*compile_args, "/define:INSTALLER", "/resource:" + str(payload) + ",payload.zip", "/out:" + str(installer), str(launcher)], check=True)
    manifest = {"installer": installer.name, "bytes": installer.stat().st_size,
                "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
                "python": PYTHON_VERSION, "python_sha256": PYTHON_SHA256}
    (WORK / "build.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    build()
