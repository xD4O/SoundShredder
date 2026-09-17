# Electron desktop

SoundShredder's shared HTML/CSS/JavaScript interface runs in a sandboxed Electron window. The main process starts the bundled Python setup manager, then displays setup or the local workspace. No JavaScript rewrite of the audio engine is needed.

User guides: [Windows](docs/WINDOWS.md) · [macOS](docs/MACOS.md).

## Build

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
- Closing the window or native Quit asks the manager to stop. Setup or active audio jobs block orderly quit with an explanation. There is no package-install cancellation yet.
- Python and the renderer communicate over authenticated setup APIs and loopback-only workspace APIs. The renderer has no Node access; sandbox/context isolation remain enabled. Privileged IPC accepts only the main window's trusted top-level frame and fixed actions. Navigation and external links are restricted.
- Old sessions/runtimes are reused from the existing standalone profile. The Electron Chromium profile is a subdirectory. Uninstalling the application leaves engines/sessions intact.
- GitHub updates are manual. The Help menu links to Electron releases; the shared sidebar checker still follows stable source releases.

## Verification

`npm run test:app` exercises a real desktop window, private CPU setup, a generated one-second audio file, separation, export, three close/relaunch cycles, duplicate launches and saved-session retention. It uses only `artifacts/` profiles. Set `SS_TEST_EXECUTABLE` to test a packaged executable; otherwise it uses development Electron. `SS_TEST_HOME` can point to an existing QA profile under workspace artifacts to reuse its engine. It never uses the normal user profile.

The `electron-desktop.yml` workflow builds on Windows, native Apple Silicon and native Intel runners, then tests the packaged apps. Artifacts include platform instructions, checksums and verification screenshots/logs. Consumer Gatekeeper/SmartScreen behavior, publisher signing/notarization and GPU validation are separate from CI testing. Keep releases marked as previews until those checks are complete.
