"""Package a one-file launcher repair for existing Mac source installations."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "Start SoundShredder - Certificate Fix.command"


def launcher():
    helper = (ROOT / "soundshredder/certificates.py").read_text(encoding="utf-8")
    return '''#!/bin/bash
set -u
cd -- "$(dirname -- "$0")" || exit 1
fail() {
    printf '\\n%s\\n' "$1"
    if [ -t 0 ]; then read -r -p "Press Return to close... " _reply; fi
    exit 1
}
[ "$(uname -s)" = "Darwin" ] || fail "This launcher is for macOS."
[ -f "app.py" ] && [ -x ".venv/bin/python" ] || fail "Put this launcher inside your existing SoundShredder folder, beside app.py. Run the original launcher first if setup has not finished."
export PYTHONUTF8=1
certificate_bundle="$("$PWD/.venv/bin/python" - <<'PYTHON_CERTIFICATES'
''' + helper + '''
PYTHON_CERTIFICATES
)" || fail "Python's certificates need repair. See the message above."
if [ -n "$certificate_bundle" ]; then
    export SSL_CERT_FILE="$certificate_bundle"
    printf 'Using Python trusted CA roots for model downloads. SSL verification stays enabled.\\n'
fi
printf 'Opening SoundShredder. Keep this window open; Control+C stops the app.\\n'
"$PWD/.venv/bin/python" app.py || fail "SoundShredder stopped. See the message above."
'''


def build(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    contents = {
        NAME: launcher(),
        "READ ME.txt": """MAC CERTIFICATE FIX — EXISTING SOURCE INSTALLS

1. Stop the old SoundShredder Terminal process with Control+C. Closing its browser tab is not enough.
2. Extract this ZIP in Finder.
3. Copy ONLY 'Start SoundShredder - Certificate Fix.command' into your existing SoundShredder folder, beside app.py.
4. Double-click the new launcher. Retry your audio/video processing in the browser.

No reinstall or replacement of your project folders is needed. Keep your .venv and data folders.
This launcher uses the trusted certificate bundle already supplied by certifi or pip when macOS Python has no default CA roots. It keeps HTTPS hostname and certificate verification enabled, changes no system trust settings, and respects existing SSL_CERT_FILE/SSL_CERT_DIR settings. It works with the recommended Python 3.11.9 source installation.

An alternative permanent Python fix is to run:
  open "/Applications/Python 3.11/Install Certificates.command"
Wait for completion, then restart the original SoundShredder launcher.

If the error persists, the network, VPN, proxy, or security software may be substituting certificates. Share the terminal error for diagnosis or ask the network administrator about its trusted certificate configuration. Never disable SSL verification.

This patch does not download audio models in advance; the first processing run still needs internet access. It has been tested with simulated missing-root conditions and launcher fixtures on Windows, not on the affected Mac.
""",
    }
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in contents.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(".command") else 0o100644) << 16
            archive.writestr(info, value.replace("\r\n", "\n").encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
    print(destination)
    return destination


if __name__ == "__main__":
    import shutil

    destination = build(ROOT / "support/mac/SoundShredder-Mac-Certificate-Fix.zip")
    artifact = ROOT / "artifacts/mac-certificates" / destination.name
    artifact.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(destination, artifact)
