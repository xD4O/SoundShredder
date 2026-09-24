# Future updates

No release date is committed for the remaining work. The latest release is v1.2.2, with Windows, Apple Silicon and Intel Mac installers together and source available separately. Earlier platform previews remain available for their verification history. Both Mac builds are Developer ID signed and Apple-notarized; native CI passed Gatekeeper, real CPU separation, export, close/reopen and crash recovery. A user confirmed the Finder installation test worked on their Mac. Broader hardware and Windows signing/SmartScreen validation remain separate work.

## Next major release: targeted cleanup with text prompts

The approved workflow is in source development: **Quick Cleanup · Easy** for presets and **Target a Sound · Guided** for local prompts, waveform intervals, short previews, independent strength/1–4-pass controls and saved versions. See the [accepted plan](docs/NEXT-RELEASE-PLAN.md), [development guide](docs/TARGETED-CLEANUP.md) and [AudioShake research](docs/AUDIOSHAKE-RESEARCH.md). Listening review, rendered UI checks and native installer validation remain before publication. No new version or date is committed; published installers remain 1.2.2.

## Mixing Lab — accepted and in source development

The approved Lab combines a shared video/audio playhead with Dialogue, Music, Effects and optional imported Ambience. Faders write edits for one nominal frame, one second or a selected interval, restoring the saved level outside it. It adds per-stem prompt cleanup with previews and 1–4 passes, source versions, removed-sound audition, imported replacements, WAV/stem ZIP export and optional video soundtrack replacement. See the [development guide](docs/MIXING-LAB.md).

Automatic ambience separation remains a research item. First evaluate a separate foreground-effects/background-ambience model against representative footage; a generic Effects output must not be relabeled as two independently separated stems. Instrument stems, EQ/compression, batching and installer changes are separate future work.

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

- Prioritize Windows publisher signing using the plan below.
- Validate NVIDIA setup on additional clean PCs to extend validation beyond the verified CPU workflow.
- Expand consumer Mac testing across macOS versions, chip types, Applications/Dock launch and Bubble FX. Signing, notarization, Gatekeeper and CPU layer-separation/reopening checks already pass on both native architectures.
- Expand single-instance protection to cover legacy source launchers as well as standalone launches.
- Add guided app updates that install after active processing finishes.
- Preserve the existing local-processing workflow and familiar interface.

The Windows app includes the first setup screen and diagnostics; keep improving recovery and usability with feedback from clean-machine testing.

## Next priority: Windows code signing

Planned as of September 18, 2026. The published Windows 1.2.2 installer is unsigned. The goal is a verified publisher on the application, installer and uninstaller, with repeatable signing for future releases.

Recommended service: **Microsoft Artifact Signing** (formerly Trusted Signing), using a **Public Trust** certificate profile. Microsoft's published starting price is **US$9.99/month**; confirm current billing before enrollment. Signing establishes publisher identity, but a new signed download can still trigger SmartScreen while reputation develops. A warning-free first download is not an acceptance criterion. [Microsoft signing and reputation guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)

1. **Set up the publisher identity.** Confirm eligibility and whether to enroll as an individual or a business. The individual route currently supports the US and Canada and requires an Individual Azure billing account whose legal name and address match the identity documents. Complete Azure enrollment, identity verification and a Public Trust profile. Review the certificate's publisher name before using it. This is a separate paid service from Apple Developer membership. [Microsoft setup guide](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart)
2. **Connect GitHub securely.** Use an Azure identity federated to a protected Windows release environment in `xD4O/SoundShredder`, with the Certificate Profile Signer role scoped to the selected profile. Prefer GitHub OIDC so a long-lived signing password is unnecessary. Record the tenant/client IDs, signing account, endpoint, certificate profile and verified publisher name in the release configuration. [Official GitHub integration](https://github.com/azure/artifact-signing-action)
3. **Integrate signing during packaging.** Extend `.github/workflows/electron-desktop.yml` and the Electron build configuration with an explicit signed Windows release mode. The repository pins electron-builder 26.15.3; use its v26 signing interface and prove OIDC authentication works through that path before enabling releases. Sign the application and generated uninstaller before they enter the NSIS package, then sign the final installer. Apply SHA-256 signatures and trusted timestamps. Inventory bundled native executables/libraries, preserve valid upstream signatures, and document any unsigned dependencies. [electron-builder v26 integration](https://www.electron.build/v26/docs/features/code-signing/code-signing-win/) and [Microsoft timestamping guidance](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations)
4. **Require signature verification.** A signed release build must fail if authentication, signing, publisher verification or timestamp validation fails. Verify the final installer and installed app/uninstaller using Authenticode and SignTool; retain a report with the build artifacts. Keep unsigned development builds clearly separate from release candidates.
5. **Test the actual download and upgrade.** Extend `scripts/test_windows_installer.ps1` to verify signatures on installed files. Test fresh installation, upgrading from unsigned 1.2.2, choosing a custom folder, CPU separation/export, quit/reopen, uninstall and reinstall with saved sessions retained. On a separate clean Windows PC, download through Edge with normal security settings and record the publisher and any SmartScreen prompts; hosted CI alone cannot establish consumer download reputation.
6. **Publish a new version after validation.** Create a draft with the tested signed installer, matching Windows guide and checksums generated after signing. Verify the downloaded asset matches the tested bytes before promotion. Update the README and release notes with the verified publisher and remaining SmartScreen expectations. Retain the existing 1.2.2 assets unchanged so earlier checksums remain meaningful.

The next setup dependency is the owner's Azure enrollment and identity verification. This plan does not enable signing or create a paid account; the existing Mac signing process and published downloads remain as they are.
