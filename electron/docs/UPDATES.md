# Desktop updates

**Available from SoundShredder 1.3.0.** Install 1.3.0 manually once if you are coming from 1.2.2 or an older standalone. Future compatible stable desktop releases can be downloaded and installed through this panel.

## Using the updater

The installed Electron app checks official stable GitHub releases shortly after opening. Open **Help > Check for Electron updates** or the update control at the bottom of either workspace's sidebar.

1. Review the available version, download size and release notes.
2. Choose **Download update**. The workspace stays usable while the download runs. Progress is visible in the panel and sidebar; **Cancel** stops the download.
3. Choose **Restart & update** when ready, or **Later** to keep working. Closing the panel leaves a download running. Closing the app normally does **not** install an update.

The restart checks for pending uploads/saves, file downloads, engine setup and active processing or exports. Busy or unresponsive work blocks installation; finish or cancel it, then retry. Updates do not cancel jobs automatically. Network failures leave the installed app intact and offer a retry or the GitHub releases link.

Saved sessions, storage selection and compatible downloaded engines/models remain outside the application and are reused. Changed engine requirements may need a new setup download. The installer updates the application in its existing location; it does not move or delete user media. The updater's temporary app download uses the operating system's application cache, separately from the chosen engine/model storage folder. Allow free space there as well as at the application location.

The browser/source edition keeps its manual update checker. Development Electron runs do not download or install desktop releases.

## Platform requirements

- **Windows:** uses the per-user NSIS installer and relaunches after the explicit restart action. SHA-512 metadata verifies downloaded bytes. Windows publisher signing remains pending; a checksum is not a publisher certificate. See [Windows download warnings](../../docs/WINDOWS-DOWNLOADS.md).
- **Mac:** requires the Developer ID signed application and a matching signed ZIP, in addition to the DMG used for initial installation. Release candidates must also pass notarization, Gatekeeper and installed-app verification. Install in Applications first. Intel receives x64; Apple Silicon receives arm64, including an app initially opened under Rosetta.
- Stable numbered releases only; prereleases and downgrades are not selected. A source commit alone does not announce an update.

## Preparing a release

`electron-updater` reads the GitHub provider embedded by `electron-builder`. The repository is fixed to `xD4O/SoundShredder`. `npm run build` still uses `--publish never`: building is not publishing.

1. Choose a new stable application version and synchronize all existing version files. Build Windows x64 and both Mac architectures from the same commit. Use the established [Mac signing workflow](MAC-SIGNING.md), not an ad-hoc build, for distributed Mac updates.
2. Keep each Windows EXE, Mac ZIP and DMG, and their generated blockmaps. Do not modify or re-sign a payload after generating update metadata; rebuild metadata and checksums if bytes change.
3. Collect the platform artifacts with `scripts/electron_artifacts.py collect`. The CI `update-metadata` job verifies each referenced asset's SHA-512 and size and merges both architectures into **one** `latest-mac.yml`. Windows uses `latest.yml`. The same merge can run locally:

   ```sh
   node electron/build/merge-updates.cjs collected-artifacts merged-metadata
   ```

4. Attach the installers, ZIPs, blockmaps, matching platform instructions and merged manifests to the **same draft stable GitHub release**. Use the merged `latest-mac.yml`, not one architecture's original file. Regenerate the final release checksum list after this merge; platform checksum files refer to the original per-platform manifests.
5. Validate an upgrade from the previous updater-enabled build before publishing. Only publish a complete, verified asset set. Missing manifests or payloads produce a recoverable check/download error. Ad-hoc CI artifacts must never become the public Mac update feed.

Existing 1.2.2 clients cannot acquire this updater without one manual upgrade. Keep the manual GitHub download path available for recovery and older clients.

## Verification

From `electron/`:

```sh
npm test
npm run test:updates-ui
# Windows only: builds, installs and upgrades a separate QA application
npm run test:updates-native
```

The first two cover update state transitions, stalled/cancelled downloads, verification rejection, metadata integrity, IPC boundaries, rendered controls and active-work protection. The native Windows check uses a distinct app ID and an installation/profile under `artifacts/electron/update-native`; it exercises real HTTP metadata, checksum verification, NSIS replacement, relaunch and retained profile data. It uses a small harness rather than the Python audio engine and uninstalls that QA app afterward.

The CI-only `npm run test:upgrade` builds a full test baseline with the candidate code and a lower app version, then updates it to the final payload on Windows and both Mac architectures. This first updater release cannot use 1.2.2 as an automatic-update baseline because that version lacks an updater. It retains real saved media and custom storage, checks Later plus ordinary Quit, blocks a pending-save restart, verifies automatic relaunch and reopens a completed result. Mac baselines and replacements must pass Developer ID, Gatekeeper and stapling checks in Applications. Subsequent releases should also upgrade from the previously published updater-enabled version. Check playback/export after relaunch, a busy job blocking restart, offline recovery, normal Quit after **Later**, and an interrupted download. Mac needs a signed-to-signed upgrade from Applications. The isolated Windows test and mocked error tests are not evidence that all native Mac failures or every power-loss stage recover correctly. See the [verification record](../../VERIFICATION.md).
