# SoundShredder releases

## v1.3.0 — Target a sound. Mix the scene.

### Desktop updates

The Electron app checks stable GitHub releases automatically. Review release notes and download size, download while working with progress/cancel, then choose **Restart & update** or **Later**. Ordinary Quit never installs a downloaded update. Pending uploads/saves, downloads, setup, processing and exports block restart. Sessions, storage selection and compatible engines/models are retained. [Update guide](electron/docs/UPDATES.md).

**Coming from 1.2.2 or an older standalone? Install 1.3.0 manually once.** This adds the updater for future compatible releases. The browser/source edition still updates manually.

### Targeted cleanup and Mixing Lab

- **Quick Cleanup · Easy** keeps familiar presets; **Target a Sound · Guided** adds a local sound description, waveform interval, short preview and independent strength / 1–4 passes. Compare Original, Cleaned and Removed, then save a new version. Original uploads and earlier versions remain available.
- **Mixing Lab** puts reference footage beside Dialogue, Music, Effects and optional imported Ambience. The visible extraction area prepares stems. Edit one nominal frame, one second or a selected range; levels return to their saved values outside it. Mute/solo, clean a selected stem with a prompt, import replacements and export channel WAVs, a master, ZIP or an MP4 with the new soundtrack.
- **Close session** in the Lab moves it to **Closed sessions** and persists across restarts. This differs from deleting a separator session. Recursive **Split deeper** remains paused; older experimental child assets/settings are retained but do not enter the four-channel mix.
- The illustrated community HTML/PDF and Windows/Mac guides cover installation, the Akira walkthrough, prompt cleanup, Lab extraction, exports and updating. Direct installer links are clickable.

Prompt cleanup is experimental. More passes may remove wanted detail; preview and listen to Removed sounds. Ambience extraction, instrument stems, EQ/compression and recursive splits are not included. The models are unchanged pretrained models, not newly trained separation models.

### Installation and validation

Windows uses the per-user EXE with a selectable application folder and a separate remembered engine/model/session location. It remains **unsigned**; read the [download warning guide](docs/WINDOWS-DOWNLOADS.md). Apple Silicon and Intel Mac releases use Developer ID signing and Apple notarization. Each platform includes its own installation guide.

See [verification](VERIFICATION.md) for native build/upgrade evidence and limitations. Broader consumer hardware, perceptual separation quality and Windows publisher signing remain separate work. Historical versions below retain their original context.

## v1.2.2 - Current Windows and Mac downloads

- [Latest release](https://github.com/xD4O/SoundShredder/releases/latest) now points to 1.2.2 with the Windows EXE, signed/notarized Apple Silicon and Intel Mac packages, platform guides and checksums together.
- Installer bytes match the previously verified platform releases; existing 1.2.2 users do not need to reinstall.
- The sidebar checker now recognizes 1.2.2 as the latest published version. Updates remain manual. Previous entries below describe their original release channels.

## v1.2.2 - Signed macOS Electron preview

- [Apple Silicon and Intel downloads](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.2-electron-macos-preview.1) are now Developer ID signed and Apple-notarized, with verified Gatekeeper acceptance and stapled tickets.
- Both native builds passed real CPU processing, export, video preview, setup recovery, storage selection and close/reopen/crash tests. A user confirmed the final Finder installation test worked on their Mac; the chip type was not recorded.
- Includes matching Mac installation instructions and checksums. Replace the older unsigned Mac preview with these new files. [Verification and limits](VERIFICATION.md#signed-and-notarized-mac-electron-release-122).

## v1.2.2 - Choose your storage folder

- Native **Choose folder…** in setup and **SoundShredder > Choose storage folder…** let desktop users put engines, model caches, sessions and temporary setup downloads on a selected local or attached drive. Windows still offers a separate application-folder choice in its installer.
- The selected location persists across launches. Existing files stay untouched; choosing an old location returns to its engine and sessions. Uninstalling retains saved data.
- Unavailable drives show recovery controls instead of silently switching to the system drive. Folder checks run asynchronously, and failed switches restore the previous profile.
- Fixed a startup error message that could be lost while the welcome screen loaded and a close request that could be ignored while switching folders.
- Windows and Mac guides distinguish the app folder from storage. These changes are included in the signed Mac 1.2.2 release above.


## v1.2.0 - Electron desktop previews

The original SoundShredder interface now opens in its own desktop window. Python is bundled; first use automatically downloads the audio engine and required models. Video preview, cleanup presets, aggressive Water bubbles and isolated-track downloads are retained.

- Native menus, Save dialogs, setup/diagnostics and an offline installation guide.
- Normal window close or native Quit stops the engine; active work must finish or be cancelled first. Reopening restores access to saved sessions. Duplicate launches focus the existing window.
- Recovery after a desktop crash, with local engine cleanup and saved sessions preserved.
- [Windows installer and Windows instructions](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.0-electron-windows-preview.1): Windows 10/11 x64, CPU or NVIDIA.
- [macOS downloads and Mac instructions](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.0-electron-macos-preview.1): Apple Silicon and Intel DMG/ZIP, macOS 13+, CPU only.

Both releases are public **unsigned prereleases**; Mac builds lack Developer ID signing/notarization. Updates are manual through **Help > Check for Electron updates**. The sidebar checker and `/releases/latest` continue following the stable v1.0.3 source release. Upgrading the desktop app retains its separate profile; no source-folder copying is required for an Electron-to-Electron update.

Validation: 173 Python tests and three Electron boundary tests passed. Packaged apps on native Windows, Apple Silicon and Intel runners completed CPU setup, real MP4/audio separation, video preview, WAV export, active-job quit protection, duplicate launches and four close/reopen cycles including crash recovery. Windows installation/reinstallation and its Start menu shortcut were also checked locally. Consumer Gatekeeper/SmartScreen behavior, broader hardware testing and Electron GPU inference remain outside these checks. [Verification record](VERIFICATION.md#electron-desktop-120-2026-09-16).

The updated [community PDF](output/pdf/SoundShredder-Higgsfield-Community-Guide-v1.2.0.pdf) and [HTML](output/html/SoundShredder-Higgsfield-Community-Guide.html) cover desktop installation, closing/reopening and the separate update channels. Historical release assets retain their original documents.

## v1.0.3 - Video preview (stable source)

- Toggleable footage monitor with a remembered show/hide preference.
- Preview original, cleaned, dialogue, music, effects, or removed audio against the same footage.
- Shared play/pause and seeking; audio players drive the muted video clock.
- Reopen saved video sessions without uploading again, with byte-range support for seeking.
- Audio-only sessions hide the monitor. Unsupported browser video codecs show an explanation while audio cleanup remains available.
- Preview only: existing WAV/ZIP exports are unchanged. Browser codec support varies; H.264 MP4 is recommended. Containers with audio/video start offsets may need alignment checked in an editor.
- Local Windows/Mac source packages; no cloud deployment. Updated eleven-page HTML/PDF community guides cover detailed Windows PC installation, Mac setup, video preview and the future installation roadmap.

Validation: 131 Python tests passed, Ruff and JavaScript syntax checks passed. Browser checks used a saved MP4 session with all six audio choices available. Mac hardware testing remains outstanding.

### Source downloads and updating

Download SoundShredder.zip for Windows or SoundShredder-Mac.zip for Mac from the assets below. Both ZIPs include installation instructions, README, ROADMAP and the HTML/PDF guides. Python is still installed separately. Finish processing and close the old app, extract the new ZIP into a fresh folder, and copy your old data folder into it to retain sessions. Run the new launcher; cached models are reused. Keep the old folder until the new installation is checked.
