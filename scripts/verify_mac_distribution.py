"""Verify actual Mac archives and distinguish bundle integrity from Apple trust.

Run on macOS after packaging. The DMG copy becomes the lifecycle test app.
Nothing removes quarantine, changes Gatekeeper, or writes into /Applications.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "artifacts/electron"
MACHO = {bytes.fromhex(value) for value in (
    "feedface", "cefaedfe", "feedfacf", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca",
)}


def run(*args, required=True):
    result = subprocess.run([str(arg) for arg in args], capture_output=True, text=True, timeout=180)
    text = (result.stdout + result.stderr).strip()
    if required and result.returncode:
        raise RuntimeError(f"{args[0]} failed ({result.returncode}): {text}")
    return {"returncode": result.returncode, "output": text}


def native_files(app):
    for item in sorted(app.rglob("*")):
        if item.is_symlink() or not item.is_file():
            continue
        with item.open("rb") as stream:
            if stream.read(4) in MACHO:
                yield item


def verify_bundle(app, *, require_notarized=False):
    if not app.is_dir() or app.suffix != ".app":
        raise RuntimeError(f"Missing app bundle: {app}")
    signature = run("/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=4", app)
    natives = list(native_files(app))
    if not natives:
        raise RuntimeError("No native code found in app")
    # Python lives under Resources; verify its executables and modules explicitly too.
    for native in natives:
        run("/usr/bin/codesign", "--verify", "--strict", native)
    identity = run("/usr/bin/codesign", "--display", "--verbose=4", app)
    python = app / "Contents/Resources/backend/python/bin/python3.11"
    run(python, "-I", "-B", "-c", "import ssl,sqlite3,ctypes,zlib,decimal; print('Bundled Python imports OK')")
    assessment = run("/usr/sbin/spctl", "--assess", "--type", "execute", "--verbose=4", app, required=False)
    ticket = run("/usr/bin/xcrun", "stapler", "validate", app, required=False)
    trusted = assessment["returncode"] == 0 and ticket["returncode"] == 0
    if require_notarized and not trusted:
        raise RuntimeError("Distribution blocked: Gatekeeper acceptance and a stapled notarization ticket are required")
    return {"app": str(app), "integrity": "passed", "native_files_verified": len(natives),
            "signature": signature, "identity": identity, "gatekeeper": assessment, "stapled_ticket": ticket,
            "notarized_distribution_ready": trusted}


def verify_archives(dist, install_root, *, require_notarized=False):
    arch = "arm64" if platform.machine() == "arm64" else "x64"
    results = {}
    for extension in ("dmg", "zip"):
        archives = list(dist.glob(f"SoundShredder-Electron-*-macOS-{arch}.{extension}"))
        if len(archives) != 1:
            raise RuntimeError(f"Expected exactly one {arch} {extension}, found {len(archives)}")
        archive = archives[0]
        destination = install_root / extension
        destination.mkdir()
        if extension == "dmg":
            run("/usr/bin/hdiutil", "verify", archive)
            with tempfile.TemporaryDirectory(prefix="soundshredder-mount-") as mount:
                run("/usr/bin/hdiutil", "attach", archive, "-readonly", "-nobrowse", "-mountpoint", mount)
                try:
                    run("/usr/bin/ditto", Path(mount) / "SoundShredder.app", destination / "SoundShredder.app")
                finally:
                    run("/usr/bin/hdiutil", "detach", mount)
        else:
            run("/usr/bin/ditto", "-x", "-k", archive, destination)
        app = destination / "SoundShredder.app"
        results[extension] = verify_bundle(app, require_notarized=require_notarized)
        results[extension]["archive"] = archive.name
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-lifecycle", action="store_true")
    parser.add_argument("--require-notarized", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Run distribution verification on macOS")
    evidence = WORK / "verification"
    evidence.mkdir(parents=True, exist_ok=True)
    report = {"architecture": platform.machine(), "require_notarized": args.require_notarized}
    name = "mac-after-lifecycle.json" if args.after_lifecycle else "mac-distribution.json"
    try:
        if args.after_lifecycle:
            app = Path(os.environ["SS_TEST_EXECUTABLE"]).resolve().parents[2]
            report["installed_app"] = verify_bundle(app, require_notarized=args.require_notarized)
        else:
            install_root = Path(tempfile.mkdtemp(prefix="Mac install with spaces ", dir=WORK))
            report["packages"] = verify_archives(WORK / "dist", install_root, require_notarized=args.require_notarized)
            executable = install_root / "dmg/SoundShredder.app/Contents/MacOS/SoundShredder"
            if os.environ.get("GITHUB_ENV"):
                with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as stream:
                    stream.write(f"SS_TEST_EXECUTABLE={executable}\n")
            report["lifecycle_executable"] = str(executable)
        report["status"] = "passed"
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        (evidence / name).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
