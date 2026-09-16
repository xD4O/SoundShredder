# Future updates

These are planned improvements, not features available in the current release. No release date is committed.

## Easier installation and updates

Priority: Windows first, then separate Apple Silicon and Intel Mac packages.

- Bundle Python in a Windows installer and Mac app bundles so users do not need to install Python or use a terminal.
- Add a first-run setup wizard that detects hardware and guides CPU or NVIDIA GPU setup, with download sizes, progress, retry, and clear errors.
- Download models only when their features are first used: Bandit for track separation and AudioSep for Bubble FX. Include progress and retry controls.
- Keep the installer manageable by downloading large AI dependencies and models during guided setup.
- Enforce one running instance: launching again opens the existing app instead of starting another server.
- Store sessions, settings, and models outside the installation folder so upgrades preserve user data.
- Add guided app updates that install after active processing finishes.
- Include a troubleshooting screen with setup status and copyable diagnostics.
- Preserve the existing local-processing workflow and familiar interface.

As an interim improvement, simplify the existing launcher with requirement checks, guided dependency installation, visible download progress, and actionable retry instructions.
