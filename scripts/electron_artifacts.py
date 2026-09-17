"""Select a built executable and collect only matching platform release files."""
import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "artifacts/electron/dist"


def main():
    if sys.argv[1] == "executable":
        candidates = list(DIST.glob("mac*/SoundShredder.app/Contents/MacOS/SoundShredder")) if sys.platform == "darwin" else [DIST / "win-unpacked/SoundShredder.exe"]
        assert len(candidates) == 1 and candidates[0].is_file()
        with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as stream:
            stream.write(f"SS_TEST_EXECUTABLE={candidates[0]}\n")
    elif sys.argv[1] == "collect":
        mac = sys.platform == "darwin"
        guide = "MACOS" if mac else "WINDOWS"
        shutil.copy2(ROOT / f"electron/docs/{guide}.md", DIST / f"{guide}-INSTALL.md")
        files = sorted(p for p in DIST.iterdir() if p.is_file() and (p.suffix in ({".dmg", ".zip"} if mac else {".exe"}) or p.name == f"{guide}-INSTALL.md"))
        assert len(files) >= 2
        (DIST / "SHA256SUMS.txt").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files), encoding="utf-8")
    else:
        raise SystemExit("Use executable or collect")


if __name__ == "__main__":
    main()
