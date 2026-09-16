# SoundShredder for Mac — standalone preview 1.1.0

Made by cyr4x. Made for the Higgsfield Community.

## Install and open

1. Choose **AppleSilicon** for M1/M2/M3/M4/M5 and other M-series Macs, or **Intel** for Intel Macs. Apple menu > About This Mac shows your chip or processor. Requires macOS 12 Monterey or newer.
2. Double-click the ZIP in Finder. Drag **SoundShredder.app** into Applications (or your own `~/Applications` folder).
3. Open SoundShredder. Its matching dark/mint setup screen opens in your default browser. Python is included; you do not need Homebrew, Terminal, pip commands, or a separate Python installer.
4. Check the displayed storage location and free space, then select **Set up SoundShredder**. Keep internet connected for the automatic CPU engine download. Allow at least **3 GiB free**, plus model and session space. Package downloads are not retained in pip's shared cache.
5. Choose **Open workspace** when ready. The original web interface, video preview, bubble presets/multi-pass cleanup, isolated track playback, and downloads are all included. If your browser blocks automatic opening, click Open workspace yourself.

This is an **unsigned, unnotarized preview**. Packaging and dependency resolution are checked on Windows; Finder launch, Gatekeeper behavior and real Mac inference still need Mac hardware testing. macOS may block the first launch. Only for a download you trust, try opening it once, then use System Settings > Privacy & Security > Open Anyway if offered. Do not disable Gatekeeper globally. If macOS says the app is damaged or no Open Anyway option is available, stop and report that message; this preview may need a signed Mac build.

## Same workspace, local processing

Drop an MP4/video or audio file into the workspace. Choose layer separation to remove or isolate dialogue, music or effects. Choose Bubble FX for targeted bubble removal; aggressive multi-pass can remove more persistent bubbles but can affect wanted effects, so compare the original, cleaned and removed tracks. Use the optional video preview to hear changes against your footage. Download individual stems or the cleaned mix. The sidebar holds recent sessions and the New session action; closing a session does not uninstall the app.

The Mac build currently processes on **CPU**. Apple Metal/MPS and NVIDIA CUDA are not enabled. Apple Silicon uses PyTorch 2.8.0. Intel uses Python 3.11, PyTorch 2.2.2, NumPy 1.26.4 and SciPy 1.14.1 for compatibility. CPU processing can take longer than the clip duration.

Models download on first use: approximately 426 MB for layer separation and 1.2 GB for Bubble FX. These are retained for reuse. Your audio stays local. Once dependencies and the relevant models are downloaded, processing can run offline. Update checks require internet and currently open the GitHub release page; they do not install an update automatically.

## Reopen, close, and troubleshoot

Open SoundShredder.app again to return to setup and reopen your workspace. A second launch reuses the existing standalone manager. Your installed engine is checked and reused. Close any older source-package instance before launching the standalone app.

Use **Close SoundShredder** on the setup screen to stop its background server. Finish/cancel audio jobs first. Closing a browser tab alone does not stop it. While setup is installing packages, wait for it to finish; this preview has no package-install cancellation control. Reopen the app to get back to the setup screen.

If setup fails, use **Retry setup** and check free space/network access. **Setup details** provides copyable diagnostics. Review local paths before sharing logs. Do not move the .app while setup or processing is running. If you move it later, reopen the .app at its new location; the runtime's app path is refreshed automatically.

If processing reports `CERTIFICATE_VERIFY_FAILED`, retain the full error and Setup details. The standalone app uses its own Python and CA bundle, so repairing a separately installed system Python may not affect it. Do not copy a source `.command` repair launcher inside the `.app`. A VPN, proxy or company network may need its trusted certificate configured by the administrator; keep SSL verification enabled. The separate source ZIP has different recovery steps in `support/mac/README.md`, including the Python 3.11.9 certificate installer and repair launcher.

## Storage and uninstall

The app is about 70 MB extracted; dependencies, models and audio use additional space.

- Application: wherever you placed `SoundShredder.app`.
- Engine: `~/Library/Application Support/SoundShredder/runtimes/`.
- Saved sessions: `~/Library/Application Support/SoundShredder/data/`.
- Settings and diagnostic logs: `~/Library/Application Support/SoundShredder/`.
- Bubble model: `~/.cache/soundshredder/audiosep/`. Bandit weights use `~/.cache/bandit-infer/`.

To uninstall, first use Close SoundShredder. Move the .app to Trash. In Finder choose Go > Go to Folder, enter `~/Library/Application Support/SoundShredder`, and remove only `runtimes` to reclaim engine space while keeping sessions. Remove the whole SoundShredder support folder only if you also want to permanently discard its sessions/settings. Remove the SoundShredder-specific bubble cache only if you no longer need it. Do not delete shared Hugging Face or pip caches indiscriminately. Empty only these items from Trash when you are ready to reclaim the space.

Mac preview release: https://github.com/xD4O/SoundShredder/releases/tag/v1.1.0-macos-preview.1

Project and updates: https://github.com/xD4O/SoundShredder
Creator: https://higgsfield.ai/@cyr4x
