# Future updates

No release date is committed for the remaining work. The stable v1.0.3 release remains the source ZIP. Browser-based standalones are separate v1.1.1 prereleases; Electron desktop work is in v1.2.0. Native Mac CI exercises launch and CPU workflows; consumer Gatekeeper and broader hardware validation remain separate checks.

## Electron desktop

- Shared web interface in a dedicated application window, with native menus and Save dialogs.
- Bundled Python and automatic engine setup; existing standalone engines and sessions retained.
- Close/reopen, duplicate-window prevention, active-work quit protection and owner-pipe crash cleanup.
- Windows per-user installer and separate Apple Silicon/Intel Mac DMG/ZIP packaging.
- Matching Windows/macOS documentation, including offline installation guides.

See [Electron documentation](electron/README.md). Publisher signing/notarization, automatic updates and broader GPU validation remain future work.

## Implemented in the standalone previews

- Per-user EXE installer with embedded Python and a Start menu shortcut.
- Branded CPU/NVIDIA setup screen with automatic dependency installation, stage progress, retry, and copyable logs.
- Private runtimes and session storage outside the installed application.
- Single-instance locking for standalone launches, with controls to close the app or change engines.
- Existing web interface and audio/video features retained.
- Separate Apple Silicon and Intel `.app` ZIPs with bundled Python, CPU-only automatic setup, native architecture checks and macOS file locking.
- Visible storage location/free space and package installs without retained pip downloads.

See [standalone documentation](desktop/README.md). Public installer signing, broader clean-machine validation, Mac hardware testing/notarization, and automatic app updates remain outstanding.

## Easier installation and updates

Priority: Windows first, then separate Apple Silicon and Intel Mac packages.

- Sign and validate the Windows installer on additional clean PCs before public distribution.
- Validate Finder launch, Gatekeeper, full first-run setup and real inference on Apple Silicon and Intel Macs; then sign and notarize the bundles.
- Improve first-run downloads with precise byte progress and cancellation rather than stage progress alone.
- Expand single-instance protection to cover legacy source launchers as well as standalone launches.
- Add guided app updates that install after active processing finishes.
- Preserve the existing local-processing workflow and familiar interface.

The Windows preview includes the first setup screen and diagnostics; keep improving recovery and usability with feedback from clean-machine testing.
