"""Build native-architecture .app ZIPs without requiring a Mac build host.

Python binaries come from checksum-pinned Astral python-build-standalone releases.
This packages real Mac binaries; executing, signing and notarizing requires macOS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import posixpath
import struct
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "artifacts" / "mac-standalone"
PYTHON_VERSION = "3.11.16"
PYTHON_RELEASE = "20260901"
RUNTIMES = {
    "arm64": ("aarch64", "AppleSilicon", "768f05cf200273bbdda9a5955a5a6892a4b22f2a0b1e4b0a9160f5c7fce86816"),
    "x86_64": ("x86_64", "Intel", "908b381433f78b832c8d64960ced0f85871893cc8779f413f963e0c9e293c258"),
}
APP = "SoundShredder.app/Contents/"


def add_file(archive, name, data, mode=0o100644):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe archive destination")
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = mode << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)


def requirements_for(machine):
    lines = [line for line in (ROOT / "requirements.txt").read_text().splitlines()
             if not line.startswith("bandit-infer")]
    if machine == "x86_64":
        lines += ["torch==2.2.2", "numpy==1.26.4", "scipy==1.14.1"]
    else:
        lines += ["torch==2.8.0"]
    return "\n".join(lines) + "\n"


def python_archive(machine):
    arch, _, digest = RUNTIMES[machine]
    name = f"cpython-{PYTHON_VERSION}+{PYTHON_RELEASE}-{arch}-apple-darwin-install_only_stripped.tar.gz"
    dest = WORK / "downloads" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PYTHON_RELEASE}/{name}"
    if not dest.exists():
        part = dest.with_suffix(".part")
        urllib.request.urlretrieve(url, part)
        part.replace(dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
        raise RuntimeError(f"Python checksum mismatch: {dest}")
    return dest, url, digest


def add_python(archive, source):
    with tarfile.open(source) as tar:
        for member in tar.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != "python":
                raise ValueError("Unsafe Python archive path")
            target = APP + "Resources/" + member.name
            if member.issym():
                resolved = posixpath.normpath(posixpath.join(str(path.parent), member.linkname))
                if member.linkname.startswith("/") or not resolved.startswith("python/"):
                    raise ValueError("Unsafe Python archive link")
                add_file(archive, target, member.linkname.encode(), 0o120777)
            elif member.isfile():
                with tar.extractfile(member) as stream:
                    add_file(archive, target, stream.read(), 0o100000 | (member.mode & 0o777))
            elif not member.isdir():
                raise ValueError("Unexpected Python archive entry")


def native_launcher(destination):
    if sys.platform != "darwin":
        raise RuntimeError("Build the AppKit launcher on macOS, or supply --launcher built by the Mac CI workflow.")
    subprocess.run(["clang", "-fobjc-arc", "-Wall", "-Wextra", "-Wno-unused-parameter", "-framework", "Cocoa",
                    "-mmacosx-version-min=12.0", "-arch", "arm64", "-arch", "x86_64",
                    str(ROOT / "desktop/MacLauncher.m"), "-o", str(destination)], check=True)
    return destination


def build(machine, wheel, launcher=None):
    from soundshredder import __version__
    source, url, digest = python_archive(machine)
    label = RUNTIMES[machine][1]
    dest = WORK / f"SoundShredder-{__version__}-Mac-{label}.zip"
    bundle = {"machine": machine, "python": PYTHON_VERSION, "python_source": url, "python_sha256": digest}
    plist = {
        "CFBundleName": "SoundShredder", "CFBundleDisplayName": "SoundShredder",
        "CFBundleExecutable": "SoundShredder", "CFBundleIdentifier": "com.cyr4x.soundshredder",
        "CFBundlePackageType": "APPL", "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__, "CFBundleIconFile": "SoundShredder.icns",
        "LSMinimumSystemVersion": "12.0", "LSArchitecturePriority": [machine],
        "LSUIElement": True, "NSHighResolutionCapable": True,
    }
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        add_file(archive, APP + "Info.plist", plistlib.dumps(plist))
        add_file(archive, APP + "PkgInfo", b"APPL????")
        if launcher is None:
            launcher = native_launcher(WORK / "SoundShredder-launcher")
        add_file(archive, APP + "MacOS/SoundShredder", Path(launcher).read_bytes(), 0o100755)
        add_python(archive, source)
        for folder in ("soundshredder", "static"):
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    add_file(archive, APP + "Resources/" + path.relative_to(ROOT).as_posix(), path.read_bytes())
        for name in ("bootstrap.py", "serve.py", "lifetime.py", "setup.html", "MAC-README.md"):
            add_file(archive, APP + "Resources/desktop/" + name, (ROOT / "desktop" / name).read_bytes())
        add_file(archive, APP + "Resources/desktop/platform.json", json.dumps(bundle, indent=2).encode())
        add_file(archive, APP + "Resources/desktop/requirements.txt", requirements_for(machine).encode())
        add_file(archive, APP + "Resources/desktop/wheels/" + wheel.name, wheel.read_bytes())
        png = (ROOT / "desktop/icon-256.png").read_bytes()
        icns = b"icns" + struct.pack(">I", len(png) + 16) + b"ic08" + struct.pack(">I", len(png) + 8) + png
        add_file(archive, APP + "Resources/SoundShredder.icns", icns)
        add_file(archive, "START HERE.txt", (ROOT / "desktop/MAC-README.md").read_bytes())
    with zipfile.ZipFile(dest) as archive:
        assert archive.testzip() is None
    result = {"file": dest.name, "bytes": dest.stat().st_size,
              "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), **bundle,
              "signed": False, "mac_hardware_tested": False}
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", choices=["arm64", "x86_64", "all"], default="all")
    parser.add_argument("--bandit-wheel", type=Path, help="Reuse a wheel built from this repo's pinned Bandit commit")
    parser.add_argument("--launcher", type=Path, help="Precompiled universal AppKit launcher from the Mac CI workflow")
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.bandit_wheel:
        wheel = args.bandit_wheel.resolve()
    else:
        wheels = WORK / "wheels"
        wheels.mkdir(exist_ok=True)
        bandit = next(line for line in (ROOT / "requirements.txt").read_text().splitlines() if line.startswith("bandit-infer"))
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-cache-dir", "--no-deps", "--wheel-dir", str(wheels), bandit], check=True)
        wheel = next(wheels.glob("bandit_infer-*.whl"))
    machines = RUNTIMES if args.arch == "all" else [args.arch]
    launcher = args.launcher or native_launcher(WORK / "SoundShredder-launcher")
    builds = [build(machine, wheel, launcher) for machine in machines]
    (WORK / "build.json").write_text(json.dumps(builds, indent=2), encoding="utf-8")
    (WORK / "SHA256SUMS.txt").write_text("".join(f"{b['sha256']}  {b['file']}\n" for b in builds), encoding="utf-8")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
