# Mac troubleshooting: certificate error during processing

Applies to the **source ZIP**, including Python **3.11.9**. The local page may open normally while processing fails with:

```text
<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
unable to get local issuer certificate (_ssl.c:1006)>
```

The browser interface runs on localhost, but first use downloads audio models over HTTPS: Bandit from Zenodo, or the Bubble FX model from Hugging Face. A missing Python CA certificate setup is one possible cause; the error alone does not identify the exact cause.

## Repair Python's certificate setup

1. In SoundShredder's Terminal window press **Control+C** to stop it. Closing the browser tab alone does not stop the app.
2. For Python **3.11.9**, run this in Terminal:

   ```bash
   open "/Applications/Python 3.11/Install Certificates.command"
   ```

3. Wait for the certificate installer to finish, then reopen **Start SoundShredder.command** and retry processing.

The folder uses `3.11`, not `3.11.9`. For another python.org Python version, use its matching major/minor folder. This step is documented in [Python's official Mac installation guide](https://docs.python.org/3/using/mac.html). If that file is missing, use the repair launcher below or check how Python was installed; do not guess a different Python installation.

## Repair launcher for an existing source installation

Use the accompanying [SoundShredder-Mac-Certificate-Fix.zip](SoundShredder-Mac-Certificate-Fix.zip). On GitHub, open the file and use **Download raw file** to save the ZIP.

1. Stop the existing app with **Control+C**.
2. Extract the repair ZIP in Finder.
3. Copy only **Start SoundShredder - Certificate Fix.command** beside `app.py` in the existing SoundShredder folder.
4. Double-click that new launcher and retry processing.

Keep the existing `.venv` and `data` folders. Do not replace the entire SoundShredder folder. If the ZIP extractor loses executable permissions, type `bash ` in Terminal, drag the new launcher into that window, then press Return.

The launcher uses certifi or pip's bundled CA roots when Python has no default roots. It preserves existing certificate settings, keeps hostname/certificate verification enabled, and changes no system trust settings. Updated source launchers already include the same fallback. The repair ZIP does not reinstall the engine or modify saved sessions.

## If it still fails

Keep the full Terminal error, Python version, processing mode and the download hostname if shown. A VPN, proxy or company HTTPS inspection can require an administrator-provided trusted certificate. Do not disable SSL verification, use `--trusted-host` to bypass it, or remove certificate checks.

The fallback and launcher were tested with simulated missing-root conditions on Windows. Verified HTTPS requests to both model hosts passed there; the affected Mac still needs confirmation.

## Standalone Mac preview

The standalone `.app` uses its own Python and CA bundle. A system Python 3.11 certificate repair may not affect it; do not place the source repair launcher inside the `.app`. Use **Setup details** to collect its diagnostics, then follow the [standalone Mac guide](../../desktop/MAC-README.md).
