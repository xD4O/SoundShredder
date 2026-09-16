#!/bin/bash
# Compatible with the Bash 3.2 supplied by macOS. Keep this file beside app.py.
set -u
cd -- "$(dirname -- "$0")" || exit 1

fail() {
    printf '\n%s\n' "$1"
    printf 'See START HERE - MAC.txt for installation and troubleshooting.\n'
    if [ -t 0 ]; then
        read -r -p "Press Return to close this window... " _reply
    fi
    exit 1
}

if [ "$(uname -s)" != "Darwin" ]; then
    fail "This launcher is for macOS. On Windows, use Start SoundShredder.bat."
fi

printf '\n  SOUNDSHREDDER / MAC\n  Dialogue. Music. Effects. Your mix.\n\n'
export PYTHONUTF8=1

if [ -x ".venv/bin/python" ]; then
    python_bin="$PWD/.venv/bin/python"
else
    python_bin=""
    # Finder's PATH can omit Homebrew and python.org, so check their usual locations.
    for version in 3.11 3.12 3.10 3.13; do
        for candidate in \
            "/Library/Frameworks/Python.framework/Versions/$version/bin/python$version" \
            "/opt/homebrew/bin/python$version" \
            "/usr/local/bin/python$version" \
            "$(command -v "python$version" 2>/dev/null || true)"; do
            if [ -n "$candidate" ] && [ -x "$candidate" ] && \
                "$candidate" -c 'import platform, sys; upper=(3,11) if platform.machine()=="x86_64" else (3,13); sys.exit(not ((3,10)<=sys.version_info[:2]<=upper))' >/dev/null 2>&1; then
                python_bin="$candidate"
                break 2
            fi
        done
    done
    if [ -z "$python_bin" ]; then
        fail "Install Python 3.11 using the macOS universal2 installer from python.org, then open this launcher again."
    fi
fi

if [ ! -x ".venv/bin/python" ] || ! "$python_bin" setup_runtime.py --device cpu --check >/dev/null 2>&1; then
    printf 'Setting up your local CPU runtime. Internet is needed on first launch.\n'
    "$python_bin" setup_runtime.py --device cpu || fail "Setup did not finish. Your files have been kept; you can retry."
fi

printf '\nOpening http://127.0.0.1:7860 in your browser.\n'
printf 'Keep this Terminal window open. Press Control+C to stop SoundShredder.\n\n'
"$PWD/.venv/bin/python" app.py || fail "SoundShredder stopped with an error. See the message above."
