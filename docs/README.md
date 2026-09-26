# SoundShredder guides

Guides for **1.3.0**, refreshed September 26, 2026.

- [Install on Windows](../electron/docs/WINDOWS.md) and [understand unsigned-download warnings](WINDOWS-DOWNLOADS.md).
- [Install on Mac](../electron/docs/MACOS.md): current Apple Silicon and Intel builds are signed and notarized.
- [Run the source web app](../README.md#run-the-web-app-locally): Windows and Mac setup, including required Python versions.
- [Akira worked example](AKIRA-EXAMPLE.md): remove music, compare against footage, audition tracks and export.
- [Community guide PDF](../output/pdf/SoundShredder-Higgsfield-Community-Guide.pdf) and [downloadable HTML](https://raw.githubusercontent.com/xD4O/SoundShredder/main/output/html/SoundShredder-Higgsfield-Community-Guide.html).
- [Presets, bubbles, devices, formats and CLI reference](REFERENCE.md).
- [Mac source SSL troubleshooting](../support/mac/README.md).
- [Verification record](../VERIFICATION.md) and [future work](../ROADMAP.md).

Use the [official GitHub release](https://github.com/xD4O/SoundShredder/releases/latest) for installers. Windows publisher signing is pending. Electron checks automatically and lets you choose when to download and restart. Browser/source updates remain manual; normal Quit never installs an update.

The [desktop updater](../electron/docs/UPDATES.md) provides automatic checks, cancellable downloads and an explicit restart choice. Users coming from 1.2.2 need one manual upgrade to 1.3.0 first.

The `desktop/` guides describe the earlier browser-based standalones. Older versioned PDFs and release entries are historical snapshots, not instructions for the current Electron download. The unversioned PDF and HTML links above are the maintained community guide.

## Maintaining the illustrated guide

Read the [targeted-cleanup guide](TARGETED-CLEANUP.md), [Mixing Lab guide](MIXING-LAB.md) and [desktop update guide](../electron/docs/UPDATES.md) for the new workflows. The [accepted plan](NEXT-RELEASE-PLAN.md) and [AudioShake research](AUDIOSHAKE-RESEARCH.md) retain design context. The community guide includes these workflows alongside Windows/Mac installation and the Akira example.

Edit `scripts/community_guide_content.py`, then run `python scripts/build_community_guide.py` with ReportLab and Pillow installed. The builder uses the committed screenshots in `docs/images`, the bundled Space Grotesk font, and Windows Segoe UI fonts. On another system, point `SOUNDSHREDDER_DOC_FONT_DIR` to a licensed copy of `segoeui.ttf` and `segoeuib.ttf`. It produces the maintained PDF and self-contained HTML and fails if PDF content crosses its footer boundary. Render and inspect every page after changing layout or text.
