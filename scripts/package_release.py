"""Create the redistributable source ZIP without audio, models or virtualenv files."""

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE_FILES = [
    "output/html/SoundShredder-Higgsfield-Community-Guide.html",
    "output/pdf/SoundShredder-Higgsfield-Community-Guide-2026-09-16.pdf",
]
FILES = [
    "README.md",
    "ROADMAP.md",
    "VERIFICATION.md",
    "RELEASE_NOTES.md",
    "app.py",
    "setup_runtime.py",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-mac-intel.txt",
    "START HERE - MAC.txt",
    "Start SoundShredder.command",
    ".gitignore",
    ".gitattributes",
] + GUIDE_FILES
WINDOWS_FILES = ["Start SoundShredder.bat", "Setup CPU.bat", "Setup NVIDIA GPU.bat"]


def build_release(root, destination, *, mac_only=False):
    sources = [root / name for name in FILES + ([] if mac_only else WINDOWS_FILES)]
    for directory in ("soundshredder", "static", "tests", "scripts", "desktop", "support"):
        sources.extend(
            path for path in (root / directory).rglob("*") if path.is_file() and "__pycache__" not in path.parts
        )
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(sources):
            info = zipfile.ZipInfo.from_file(source, "SoundShredder/" + source.relative_to(root).as_posix())
            # Set Unix executable permissions even when building this ZIP on Windows.
            info.create_system = 3
            info.external_attr = (0o100755 if source.suffix == ".command" else 0o100644) << 16
            payload = source.read_bytes()
            if source.suffix == ".command":
                payload = payload.replace(b"\r\n", b"\n")
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        if not mac_only:
            assert "SoundShredder/Start SoundShredder.bat" in archive.namelist()
        launcher = archive.getinfo("SoundShredder/Start SoundShredder.command")
        assert launcher.create_system == 3 and (launcher.external_attr >> 16) & 0o111 == 0o111
        assert b"\r" not in archive.read(launcher)
        assert "SoundShredder/START HERE - MAC.txt" in archive.namelist()
        assert "SoundShredder/soundshredder/engine.py" in archive.namelist()
        assert not any("/.venv/" in name or "/data/" in name for name in archive.namelist())
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(f"{destination}\n{destination.stat().st_size:,} bytes\nSHA-256: {digest}")
    return digest


def main():
    parser = argparse.ArgumentParser(description="Build universal and Mac source ZIPs")
    parser.add_argument("--mac-only", action="store_true", help="Build only SoundShredder-Mac.zip")
    args = parser.parse_args()
    checksums = []
    if not args.mac_only:
        digest = build_release(ROOT, ROOT / "SoundShredder.zip")
        checksums.append(f"{digest}  SoundShredder.zip")
    digest = build_release(ROOT, ROOT / "SoundShredder-Mac.zip", mac_only=True)
    checksums.append(f"{digest}  SoundShredder-Mac.zip")
    for name in GUIDE_FILES:
        guide = ROOT / name
        checksums.append(f"{hashlib.sha256(guide.read_bytes()).hexdigest()}  {guide.name}")
    (ROOT / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
