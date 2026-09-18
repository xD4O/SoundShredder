# Mac signing setup for the maintainer

This guide is for the SoundShredder publisher. App users do not need an Apple developer account. Keep the public Mac launch notice in place until a replacement passes notarization and a normal browser-download/Finder test.

**Already an active member?** Start by checking for an existing **Developer ID Application** identity on your Mac, then add its credentials directly to GitHub Actions secrets. Membership alone does not sign an app. Do not send passwords, private keys or certificate exports through chat. The **Team ID** shown in Membership details is the value needed below; an enrollment or order ID is not a substitute.

## 1. Check your membership

Sign in yourself at [Apple Developer Account](https://developer.apple.com/account/). Check **Membership details** for an active **Apple Developer Program** membership and a Team ID. A free developer login or Xcode Personal Team is not sufficient. Apple lists **US$99 per membership year** (regional pricing can differ). This is the publisher's membership; SoundShredder users do not need to pay it. If the account offers **Join / Enroll**, review [Apple's membership information and current pricing](https://developer.apple.com/programs/enroll/) before deciding whether to enroll. Enrollment, payment and agreements are completed by the account owner. The local browser version remains available without this membership.

Open **Certificates, Identifiers & Profiles**. For an organization, certificate access depends on the role assigned by its Account Holder. Do not buy another membership if the correct team already has access. See [Apple's Developer ID certificate requirements](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/).

## 2. Create or use a Developer ID Application certificate

If you have a SoundShredder source checkout on the Mac, run this from its folder in Terminal:

```sh
bash scripts/check_mac_signing.sh
```

This uses only macOS tools. It checks for Apple's `notarytool` and lists valid Developer ID Application identities already in your keychain, including their public certificate names and Team IDs. It does not export keys, request passwords, change the keychain, or upload anything. A passing check does not prove that Apple will authorize notarization. You can also check **Keychain Access > My Certificates** manually; no source checkout is required for the following steps.

On your Mac, use **Keychain Access > Certificate Assistant > Request a Certificate From a Certificate Authority** to create a certificate signing request saved to disk. Use your account details; the private key stays in that Mac's keychain.

In the Apple developer account, open **Certificates**, add a certificate, and select **Developer ID Application** for distribution outside the Mac App Store. Follow Apple's prompts using the request created on your Mac, download the resulting certificate, and open it to import it into Keychain Access. If an appropriate certificate and its private key already exist, reuse them.

Use **Developer ID Application**, not **Apple Development**, **Apple Distribution** or **Developer ID Installer**. SoundShredder ships as a DMG/ZIP app; it does not need an Installer certificate for a `.pkg`. Do not revoke or replace an existing identity just because a new certificate can be created.

In Keychain Access, select **My Certificates**. Find **Developer ID Application: … (TEAMID)** and confirm it expands to show a private key. Export that identity and key as a password-protected **.p12**, for example `SoundShredder-Developer-ID.p12`. A `.cer` without its private key cannot sign the app. Keep the `.p12` and password private; do not commit them, attach them to issues, or paste them into chat.

## 3. Store credentials in GitHub

Open [SoundShredder Actions secrets](https://github.com/xD4O/SoundShredder/settings/secrets/actions) yourself. Create these repository secrets using **New repository secret**:

| Secret name | Value |
| --- | --- |
| `MAC_CSC_LINK` | Base64-encoded contents of the exported `.p12` certificate and private key. |
| `MAC_CSC_KEY_PASSWORD` | The password you chose when exporting the `.p12`. |
| `MAC_CSC_NAME` | The certificate's full name, such as `Developer ID Application: Your Name (TEAMID)`. |
| `APPLE_ID` | Your Apple account email, authorized to notarize for the team. |
| `APPLE_APP_SPECIFIC_PASSWORD` | An app-specific password created at [Apple Account](https://account.apple.com/), under Sign-In and Security. This is **not** your normal Apple password. |
| `APPLE_TEAM_ID` | The Team ID from your Developer Program membership. |

To copy the `.p12` as base64 on a Mac without printing the private key into Terminal, adjust the path and run:

```sh
base64 -i "$HOME/Desktop/SoundShredder-Developer-ID.p12" | pbcopy
```

Paste directly into the `MAC_CSC_LINK` GitHub secret. Clear the clipboard afterward. Add the other five secrets directly in GitHub as well. The Team ID at the end of `MAC_CSC_NAME` must match `APPLE_TEAM_ID`; copy both from the actual identity and membership details. Keep a secure backup of the signing identity outside the repository. Anyone who can change trusted repository workflows may be able to use its signing secrets, so limit repository write access to trusted maintainers.

## 4. Run the notarized build

First run **Actions > Check Mac notarization access > Run workflow** on `main`. This uses Apple's read-only `notarytool history` command to verify the account and app-specific password without building or submitting an application. It does not print the credentials or submission history. The check stops after 60 seconds if Apple does not respond.

Open **Actions > Electron desktop builds and lifecycle > Run workflow** on `main`. Set **platform** to **mac** and **mac_signing** to **developer-id**. This builds both Apple Silicon and Intel versions without rebuilding Windows. The default `adhoc` mode is only for tests and does not make a trusted public Mac release.

The Developer ID path repeats that login check before build downloads. It also rejects missing credential fields, the wrong certificate type or a mismatched Team ID. Certificate import and signing validate the export password and private key later in the build. Apple ID and app-specific password values have surrounding whitespace removed to tolerate a trailing newline from copying; the certificate export password is preserved exactly. The build requires code signing, submits the app to Apple's notary service through electron-builder, and staples the app ticket before packaging. It verifies the actual DMG and ZIP contents, runs real CPU processing and relaunch tests on the DMG-installed copy, then rechecks bundle integrity. Both Mac jobs must pass Gatekeeper assessment and stapled-ticket validation; a valid ad-hoc signature alone cannot pass this release gate.

Apple's service can take time. Signed Mac jobs allow up to 120 minutes, with signing/notarization limited to 90 minutes so the installed-app tests have their own remaining window. A timeout is not an Apple rejection: check which step stopped before retrying. If Apple rejects the app, review the job/notarization output, fix the reported issue and rebuild. Do not publish by skipping a failed signing or notarization check. Windows keeps its existing independent packaging behavior.

### Apple rejects the login with HTTP 401

All six secret names can be present while a saved value is incorrect. Check that the Apple account used to generate the app-specific password is the same email saved as `APPLE_ID`. If unsure, sign into that account at [Apple Account](https://account.apple.com/), generate a new app-specific password for SoundShredder, and update only `APPLE_APP_SPECIFIC_PASSWORD` in GitHub. Use the generated password, not its label or the normal Apple account password. Keep it out of chat and logs. Changing the normal Apple account password revokes existing app-specific passwords; see [Apple's instructions](https://support.apple.com/en-us/102654).

An authentication rejection is not evidence that the Developer ID certificate needs replacing. Re-run **Check Mac notarization access** after correcting the secret, then build again. HTTP 403 instead means the account's team access or required developer agreements need checking. GitHub lists saved names under **Repository secrets**, below the separate **Environment secrets** section; saved values cannot be read back from that list.

## 5. Check the customer installation before publishing

Use a separate Mac with standard Gatekeeper settings. Download the candidate through a normal browser, open the DMG, drag the app into Applications, eject the disk image, and launch from Finder. Complete setup and process a short clip, quit, and reopen from Finder. Repeat on Apple Silicon and Intel. Keep the usual downloaded-from-the-internet confirmation; no Terminal quarantine removal or global security changes should be needed.

Only after those checks pass, publish a new Mac release with its matching Mac guide and checksums. Do not silently replace the previous release's DMGs or claim that the existing preview was notarized. Update the main README download links and remove the launch notice only when the replacement is available.

References: [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) · [Apple's Mac app warnings](https://support.apple.com/en-us/102445).
