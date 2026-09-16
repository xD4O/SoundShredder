# SoundShredder v1.0.1

SoundShredder now links directly to its GitHub project and can check for new releases from the app.

## What's new

- **GitHub project** link beside the installed version, visible on desktop and mobile.
- **Check for updates** compares your version with the latest published stable release and offers a **Get v…** link when a newer version is available.
- Clear up-to-date, newer-local-version, offline and GitHub-limit messages, with a fallback link to Releases.
- Update checks run only when clicked. They send no audio, filenames, saved-session information or credentials. Recent results are cached to avoid repeated GitHub requests.

All v1.0.0 features remain included: dialogue/music/effects separation, four listening tracks, multi-pass Water bubbles cleanup, Windows/Mac launchers and CPU/NVIDIA GPU support.

## Downloads and setup

- **Windows:** download `SoundShredder.zip`, extract it, install Python 3.12 with **Add Python to PATH**, and run **Start SoundShredder.bat**. CPU and NVIDIA setup launchers are included.
- **Mac:** download `SoundShredder-Mac.zip`, extract it, install Python 3.11 using the macOS universal2 installer, and run **Start SoundShredder.command**. See **START HERE - MAC.txt** for launch troubleshooting.
- Both downloads include the full installation guide. These are Python source packages with setup launchers; dependencies and model weights download on first use. `SHA256SUMS.txt` contains both ZIP checksums.

## Updating from v1.0.0

Finish processing and close SoundShredder. Extract the new ZIP into a new writable folder. To retain saved sessions, copy your old `data` folder into the new folder while the app is closed, then run the new launcher. The model cache is reused. Keep the old folder until you have checked the new installation. Updates are installed manually; the button checks for availability and opens release downloads.

## Verification and limits

129 automated tests passed on Windows with Python 3.12/PyTorch 2.8. The 36 update/API checks also passed with Python 3.11/PyTorch 2.2.2 CPU. Coverage includes numeric version ordering, offline/time-out/rate-limit recovery, rejecting draft or prerelease metadata, fixed project links, cached concurrent checks and explicit same-origin checks. Browser verification exercised live GitHub checks and simulated newer-release/offline responses on desktop and mobile.

Mac uses CPU; actual Mac hardware remains untested. Bubble FX remains experimental, and extra passes can reduce wanted sounds. Compare the original, cleaned and Removed sounds previews. Uploaded media, saved sessions, model weights and local environments are excluded from the release packages.

**Made by cyr4x · Made for Higgsfield Community**

[GitHub](https://github.com/xD4O/SoundShredder) · [X](https://x.com/_cyr4x) · [Higgsfield](https://higgsfield.ai/@cyr4x) · [Instagram](https://www.instagram.com/__cyr4x__/) · [YouTube](https://www.youtube.com/@cyr4xfilms)
