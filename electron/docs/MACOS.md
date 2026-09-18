# SoundShredder 1.2.0 — macOS Electron preview

Made by cyr4x. Made for the Higgsfield Community.

> **Known issue — updated September 18, 2026:** the published Electron Mac preview can be blocked by Finder with “SoundShredder is damaged and can't be opened.” It has no Developer ID signature or Apple notarization. Use the [local browser version](https://github.com/xD4O/SoundShredder#mac-browser-setup) while normal Mac distribution is being resolved. A ZIP of the same app does not solve its trust status.

## Finder says damaged or cannot be opened

This is an installation/launch failure, not a successful install. The published build explicitly skipped app signing. Automated launch tests on a build runner did not exercise a browser download through Gatekeeper. The message alone does not establish whether your copy is corrupted, has an invalid signature, or was rejected by local policy.

1. Download only from the [official Mac release](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.0-electron-macos-preview.1). Choose **arm64** for M-series Macs or **x64** for Intel; use macOS 13 or newer. If the **disk image itself** will not mount, download it again and check its SHA-256 against the release's `SHA256SUMS.txt`.
2. If the image opens, quit SoundShredder, drag the app into Applications and eject the image before trying to open it. Replacing the app does not remove your separate engine or sessions.
3. For an **unidentified developer / cannot check for malicious software** warning on a copy you trust, Apple offers **System Settings > Privacy & Security > Open Anyway** after the first launch attempt, when available. This is a user-approved exception, not notarization. See [Apple's instructions](https://support.apple.com/en-us/102445).
4. If the message says **damaged**, or no override is offered, use the browser version. Do not keep reinstalling the same preview, disable Gatekeeper globally, or run a generic “Mac cleaner.” Do not treat a checksum match as proof of Apple approval.

Optional read-only checks for a support report (Terminal; no administrator access needed):

```sh
codesign --verify --deep --strict --verbose=4 "/Applications/SoundShredder.app"
spctl --assess --type execute --verbose=4 "/Applications/SoundShredder.app"
```

Include the exact alert, macOS version, chip type, release filename and command output. A successful `codesign` check establishes bundle integrity; Gatekeeper can still reject an app without a trusted developer signature and notarization. Avoid sharing private paths or audio.

Source changes now enable **ad-hoc signing** for test builds, keep Python from writing cache files inside the installed bundle, and add DMG/ZIP integrity checks before and after the real processing/relaunch tests. These changes do **not** notarize the existing download. A normal public Mac release still needs a Developer ID Application certificate, Apple notarization, a stapled ticket and testing on a Mac with standard Gatekeeper settings.

## Install and open

1. Use **macOS 13 Ventura or newer**. Check Apple menu > About This Mac: download **arm64** for Apple Silicon (M-series) or **x64** for Intel. Do not use the Windows installer.
2. Quit the previous standalone through its menu-bar Quit control or setup page's **Close SoundShredder**. Keep `~/Library/Application Support/SoundShredder` to reuse sessions and the CPU engine.
3. Open the matching `SoundShredder-Electron-1.2.0-macOS-…dmg`. Drag **SoundShredder** into **Applications**, replace the old app when prompted, then eject the disk image. Alternatively, extract the matching ZIP and move its app into Applications.
4. Try opening SoundShredder from Applications. If Finder blocks it, follow the launch troubleshooting above; setup cannot start until macOS allows the app to run. Once opened, its original dark/mint interface runs in its own window, with a Dock icon and application menus. Python is bundled; no Homebrew or separate Python installation is needed.
5. On first use, choose **Set up SoundShredder**. The **CPU engine** downloads automatically. Keep internet connected and at least **3 GiB free**, plus room for the app, models and sessions. Apple Metal/MPS and NVIDIA acceleration are not enabled in this Mac preview.
6. The workspace opens when ready. Drop audio/video into it, select a preset, listen to the tracks alongside your footage, and download your mix or isolated tracks through a native Save dialog.

Models download on first feature use: about 426 MB for layer separation and 1.2 GB for Bubble FX. Processing works offline once the needed files are cached. Audio is processed locally.

## Quit and reopen

- Close the window or choose **SoundShredder > Quit SoundShredder** (`Cmd+Q`) to stop the local engine. If setup or audio processing is active, finish/cancel it before quitting; the app explains what is still running.
- Open SoundShredder again from Applications or the Dock whenever you return. Saved sessions and compatible engines are reused. Opening a running copy brings its window forward.
- **SoundShredder > Workspace** (`Cmd+1`) and **Setup and diagnostics** (`Cmd+,`) switch between the workspace and setup.
- Sessions remain in the left panel. Closing a session there removes that session; quitting the app preserves sessions.

## Updates, storage and uninstall

**Help > Check for Electron updates** opens GitHub releases. Quit, download the matching Mac architecture, and replace the app in Applications. Updates are manual; no automatic app replacement is enabled. The workspace's existing update checker checks stable source releases, a separate channel.

The shared profile is `~/Library/Application Support/SoundShredder`: `data` contains sessions, `runtimes` contains the CPU engine, `electron` contains window/browser settings, and diagnostic logs live beside them. Models use existing user caches. Replacing the app preserves this profile.

To uninstall, quit and move SoundShredder.app to Trash. Sessions, engines and models remain. For a complete removal, back up wanted audio and remove the shared profile yourself after all copies are closed. Keep any model caches needed by other apps.

## Troubleshooting

- **Older standalone already running:** quit its menu-bar app or close its setup screen's engine, then use Retry opening in Electron.
- **Engine stopped:** Retry opening restarts it; interrupted jobs can be rerun from the saved session.
- **Wrong architecture:** return to the release and choose arm64 for Apple Silicon or x64 for Intel.
- **SSL / CERTIFICATE_VERIFY_FAILED:** the app has its own Python and CA bundle. Repairing system Python does not fix the bundled runtime. Check VPN/proxy settings; a managed network may need its trusted CA configured by the administrator. Keep certificate verification enabled. Include the full error and Setup details when reporting it.
- **Diagnostic logs:** open SoundShredder > Open logs folder, or copy Setup details. Review local paths before sharing.

This preview has **no Developer ID signing or notarization**. See the launch issue at the top of this guide and the release notes for what was actually tested on each architecture. The browser version remains available while a notarized desktop release is pending.
