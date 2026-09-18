#!/bin/bash
# Read-only maintainer check. Never exports private keys or reads passwords.
set -u

if [[ "$(uname -s)" != Darwin ]]; then
  printf '%s\n' 'Run this check on the Mac that holds your signing certificate.' >&2
  exit 1
fi

status=0
printf '%s\n' 'SoundShredder Mac signing readiness' ''
if /usr/bin/xcode-select -p >/dev/null 2>&1 && /usr/bin/xcrun --find notarytool >/dev/null 2>&1; then
  printf '%s\n' 'PASS: Apple notarytool is available.'
else
  printf '%s\n' 'NEEDED: Install current Xcode command-line tools (or Xcode), then run this check again.'
  status=1
fi

found=0
if identities=$(/usr/bin/security find-identity -v -p codesigning 2>/dev/null); then
  while IFS= read -r line; do
    if [[ "$line" == *'"Developer ID Application: '* ]]; then
      printf '%s\n' "FOUND: $line"
      found=1
    fi
  done <<< "$identities"
else
  printf '%s\n' 'NEEDED: Unlock your login keychain in Keychain Access, then run this check again.'
  status=1
fi

if [[ "$found" -eq 0 ]]; then
  printf '%s\n' 'NEEDED: A valid Developer ID Application identity and its private key in Keychain Access.'
  printf '%s\n' 'A downloaded .cer alone, Apple Development, or Developer ID Installer is not sufficient.'
  status=1
else
  printf '%s\n' 'Compare the Team ID in parentheses with Membership details in Apple Developer.'
fi

printf '\n%s\n' 'This read-only check does not export keys, upload credentials, or prove notarization access.'
printf '%s\n' 'Next: follow electron/docs/MAC-SIGNING.md to add private credentials directly to GitHub Actions secrets.'
exit "$status"
