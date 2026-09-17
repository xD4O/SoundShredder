# SoundShredder 1.2.0 — Windows Electron preview

Made by cyr4x. Made for the Higgsfield Community.

## Install and open

1. Use Windows 10/11 **64-bit (x64)**. Download `SoundShredder-Electron-1.2.0-Windows-x64-Setup.exe` from the Windows Electron release.
2. Quit any earlier standalone using its setup page's **Close SoundShredder** control. Keep its engine/data folders to reuse your setup and sessions.
3. Run the installer. It installs for your user, lets you choose the app folder, and creates Start menu and desktop shortcuts. No administrator rights, separate Python, terminal commands or browser are required.
4. Open **SoundShredder**. Setup appears inside its own dark/mint application window. Choose **CPU** or **NVIDIA GPU**, then **Set up SoundShredder**. Existing compatible engines are reused.
5. First setup needs internet and at least **4 GiB free for CPU** or **14 GiB for NVIDIA**, plus room for this app, models and sessions. The engine downloads automatically; NVIDIA requires a compatible GPU/driver. No separate CUDA Toolkit is required.
6. The workspace opens automatically when ready. Drop an audio/video file, select a preset, process, audition tracks, and save your mix or isolated tracks with the download buttons. Downloads show a native Save dialog.

Python is bundled; audio dependencies/models are downloaded separately. Models use about 426 MB for layer separation and 1.2 GB for Bubble FX. Once cached, processing works offline.

## Close, reopen and return

- Closing the window or **SoundShredder > Quit SoundShredder** stops the local engine. During setup or active audio processing, finish/cancel that work before quitting; the app explains what is still running.
- Open the Start menu or desktop shortcut again to start the engine and return. Double-opening brings the existing window forward instead of starting duplicate engines.
- **SoundShredder > Workspace** (`Ctrl+1`) returns to the workspace. **Setup and diagnostics** (`Ctrl+,`) opens engine settings and copyable diagnostics.
- Saved sessions remain in the left panel. Closing a session there removes that session; quitting the application does not remove sessions.

## Storage, updates and uninstall

The normal Electron app location is `%LOCALAPPDATA%\Programs\SoundShredder` (or your chosen installer folder). Your shared profile is `%LOCALAPPDATA%\SoundShredder`: `data` contains sessions, `runtimes` holds engines, `electron` holds window/browser settings, and logs live beside them. Model caches remain in your user folder. Older standalone launchers may remain in versioned subfolders such as `1.1.1`; the new Start menu shortcut opens Electron.

**Help > Check for Electron updates** opens GitHub releases. Install the matching newer Windows Electron release after quitting. Updates are manual; no background update installation is enabled. The workspace's existing update checker checks stable source releases, which are a separate channel.

Uninstall **SoundShredder** through Windows Settings > Apps. Sessions, shared engines and model caches are retained. To remove those too, first back up wanted audio, close every SoundShredder copy, then remove `%LOCALAPPDATA%\SoundShredder` yourself. Do not delete shared model caches if another audio application needs them.

## Troubleshooting

- **An older standalone is running:** close it using its own setup screen, then use Retry opening in Electron.
- **Engine stopped:** use Retry opening. An interrupted job may need rerunning; saved files remain.
- **Setup failed:** check connection/storage, open Setup and diagnostics, and retry. CPU is an alternative to NVIDIA setup.
- **App files missing:** reinstall the Electron installer; retain the separate profile folder.
- **Details for support:** use Setup details or SoundShredder > Open logs folder. Review paths before sharing `electron-engine.log`, `setup.log`, or `app.log`.

This is an **unsigned prerelease**. Windows may show a publisher/SmartScreen warning. Only run downloads you trust. Broader clean-PC, GPU and installer testing continues; see the release's verification notes. Checksums are included with the release.
