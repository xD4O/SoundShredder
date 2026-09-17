# SoundShredder 1.2.0 — macOS Electron preview

Made by cyr4x. Made for the Higgsfield Community.

## Install and open

1. Use **macOS 13 Ventura or newer**. Check Apple menu > About This Mac: download **arm64** for Apple Silicon (M-series) or **x64** for Intel. Do not use the Windows installer.
2. Quit the previous standalone through its menu-bar Quit control or setup page's **Close SoundShredder**. Keep `~/Library/Application Support/SoundShredder` to reuse sessions and the CPU engine.
3. Open the matching `SoundShredder-Electron-1.2.0-macOS-…dmg`. Drag **SoundShredder** into **Applications**, replace the old app when prompted, then eject the disk image. Alternatively, extract the matching ZIP and move its app into Applications.
4. Open SoundShredder from Applications. Its original dark/mint interface now runs in its own window, with a Dock icon and application menus. Python is bundled; no Homebrew, Terminal commands or separate Python installation is needed.
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

This preview has **no Developer ID signing or notarization**. macOS may block browser-downloaded apps. Only for a download you trust, try opening it once, then System Settings > Privacy & Security > Open Anyway if offered. Do not disable Gatekeeper globally. If macOS reports damage or no override is offered, report the message; a signed release may be required. See release notes for what was actually tested on each architecture.
