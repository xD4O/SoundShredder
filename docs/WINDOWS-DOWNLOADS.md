# Windows download warnings

Applies to the **unsigned SoundShredder 1.2.2 Windows Electron installer**. Updated September 22, 2026.

## Get the official download

Use **[github.com/xD4O/SoundShredder/releases/latest](https://github.com/xD4O/SoundShredder/releases/latest)**. This is the project's official distribution page. Choose the Windows EXE from its Assets list; avoid reuploaded installers or similarly named repositories.

The current file is [SoundShredder-Electron-1.2.2-Windows-x64-Setup.exe](https://github.com/xD4O/SoundShredder/releases/download/v1.2.2/SoundShredder-Electron-1.2.2-Windows-x64-Setup.exe). Windows publisher signing is planned and has **not** been completed. Mac Developer ID signing and notarization do not sign this Windows EXE.

## Why Edge or Windows shows a warning

Edge may say **“isn't commonly downloaded”**. Windows may show **“Windows protected your PC”** or an unknown publisher. SmartScreen considers a file's download reputation and its publisher's signature; an unsigned or unfamiliar release can trigger these messages. This particular reputation warning does not report a specific malware detection. Signing can help future releases build publisher reputation, but does not guarantee that every warning immediately disappears. [Microsoft's explanation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)

The official release has passed installation, reinstallation, uninstallation, CPU processing/export and close/reopen tests. These are functional checks, not a security audit or a guarantee that software is risk-free. Downloading from GitHub alone does not establish safety; confirm the exact project and release, and keep your security protection enabled.

## Check that your download matches the release

1. Download the EXE and [SHA256SUMS.txt](https://github.com/xD4O/SoundShredder/releases/download/v1.2.2/SHA256SUMS.txt) from the **same release**.
2. In PowerShell, run the following, replacing the path if you saved the EXE elsewhere:

   ```powershell
   Get-FileHash -Algorithm SHA256 -LiteralPath "$env:USERPROFILE\Downloads\SoundShredder-Electron-1.2.2-Windows-x64-Setup.exe"
   ```

3. Compare the entire Hash value with the checksum line for that exact filename. Letter case does not matter. A match verifies that the bytes match the published checksum; it is not a malware scan or a publisher certificate.
4. Keep Microsoft Defender or your usual security software enabled. If the hash differs, do not run the file; download it again from the official release. If security software reports a named threat, stop and report that exact detection. Treat it separately from an uncommon-download message.

If you have verified the source and checksum and decide to proceed with a reputation warning, Edge may offer **… > Keep > Show more > Keep anyway**. A Windows SmartScreen prompt may offer **More info > Run anyway**. Wording and availability vary. These choices apply to that download; do not disable SmartScreen, antivirus or Smart App Control globally. If Windows or your organization blocks the file without an override, use the [source web-app instructions](https://github.com/xD4O/SoundShredder#run-the-web-app-locally) where permitted, or contact your administrator.

## Get help

[Report an issue](https://github.com/xD4O/SoundShredder/issues) with the release filename, Windows version and exact warning or detection. Avoid sending private media or credentials. See the [Windows installation guide](https://github.com/xD4O/SoundShredder/blob/main/electron/docs/WINDOWS.md) and [signing roadmap](https://github.com/xD4O/SoundShredder/blob/main/ROADMAP.md#next-priority-windows-code-signing).
