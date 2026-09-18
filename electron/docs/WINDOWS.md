# SoundShredder 1.2.2 — Windows Electron preview

Made by cyr4x. Made for the Higgsfield Community.

## Install and open

1. Use Windows 10/11 **64-bit (x64)**. Download `SoundShredder-Electron-1.2.2-Windows-x64-Setup.exe` from the Windows Electron release.
2. Quit any earlier standalone using its setup page's **Close SoundShredder** control. Keep its engine/data folders to reuse your setup and sessions.
3. Run the installer. It installs for your user, lets you choose the app folder, and creates Start menu and desktop shortcuts, including **Uninstall SoundShredder** in Start. No administrator rights, separate Python, terminal commands or browser are required.
4. Open **SoundShredder**. Setup appears inside its own dark/mint application window. Use **Choose folder…** to select a drive for engines, models and sessions, or keep the existing location. Choose **CPU** or **NVIDIA GPU**, then **Set up SoundShredder**. Existing compatible engines are reused.
5. First setup needs internet and at least **4 GiB free for CPU** or **14 GiB for NVIDIA**, plus room for this app, models and sessions. The engine downloads automatically; NVIDIA requires a compatible GPU/driver. No separate CUDA Toolkit is required.
6. The workspace opens automatically when ready. Drop an audio/video file, select a preset, process, audition tracks, and save your mix or isolated tracks with the download buttons. Downloads show a native Save dialog.

Python is bundled; audio dependencies/models are downloaded separately. Models use about 426 MB for layer separation and 1.2 GB for Bubble FX. Once cached, processing works offline.

## Choose where your files live

The installer chooses the **application folder**. The setup screen's **Choose folder…** button chooses where the larger **engines, models, sessions and temporary setup downloads** go. For example, selecting `D:\Audio tools` uses `D:\Audio tools\SoundShredder`. Selecting an existing folder named `SoundShredder` uses that folder directly. Use a writable local or attached drive, separate from the app installation.

You can change this later from **SoundShredder > Choose storage folder…**. Finish or cancel setup and audio processing first. The choice persists when you close, reopen or update the app. **Existing files are not moved or deleted.** A new location has its own engine and sessions and may need fresh downloads. Select your original SoundShredder folder again to return to its saved work.

Keep external drives connected. If the saved folder is unavailable, the app offers **Retry opening** and **Choose storage folder…**; it does not silently download everything to C:. Reconnect the drive and retry, or choose another location.

## Follow or cancel first setup

Version 1.2.2 shows the current package, downloaded bytes, average speed and elapsed time. The main bar shows **setup stages**; the second bar shows the current download. Installing or checking downloaded packages can take time without moving either bar.

**Setup details** opens live diagnostics. **Cancel setup** stops installation safely and keeps your sessions. Closing the window during setup offers **Continue setup** or **Cancel setup and quit**. Reopen and select **Set up SoundShredder** to repair an interrupted engine; some packages may download again. A completed compatible engine is reused on normal launches.

Network requests have timeouts and limited retries. An installer command with no output for ten minutes stops with an explanation; each installer command also has a one-hour limit. If local setup loses its connection, the interface shows **Reconnecting** and keeps trying. If recovery fails, close and reopen the app, check internet/free space, then retry. Computer sleep, slow storage and network conditions can still affect completion time.

## Close, reopen and return

- Closing the window or **SoundShredder > Quit SoundShredder** stops the local engine. During setup you can cancel and quit. Active audio processing must finish or be canceled in the workspace before quitting.
- Open the Start menu or desktop shortcut again to start the engine and return. Double-opening brings the existing window forward instead of starting duplicate engines.
- **SoundShredder > Workspace** (`Ctrl+1`) returns to the workspace. **Setup and diagnostics** (`Ctrl+,`) opens engine settings and copyable diagnostics.
- Saved sessions remain in the left panel. Closing a session there removes that session; quitting the application does not remove sessions.

## Storage, updates and uninstall

The normal Electron app location is `%LOCALAPPDATA%\Programs\SoundShredder` (or your chosen installer folder). Without a folder choice, engines and sessions keep using `%LOCALAPPDATA%\SoundShredder`, and models use existing user caches. After choosing a folder, it holds `data` (sessions), `runtimes` (engines), `models`, `cache`, `temp` and logs. Small app preferences and the `electron` browser profile remain in `%LOCALAPPDATA%\SoundShredder` so the app remembers your choice. Older standalone launchers may remain in versioned subfolders such as `1.1.1`; the new Start menu shortcut opens Electron.

**Help > Check for Electron updates** opens GitHub releases. Install the matching newer Windows Electron release after quitting. Updates are manual; no background update installation is enabled. The workspace's existing update checker checks stable source releases, which are a separate channel.

### Uninstall the Windows app

1. Finish or cancel processing, then close every SoundShredder window.
2. Open Start, search for **Uninstall SoundShredder**, and run it. Follow the uninstall wizard. Alternatively, open **Windows Settings > Apps > Installed apps** (**Apps & features** on Windows 10), find SoundShredder, and choose **Uninstall**.
3. The app and its shortcuts are removed. **Saved sessions, downloaded engines, model caches and exported audio remain**, so reinstalling can reuse them.

The app's **SoundShredder > Uninstall SoundShredder…** menu also opens the Windows Settings uninstall screen. Older Electron installers already have a Windows Settings uninstaller; the explicit Start menu entry is included from Windows preview 2 onward.

For complete profile removal, first note the location shown in Setup and diagnostics, back up wanted audio and close every SoundShredder copy. If you chose another storage folder, remove that specific SoundShredder folder only when you no longer need its contents. Then open `%LOCALAPPDATA%\SoundShredder` in File Explorer and remove that specific folder only if you no longer need any of its sessions or downloaded engines. This also affects older standalone versions that share the profile. Do not delete shared model caches if another audio application needs them. Exported files outside this folder remain where you saved them.

## Troubleshooting

- **An older standalone is running:** close it using its own setup screen, then use Retry opening in Electron.
- **Storage unavailable:** reconnect the selected drive and use Retry opening, or choose another folder from the recovery screen. Select your old folder to return to its sessions.
- **Engine stopped:** use Retry opening. An interrupted job may need rerunning; saved files remain.
- **Setup failed:** check connection/storage, open Setup and diagnostics, and retry. CPU is an alternative to NVIDIA setup.
- **App files missing:** reinstall the Electron installer; retain the separate profile folder.
- **Details for support:** use Setup details or SoundShredder > Open logs folder. Review paths before sharing `electron-engine.log`, `setup.log`, or `app.log`.

This is an **unsigned prerelease**. Windows may show a publisher/SmartScreen warning. Only run downloads you trust. Broader clean-PC, GPU and installer testing continues; see the release's verification notes. Checksums are included with the release.
