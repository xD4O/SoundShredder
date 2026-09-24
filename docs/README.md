# SoundShredder guides

Current release: **1.2.2**. Development documentation refreshed September 24, 2026.

- [Install on Windows](../electron/docs/WINDOWS.md) and [understand unsigned-download warnings](WINDOWS-DOWNLOADS.md).
- [Install on Mac](../electron/docs/MACOS.md): current Apple Silicon and Intel builds are signed and notarized.
- [Run the source web app](../README.md#run-the-web-app-locally): Windows and Mac setup, including required Python versions.
- [Akira worked example](AKIRA-EXAMPLE.md): remove music, compare against footage, audition tracks and export.
- [Community guide PDF](../output/pdf/SoundShredder-Higgsfield-Community-Guide.pdf) and [downloadable HTML](https://raw.githubusercontent.com/xD4O/SoundShredder/main/output/html/SoundShredder-Higgsfield-Community-Guide.html).
- [Presets, bubbles, devices, formats and CLI reference](REFERENCE.md).
- [Mac source SSL troubleshooting](../support/mac/README.md).
- [Verification record](../VERIFICATION.md) and [future work](../ROADMAP.md).

Use the [official GitHub release](https://github.com/xD4O/SoundShredder/releases/latest) for installers. Windows publisher signing is pending. Updates are manual; the app does not silently install updates.

The `desktop/` guides describe the earlier browser-based standalones. Older versioned PDFs and release entries are historical snapshots, not instructions for the current Electron download. The unversioned PDF and HTML links above are the maintained community guide.

## Maintaining the illustrated guide

The next release is tracked separately in the [targeted-cleanup plan](NEXT-RELEASE-PLAN.md), [prototype guide](TARGETED-CLEANUP.md), [Mixing Lab guide](MIXING-LAB.md) and [AudioShake research](AUDIOSHAKE-RESEARCH.md). These features are not yet in the current installers or illustrated release guide.

Edit `scripts/community_guide_content.py`, then run `python scripts/build_community_guide.py` with ReportLab and Pillow installed. The builder uses the committed screenshots in `docs/images`, the bundled Space Grotesk font, and Windows Segoe UI fonts. On another system, point `SOUNDSHREDDER_DOC_FONT_DIR` to a licensed copy of `segoeui.ttf` and `segoeuib.ttf`. It produces the maintained PDF and self-contained HTML and fails if PDF content crosses its footer boundary. Render and inspect every page after changing layout or text.
