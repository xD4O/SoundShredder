# SoundShredder v1.0.0

The first community release of SoundShredder: a local audio cleanup workspace made by **cyr4x** for the **Higgsfield Community**.

Upload one audio or video file, separate dialogue, music and sound effects, then choose what stays. Your audio is processed on your computer.

## Downloads and installation

- **Windows:** download `SoundShredder.zip`, extract the entire folder, install Python 3.12 with **Add Python to PATH**, and double-click **Start SoundShredder.bat**. Choose **Setup CPU.bat** for CPU-only setup or **Setup NVIDIA GPU.bat** for NVIDIA acceleration.
- **Mac:** download `SoundShredder-Mac.zip`, extract it to a writable folder, install Python 3.11 from the macOS universal2 installer, and double-click **Start SoundShredder.command**. If Finder will not launch it, run `bash ` followed by the dragged launcher path in Terminal. See **START HERE - MAC.txt** for the full guide.
- Keep the launcher window open while using the browser interface. First use downloads dependencies and model weights; an account or API key is not required.
- These are source packages with setup launchers. Python is installed separately. `SHA256SUMS.txt` contains the checksums for both downloads.

## Included

- Bandit v2 separation into dialogue, music and sound effects, with presets, level controls and WAV/ZIP exports.
- Four separate listening tracks: Dialogue, Music, Sound effects and Removed sounds, with waveforms, playback controls and downloads.
- Experimental **Bubble FX** cleanup with four sound targets, reduction strength and optional time ranges.
- **Water bubbles → Aggressive multi-pass:** 2, 3 or 4 passes, each analyzing the previous cleaned result. Start with 2 passes and check the combined Removed sounds track.
- Saved sessions and **Clean up again** to rerun the original upload without another upload. Earlier sessions and exports are retained.
- Auto, NVIDIA GPU or CPU processing, plus optional CPU fallback when GPU memory runs out. Mac uses CPU.
- A responsive dark interface, cyr4x social links and Higgsfield Community branding.
- A Windows fix for temporary access-denied errors while updating progress files.

## Tested and known limits

106 automated tests passed in both tested Windows Python/PyTorch environments. Real GPU and CPU runs, saved-source reruns, audio previews and export timing were checked. The Mac launcher and dependency handling are included, but actual Mac hardware has not been tested; Apple Metal/MPS acceleration is not implemented.

AI separation can leave bleed or reduce wanted sounds. Bubble FX is experimental, and additional passes can remove overlapping effects. Compare the original, cleaned audio and Removed sounds before using a result. Samples outside a selected bubble-cleanup interval are preserved exactly in the float WAV. Numerical checks do not establish perceptual quality inside that interval.

Model weights, uploaded clips, saved sessions and local environments are excluded from these packages. Bundled AudioSep code and Space Grotesk include their upstream licenses; model attribution and branding sources are documented in the included README and notices.

**Made by cyr4x · Made for Higgsfield Community**

[X](https://x.com/_cyr4x) · [Higgsfield](https://higgsfield.ai/@cyr4x) · [Instagram](https://www.instagram.com/__cyr4x__/) · [YouTube](https://www.youtube.com/@cyr4xfilms)
