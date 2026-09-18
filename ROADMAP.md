# Future updates

No release date is committed for the remaining work. The latest release is v1.2.2, with Windows, Apple Silicon and Intel Mac installers together and source available separately. Earlier platform previews remain available for their verification history. Both Mac builds are Developer ID signed and Apple-notarized; native CI passed Gatekeeper, real CPU separation, export, close/reopen and crash recovery. A user confirmed the Finder installation test worked on their Mac. Broader hardware and Windows signing/SmartScreen validation remain separate work.

## Published in the Electron desktop app

- Shared web interface in a dedicated application window, with native menus and Save dialogs.
- Bundled Python and automatic engine setup; existing standalone engines and sessions retained.
- Close/reopen, duplicate-window prevention, active-work quit protection and owner-pipe crash cleanup.
- Windows per-user installer and separate Apple Silicon/Intel Mac DMG/ZIP packaging.
- Matching Windows/macOS documentation, including offline installation guides.
- Remembered engine/model/session storage choices, download progress, setup cancellation and disconnected-drive recovery.
- Developer ID signing and Apple notarization for both Mac architectures.

See the [Windows release](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.2-electron-windows-preview.1), [Mac release](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.2-electron-macos-preview.1) and [Electron documentation](electron/README.md). Windows publisher signing, automatic updates and broader GPU validation remain future work.

## Implemented in the standalone previews

- Per-user EXE installer with embedded Python and a Start menu shortcut.
- Branded CPU/NVIDIA setup screen with automatic dependency installation, stage progress, retry, and copyable logs.
- Private runtimes and session storage outside the installed application.
- Single-instance locking for standalone launches, with controls to close the app or change engines.
- Existing web interface and audio/video features retained.
- Separate Apple Silicon and Intel `.app` ZIPs with bundled Python, CPU-only automatic setup, native architecture checks and macOS file locking.
- Visible storage location/free space and package installs without retained pip downloads.

See [standalone documentation](desktop/README.md) for the earlier browser-based previews. Their verification history is separate from the newer Electron builds.

## Easier installation and updates

Next work across the Windows and Mac apps:

- Sign and validate the Windows installer and NVIDIA setup on additional clean PCs to extend validation beyond the verified CPU workflow.
- Expand consumer Mac testing across macOS versions, chip types, Applications/Dock launch and Bubble FX. Signing, notarization, Gatekeeper and CPU layer-separation/reopening checks already pass on both native architectures.
- Expand single-instance protection to cover legacy source launchers as well as standalone launches.
- Add guided app updates that install after active processing finishes.
- Preserve the existing local-processing workflow and familiar interface.

The Windows app includes the first setup screen and diagnostics; keep improving recovery and usability with feedback from clean-machine testing.
