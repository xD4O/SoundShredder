# SoundShredder v1.0.2

The installed version, GitHub project link and update checker now live together in a uniform card at the bottom of the left sidebar. This release also includes the illustrated Higgsfield Community guide in HTML and PDF.

## What's new

- **A cleaner workspace:** matching GitHub and update rows, a version badge, update status and local-processing information in one sidebar card.
- **Controls stay accessible on small screens:** the same card moves to the bottom of the workspace when the sidebar collapses, retaining the current update result.
- **Nine-page community guide:** real interface screenshots covering Windows/Mac setup, CPU/NVIDIA GPU selection, MP4/MP3 imports, cleanup presets, aggressive multi-pass Water bubbles, isolated tracks, downloads and session management.
- **Guides included in both app ZIPs**, with separate HTML and PDF downloads below. The HTML embeds its screenshots and font for sharing as one file.

All existing audio features remain included. This release changes the interface and documentation; it does not change the separation models.

## Downloads and setup

- **Windows:** download [SoundShredder.zip](https://github.com/xD4O/SoundShredder/releases/download/v1.0.2/SoundShredder.zip), extract it, install Python 3.12 with **Add Python to PATH**, and run **Start SoundShredder.bat**. CPU and NVIDIA setup launchers are included.
- **Mac:** download [SoundShredder-Mac.zip](https://github.com/xD4O/SoundShredder/releases/download/v1.0.2/SoundShredder-Mac.zip), extract it, install Python 3.11 using the macOS universal2 installer, and run **Start SoundShredder.command**. See **START HERE - MAC.txt** for launch troubleshooting.
- **Community guide:** [PDF](https://github.com/xD4O/SoundShredder/releases/download/v1.0.2/SoundShredder-Higgsfield-Community-Guide.pdf) or [HTML](https://github.com/xD4O/SoundShredder/releases/download/v1.0.2/SoundShredder-Higgsfield-Community-Guide.html). Open the downloaded HTML in your browser. Both formats are included under `output/` in each ZIP.
- These are Python source packages with setup launchers. Python is installed separately; dependencies and model weights download on first use. `SHA256SUMS.txt` covers both app ZIPs and both standalone guides.

## Updating from an earlier version

Finish processing and close SoundShredder. Extract the new ZIP into a new writable folder. To retain saved sessions, copy your old `data` folder into the new folder while the app is closed, then run the new launcher. The model cache is reused. Keep the old folder until you have checked the new installation. Updates are installed manually; the button checks for availability and opens release downloads.

## Verification and limits

All **129 automated tests passed** on Windows, covering audio processing, API behavior, update checks, installation helpers and release packaging. Ruff and JavaScript syntax checks passed. The sidebar was checked at desktop and phone widths, including a live GitHub update check and preserving its result while resizing. Both guide formats were visually checked, including all nine PDF pages.

Mac uses CPU; actual Mac hardware remains untested. Bubble FX remains experimental, and extra passes can reduce wanted sounds. Compare the original, cleaned and Removed sounds previews. Uploaded media, saved sessions, model weights and local environments are excluded from the release packages.

**Made by cyr4x · Made for Higgsfield Community**

[GitHub](https://github.com/xD4O/SoundShredder) · [X](https://x.com/_cyr4x) · [Higgsfield](https://higgsfield.ai/@cyr4x) · [Instagram](https://www.instagram.com/__cyr4x__/) · [YouTube](https://www.youtube.com/@cyr4xfilms)
