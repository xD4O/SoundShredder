# Electron desktop

SoundShredder's shared HTML/CSS/JavaScript interface runs in a sandboxed Electron window. The main process starts the bundled Python setup manager, then displays setup or the local workspace. No JavaScript rewrite of the audio engine is needed.

User guides: [Windows](docs/WINDOWS.md) · [macOS](docs/MACOS.md).

Published downloads: [Windows Electron preview](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.1-electron-windows-preview.1) · [macOS Electron preview](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.0-electron-macos-preview.1). The illustrated [community guide](../output/pdf/SoundShredder-Higgsfield-Community-Guide-v1.2.0.pdf) covers installation, presets, video, track exports and sessions.

## Build

Build from a Git clone of the full repository. The separately packaged browser source ZIPs include these guides for reference but do not include the complete Electron build project.

Use Node.js 24 and Python 3.12+ with pip on the target OS. Build Mac arm64 on Apple Silicon and Mac x64 on Intel. Electron 44 requires macOS 13+; legacy browser-based standalones support macOS 12.

```sh
python scripts/prepare_electron.py
cd electron
npm ci
npm test
npm start
```

Package Windows with `npm run build -- --win --x64`; package Mac with `npm run build -- --mac --arm64` or `--x64`. Output is in `artifacts/electron/dist`. Each package includes `resources/backend/INSTALLATION.md` for its own platform; Help opens that guide. Build inputs include checksum-pinned Python, the existing pinned Bandit source, and a committed npm lockfile. Node/Electron/Python development tools are not required by users.

## Lifecycle and isolation

- Electron's single-instance lock focuses the existing window. The shared Python lock prevents overlap with an older standalone using the same profile. A running older version must be closed before Electron starts.
- The setup manager owns the workspace through a pipe; Electron owns the manager through another pipe. EOF triggers cleanup after a host crash. No process is selected or killed using a stale PID file.
- Closing the window or native Quit asks the manager to stop. During setup, users choose Continue setup or Cancel setup and quit. Active audio jobs still block orderly quit until finished or canceled in the workspace.
- Setup runs on a worker thread; status polling avoids disk probes, diagnostics fetch independently, and installer output supplies package/download activity. Network requests have bounded timeouts and retries. Installer commands stop after ten minutes without output or one hour overall; workspace readiness has a two-minute deadline.
- Cancel stops the owned installer process. Incomplete copy/install markers trigger repair of only the private engine folder on explicit retry. Interrupted setup does not automatically restart at launch. Sessions and models remain separate, and completed compatible engines are reused.
- Python and the renderer communicate over authenticated setup APIs and loopback-only workspace APIs. The renderer has no Node access; sandbox/context isolation remain enabled. Privileged IPC accepts only the main window's trusted top-level frame and fixed actions. Navigation and external links are restricted.
- Old sessions/runtimes are reused from the existing standalone profile. The Electron Chromium profile is a subdirectory. Uninstalling the application leaves engines/sessions intact.
- GitHub updates are manual. The Help menu links to Electron releases; the shared sidebar checker still follows stable source releases.

## Verification

`npm run test:setup-ui` injects stalled status and diagnostics responses into the actual setup page in Electron. It checks download reporting, a live timer, usable cancellation, bounded requests, reconnection and narrow-screen overflow. Python regression tests use real stalled child processes to check cancellation, deadlines, interrupted-runtime repair and preservation of saved audio. On a fresh profile, `npm run test:app` additionally cancels setup, retries, tests both native quit choices, then reopens and completes the real CPU installation before the processing/lifecycle checks below.

**Mac distribution issue (September 18, 2026):** the original preview used `mac.identity: null` and did not pass a browser-download Gatekeeper test. Current test packaging uses an explicit ad-hoc identity, hardened runtime, JIT/library-validation entitlements, and strict signature verification. Ad-hoc signing is an integrity measure for testing, **not Developer ID signing or notarization**. The existing release binaries are unchanged. See [Mac launch troubleshooting](docs/MACOS.md#finder-says-damaged-or-cannot-be-opened).

`python scripts/verify_mac_distribution.py` verifies the DMG container, extracts both DMG and ZIP, verifies the app and all native code (including Python), records Gatekeeper/stapler results, and selects a copy from the DMG for lifecycle tests. `--after-lifecycle` rechecks that installed copy after setup, processing, crashes and reopening. Python launches disable bytecode writes so importing modules cannot change the signed bundle. No step clears quarantine or disables Gatekeeper.

For a **notarized** Mac candidate, follow the [maintainer signing setup](docs/MAC-SIGNING.md), then dispatch the workflow with `mac_signing: developer-id`. This uses `build/notarized.cjs`, requires signing/notarization credentials and enforces `--require-notarized` before and after lifecycle testing. That flag fails unless both Gatekeeper assessment and stapled-ticket validation pass. Keep credential values out of the repository. Then test an actual browser download, drag to Applications, quit and relaunch on a separate Mac. Automatic push builds remain ad-hoc tests; they must not be presented as notarized releases.

The [published builds passed on all three native platforms](https://github.com/xD4O/SoundShredder/actions/runs/35167472250). See the [versioned verification record](../VERIFICATION.md#electron-desktop-120-2026-09-16) for scope and remaining limitations.

`npm run test:app` exercises a real desktop window, private CPU setup, generated one-second video/audio, video playback/toggling, separation, export, active-job quit protection, four launch cycles, duplicate launches and saved-session retention. One cycle simulates a desktop crash and verifies engine shutdown and subsequent relaunch. It uses only `artifacts/` profiles. Set `SS_TEST_EXECUTABLE` to test a packaged executable; otherwise it uses development Electron. `SS_TEST_HOME` can point to an existing QA profile under workspace artifacts to reuse its engine. It never uses the normal user profile.

The `electron-desktop.yml` workflow builds on Windows, native Apple Silicon and native Intel runners, then tests the packaged apps. Artifacts include platform instructions, checksums and verification screenshots/logs. Consumer Gatekeeper/SmartScreen behavior, publisher signing/notarization and GPU validation are separate from CI testing. Keep releases marked as previews until those checks are complete.
