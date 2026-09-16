# Standalone apps

Separate [Windows](https://github.com/xD4O/SoundShredder/releases/tag/v1.1.0-windows-preview.1) and [Mac](https://github.com/xD4O/SoundShredder/releases/tag/v1.1.0-macos-preview.1) prereleases are available. Each build includes its own Python interpreter and opens the same SoundShredder web interface, with a matching dark/mint setup screen. Users do not install Python, edit PATH, open a terminal, or install packages themselves.

## Using the installer

1. Open **SoundShredder-Setup-1.1.0-Windows.exe** on 64-bit Windows 10 or 11.
2. Choose **CPU** or **NVIDIA GPU** in the setup screen, then **Set up SoundShredder**. Keep an internet connection during the initial downloads. The setup progress bar represents stages, not a precise download percentage; Setup details shows package download progress.
3. Select **Open workspace** when ready. The familiar interface, video preview, presets, sessions, and track downloads remain available. Browser popup blocking may require clicking this button.
4. Reopen using **SoundShredder** in the Windows Start menu. Setup reuses its installed engine and checks it before opening the workspace. Launching the shortcut twice reopens the existing standalone manager.
5. Use **Close SoundShredder** in the setup screen to stop the app. Finish or cancel active audio jobs first. Closing a browser tab alone does not stop the server. Reopen the Start menu shortcut to get back to these controls.

The installer is currently unsigned. Code signing and broader clean-machine testing are required before treating it as a polished public installer. No administrator privileges or global Python changes are needed. Dependencies and models are not all bundled: setup downloads the selected engine automatically. CPU PyTorch is about 620 MB; NVIDIA PyTorch is about 3.2 GB, plus other packages. Keep at least 4 GiB free for CPU setup or 14 GiB for NVIDIA setup, plus model and session space. This build does not retain duplicate pip downloads. Layer separation downloads about 426 MB of model weights; Bubble FX downloads about 1.2 GB on first use.

## Files and upgrades

- Application: `%LOCALAPPDATA%\Programs\SoundShredder\1.1.0`
- Sessions: `%LOCALAPPDATA%\SoundShredder\data`
- Private engines: `%LOCALAPPDATA%\SoundShredder\runtimes`
- Settings and setup/app diagnostic logs: `%LOCALAPPDATA%\SoundShredder`
- Models continue using the existing caches in the user's home directory.

Application files and sessions are separate. Future versioned installer upgrades can reuse engines and sessions. Automatic app updates are still future work; the existing update checker opens GitHub releases. To transfer sessions from the source ZIP, close both apps and copy the old `data` contents into the standalone data folder without overwriting other sessions. The standalone manager prevents duplicate standalone instances; old source launchers are independent and should be closed first.

To change engines, use **Change engine** in the setup screen after processing finishes. Existing audio is retained. If setup fails, use **Retry setup** or select CPU. **Setup details** includes copyable diagnostics; review local paths before sharing. This version has no cancellation control while package setup is running.

## Building

On Windows with Python and pip available, run `python scripts/build_windows_standalone.py`. The build uses the Windows .NET Framework compiler. Outputs are under `artifacts/standalone/`; no user audio or model cache is packaged.

The build downloads the official CPython 3.13.15 embedded AMD64 package and checks its published SHA-256. It bundles pip and builds a wheel from the pinned Bandit commit. First-run setup installs only wheels into a private interpreter; the `_pth` file explicitly includes its package directory and application root, without loading user site-packages. Python and bundled dependency license files are retained.

## Mac standalone previews

Separate Apple Silicon and Intel `.app` ZIPs now include private Python 3.11.16 from checksum-pinned [Astral Python standalone builds](https://github.com/astral-sh/python-build-standalone/releases/tag/20260901). Both use the same web interface and branded setup screen. Intel retains PyTorch 2.2.2/NumPy 1.26.4/SciPy 1.14.1; Apple Silicon uses PyTorch 2.8.0. Processing uses CPU; Metal/MPS is not enabled.

See [the included Mac installation and uninstall guide](MAC-README.md). Build with `python scripts/build_mac_standalone.py` on a host with Python and pip. Both ZIPs and SHA256SUMS.txt are written under `artifacts/mac-standalone/`. ZIP Unix executable permissions and relative interpreter symlinks are preserved even when packaged on Windows. Python and pip license files remain in the app bundle. No audio, sessions or model caches are included.

The Mac builds are unsigned and unnotarized. Dependency resolution and package contents have been checked, but native Mac launch, Gatekeeper and inference have not been exercised here. They must remain previews until those checks pass. The older Mac source ZIP is still supported and still requires a separately installed Python.

## Storage fix in the published Windows preview

The original Windows EXE preview asked for 3 GB/8 GB. Updated setup source reserves 4 GiB for CPU or 14 GiB for NVIDIA, plus model and session space, and disables retained pip downloads. The published Windows prerelease has been rebuilt with these fixes. Earlier downloaded EXEs are unchanged; download the new asset from the Windows preview release. Mac setup reserves 3 GiB plus model/session space and does not retain pip downloads.
