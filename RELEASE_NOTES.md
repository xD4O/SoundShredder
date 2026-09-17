# SoundShredder releases

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
