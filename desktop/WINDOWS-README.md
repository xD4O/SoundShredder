# SoundShredder Windows standalone preview 1.1.1

Made by cyr4x. Made for the Higgsfield Community.

## Install and start

1. Download **SoundShredder-Setup-1.1.1-Windows.exe** and open it on 64-bit Windows 10 or 11. No administrator privileges or separately installed Python are required.
2. The matching dark/mint setup screen opens in your browser. Choose **CPU** or **NVIDIA GPU**, check the displayed storage location/free space, then select **Set up SoundShredder**.
3. Keep internet connected during the automatic engine download. Allow **4 GiB free for CPU** or **14 GiB for NVIDIA**, plus model and session storage. The NVIDIA engine download is about 3.2 GB and expands substantially when installed. Package downloads are not retained in pip's shared cache by this build.
4. Select **Open workspace**. The existing web interface, video preview, presets, multi-pass bubble cleanup, isolated tracks and downloads are included. If automatic browser opening is blocked, click Open workspace yourself.
5. Reopen **SoundShredder** from the Windows Start menu after closing the browser or quitting the app. An existing workspace is reopened; a closed app starts again using your saved engine and sessions. **SoundShredder Setup** opens setup, diagnostics and the Close control.

Python 3.13.15 is bundled. The audio engine and models are downloaded separately and automatically. Layer separation downloads about 426 MB of weights, and Bubble FX about 1.2 GB on first use. Processing can run offline once the needed files are cached. CPU works without a supported NVIDIA GPU; CUDA mode requires a compatible NVIDIA GPU and driver. No separate CUDA Toolkit is needed.

## Close and troubleshoot

Use **Close SoundShredder** in the setup screen to stop the background app. Finish/cancel audio jobs first. Closing a browser tab alone does not stop it. Use **SoundShredder Setup** in the Start menu to return to the setup controls. Package installation cannot be cancelled from the setup screen yet; wait for it to finish or report an error.

Use **Setup details** for copyable logs, **Retry setup** after an error, or **Change engine** after processing finishes. Keep the application files in place while it runs. Close older source-package instances before using standalone. The standalone lock prevents duplicate standalone managers; source launchers are independent.

This preview is **unsigned**. Windows may show publisher/SmartScreen warnings. Only run a download you trust. The prior embedded CPU runtime completed real separation and WAV export; this release also undergoes package and launch checks. Broader clean-PC and NVIDIA validation remain outstanding. Model separation may leave artifacts or reduce wanted effects; audition the results.

## Storage and uninstall

**Upgrade from 1.1.0:** use Close SoundShredder in the old setup screen, then open the new installer. Keep the engine, data and model folders. The updated Start menu shortcuts point to 1.1.1 and reuse your engine and sessions. Reopening this installer also repairs missing app files and recreates the shortcuts; close the app first when repairing damaged files.

- App: `%LOCALAPPDATA%\Programs\SoundShredder\1.1.1`
- Engines: `%LOCALAPPDATA%\SoundShredder\runtimes`
- Sessions: `%LOCALAPPDATA%\SoundShredder\data`
- Setup/app logs and settings: `%LOCALAPPDATA%\SoundShredder`
- Models: `~/.cache/bandit-infer/` and `~/.cache/soundshredder/audiosep/`

To remove this preview, first use Close SoundShredder. Delete the versioned app folder and both SoundShredder Start menu shortcuts. Delete `runtimes` to reclaim engine space. Keep `data` if you want saved sessions. There is no registered Windows uninstaller yet. Old preview downloads may have left pip cache files; this build does not clear shared caches or remove other applications' files.

To transfer sessions from a source ZIP, close both apps and copy the old `data` contents into the standalone `data` folder without overwriting existing sessions. Automatic updates are not implemented. The update checker only checks stable releases; obtain preview updates from their release pages and close the app before replacing it.

Project: https://github.com/xD4O/SoundShredder
Windows previews: https://github.com/xD4O/SoundShredder/releases/tag/v1.1.1-windows-preview.1
Creator: https://higgsfield.ai/@cyr4x
