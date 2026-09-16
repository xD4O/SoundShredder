#!/bin/sh
# Finder launcher. Python is bundled; no system Python, Homebrew or Terminal needed.
set -eu
umask 077
resources=$(CDPATH='' cd "$(dirname "$0")/../Resources" && pwd -P)
expected="@ARCH@"
actual=$(/usr/bin/uname -m)
if [ "$actual" != "$expected" ]; then
    /usr/bin/osascript -e 'display alert "Choose the matching Mac download" message "Download Apple Silicon for M-series Macs, or Intel for Intel Macs. This package is for a different processor." as critical'
    exit 1
fi
version=$(/usr/bin/sw_vers -productVersion)
if [ "${version%%.*}" -lt 12 ]; then
    /usr/bin/osascript -e 'display alert "macOS update required" message "SoundShredder requires macOS 12 Monterey or newer." as critical'
    exit 1
fi
case "$resources" in
    /Volumes/*)
        /usr/bin/osascript -e 'display alert "Move SoundShredder first" message "Copy SoundShredder.app to your Applications folder, then open that copy."'
        exit 1 ;;
esac
profile=${SOUNDSHREDDER_DESKTOP_HOME:-"$HOME/Library/Application Support/SoundShredder"}
mkdir -p "$profile"
unset PYTHONHOME PYTHONPATH
exec "$resources/python/bin/python3.11" -I "$resources/desktop/bootstrap.py" "$@" >> "$profile/launcher.log" 2>&1
