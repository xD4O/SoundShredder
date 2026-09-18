# SoundShredder 1.2.2 — macOS Electron guide

Made by cyr4x. Made for the Higgsfield Community.

> **For the 1.2.2 Mac Electron preview.** Use the release notes to check the exact downloads and completed verification. The older 1.2.0 preview remains unsigned and unnotarized and has a known Finder launch issue; a newer release does not change those older files.

SoundShredder opens the familiar dark/mint workspace in its own Mac application window. Python is bundled. The audio engine and models download when needed; you do not need Homebrew, a separate Python installation, or an Apple developer account to use it.

## Choose your download

Use **macOS 13 Ventura or newer**. Open **Apple menu > About This Mac** to check your computer.

| Your Mac | Download |
| --- | --- |
| Apple Silicon — M1, M2, M3, M4 or newer M-series | [SoundShredder-Electron-1.2.2-macOS-arm64.dmg](https://github.com/xD4O/SoundShredder/releases/download/v1.2.2-electron-macos-preview.1/SoundShredder-Electron-1.2.2-macOS-arm64.dmg) |
| Intel processor | [SoundShredder-Electron-1.2.2-macOS-x64.dmg](https://github.com/xD4O/SoundShredder/releases/download/v1.2.2-electron-macos-preview.1/SoundShredder-Electron-1.2.2-macOS-x64.dmg) |

Matching ZIP files are alternatives to the DMGs. Use the native build for your chip. This release processes audio on the **CPU**; Apple Metal/MPS and NVIDIA acceleration are not enabled. Processing speed depends on your Mac, clip length and chosen cleanup settings.

## Install and open

1. Download from the [official SoundShredder releases](https://github.com/xD4O/SoundShredder/releases). Check the release tag and architecture before opening the file. `SHA256SUMS.txt` is provided for checking download integrity.
2. Quit any previous SoundShredder app. For the older browser-based standalone, use its setup page's **Close SoundShredder** control or its menu-bar Quit control. Keep your engine and session folders.
3. Open the matching DMG. Drag **SoundShredder** to **Applications**, replace the previous app if prompted, then eject the disk image. For a ZIP, extract it and move **SoundShredder.app** into Applications.
4. Open **SoundShredder** from Applications or Finder. macOS may ask you to confirm opening an app downloaded from the internet. If it says the app is damaged or cannot be opened, use the troubleshooting below; do not assume setup completed.
5. In setup, choose **Choose folder…** if you want engines, models and sessions on another drive. Otherwise, keep the existing location. Select **Set up SoundShredder** to install the CPU engine. A compatible completed engine is reused.
6. Keep internet connected and allow at least **3 GiB free for engine setup**, plus space for the app, models and your media. Model downloads are approximately **426 MB** for layer separation and **1.2 GB** for Bubble FX. These are additional to the setup allowance.
7. The workspace opens when the engine is ready. Drop audio or video into it, choose a preset, process, listen and export. Your audio is processed locally; cached engines and models can process files offline.

## Choose where your files live

The app belongs in **Applications**. The setup screen's **Choose folder…** button controls the larger **engines, model downloads, sessions and temporary setup files**. You can change this later through **SoundShredder > Choose storage folder…** after finishing or canceling active setup and audio work.

Choose a writable local or attached drive with enough free space. SoundShredder creates a `SoundShredder` folder inside the selected location, or reuses that folder when you select it directly. For example, choosing `/Volumes/Media/Audio tools` uses `/Volumes/Media/Audio tools/SoundShredder`.

The location is remembered when you quit, reopen or update. **Existing files are not moved or deleted.** An empty location starts a separate engine/session setup and may require new downloads. Select your original SoundShredder folder again to return to its saved sessions. Automatic file migration is not included.

Keep the chosen drive connected. If it is unavailable, reconnect it and use **Retry opening**, or choose another folder from the recovery screen. SoundShredder does not silently replace the missing profile with a new one on your internal drive. Small app preferences remain in `~/Library/Application Support/SoundShredder` so the app remembers your choice.

## Follow, cancel or retry setup

Setup shows the current package, downloaded bytes, average download speed and elapsed time. The main progress bar tracks **setup stages**; a separate bar tracks the current download. Installing or checking downloaded packages can take time without either bar moving. **Setup details** opens live diagnostics.

Use **Cancel setup** to stop. Closing the window while setup runs offers **Continue setup** or **Cancel setup and quit**. Reopen and select **Set up SoundShredder** to repair an interrupted engine. Sessions stay saved; some packages may download again. Compatible completed engines are reused on normal launches.

Network requests have timeouts and limited retries. An installer command stops after ten minutes without output or one hour overall and provides an explanation and retry path. A lost local connection shows **Reconnecting**. If it does not recover, close and reopen the app, check internet access and free space, then retry. Network conditions, computer sleep and slow storage can still delay completion.

## Clean up, compare and export

Drop a supported audio or video file, including MP3 or MP4, into the workspace. Choose a preset to reduce unwanted dialogue, music or sound effects. The **Water bubbles** preset targets unwanted bubble sounds; optional aggressive multi-pass cleanup can catch more of them, but may also remove wanted sounds. Start with fewer passes and compare the **Original**, **Cleaned** and **Removed sounds** previews.

The optional video player helps compare the sound against your footage; hide or show it as needed. The listening tracks provide separate dialogue, music, sound-effects and removed-sound previews. In bubble sessions, prepare the additional tracks when offered. Download the cleaned mix or isolated tracks through the native Save dialog. These exports are audio files; the player does not render a replacement video.

Use the left panel to return to saved sessions or start a new one. Closing/removing a session there removes that session; **quitting the app preserves sessions**. Export wanted audio before deleting a session.

## Quit and reopen

- Close the application window or choose **SoundShredder > Quit SoundShredder** (`Cmd+Q`) to stop the local engine. During setup, you can cancel and quit. Finish or cancel active audio processing in the workspace before quitting.
- Open SoundShredder again from **Applications** or the Dock. Saved sessions and compatible engines are reused. Opening an already-running copy brings its window forward instead of starting another engine.
- **SoundShredder > Workspace** (`Cmd+1`) returns to your sessions. **Setup and diagnostics** (`Cmd+,`) opens engine settings, storage information and diagnostics.
- **Retry opening** can restart a stopped engine. An interrupted audio job may need to be rerun from its saved session.

## Updates, storage and uninstall

**Help > Check for Electron updates** opens GitHub releases. Quit the app, download the matching newer Mac build and replace the app in Applications. Updates are manual; no automatic app replacement is enabled. The workspace sidebar's update checker checks stable source releases, which are a separate channel.

Without a folder choice, engines and sessions remain in `~/Library/Application Support/SoundShredder`, and models use the existing user caches. After choosing a folder, that folder holds `data` (sessions), `runtimes` (engines), `models`, `cache`, `temp` and diagnostic logs. Small preferences and the `electron` browser profile remain in the default Application Support folder. Replacing the app preserves these separate locations.

To uninstall:

1. Finish or cancel active work and quit every SoundShredder copy.
2. Move **SoundShredder.app** from Applications to Trash. Remove its Dock shortcut if wanted.
3. Your sessions, downloaded engines, model caches and exported audio remain for later reuse.

For complete data removal, first note the storage location shown in **Setup and diagnostics** and back up wanted audio. Remove only that specific SoundShredder storage folder and `~/Library/Application Support/SoundShredder` after all copies are closed. This also affects older standalones sharing the same profile. Keep shared model caches used by other audio apps. Files exported elsewhere stay where you saved them.

## Finder says damaged or cannot be opened

The **older `v1.2.0-electron-macos-preview.1` download** skipped signing and notarization and has a known Finder launch issue. Its DMG and ZIP contain the same app; changing archive formats does not repair its trust status. A newer release does not alter those old downloads.

For version 1.2.2, check the [Mac release notes](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.2-electron-macos-preview.1) for the verified signing/notarization status and exact tested files. Personal-Mac browser-download/Finder validation remains unverified unless the release notes explicitly report it.

If the disk image itself will not mount, download it again and compare its SHA-256 with the release's checksum file. If the image mounts but the app is blocked, confirm the version and chip type, quit old copies, copy the app into Applications and eject the image before retrying. Report the exact warning if the problem persists. Do not disable Gatekeeper or remove quarantine as an installation step.

Optional read-only support checks in Terminal:

```sh
codesign --verify --deep --strict --verbose=4 "/Applications/SoundShredder.app"
spctl --assess --type execute --verbose=4 "/Applications/SoundShredder.app"
```

A successful signature check establishes bundle integrity; it does not alone prove notarization. See [Apple's explanation of Mac app warnings](https://support.apple.com/en-us/102445). The [local Mac browser version](https://github.com/xD4O/SoundShredder#mac-browser-setup) remains available if you cannot launch the desktop app.

## Other troubleshooting

- **Wrong architecture:** check About This Mac and use arm64 for Apple Silicon or x64 for Intel; macOS 13 or newer is required.
- **Older standalone already running:** quit it through its own setup page/menu-bar control, then use **Retry opening** in Electron.
- **Storage unavailable:** reconnect the chosen drive and retry, or select another folder on the recovery screen. Select the original folder to return to saved work.
- **Setup failed or stopped:** check internet access and free space, open Setup details and retry. Keep the app open and the drive connected while setup runs.
- **SSL / CERTIFICATE_VERIFY_FAILED:** the Electron app uses its bundled Python and CA roots. Repairing a separate system Python installation does not repair that bundled runtime. Check VPN/proxy settings; a managed network may require its administrator's trusted CA configuration. Keep certificate verification enabled. If you are running the browser/source version instead, follow that version's Mac setup and certificate troubleshooting.
- **Logs for support:** use **SoundShredder > Open logs folder** or copy **Setup details**. Include the release filename, macOS version, chip type and exact error. Review private paths before sharing logs; do not send private audio unnecessarily.

Community-created; not an official Higgsfield product.
