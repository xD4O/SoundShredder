# SoundShredder

A local Python audio tool for cleaning up Seedance clips and other mixed soundtracks. Upload one file, separate **dialogue, music and sound effects**, then choose what stays. Includes a browser interface and a command line tool.

See the [future-update roadmap](ROADMAP.md) for planned installation, first-run setup, and app-update improvements.

## Electron desktop previews (v1.2.0)

The same dark/mint interface now runs in its own desktop window, with bundled Python, automatic engine setup, native menus and Save dialogs. Closing the window quits the app after work finishes; reopening reuses saved sessions and engines. Duplicate launches focus the existing window. An earlier standalone must be quit before using Electron with its shared profile.

- **[Windows Electron](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.0-electron-windows-preview.1)** — Windows 10/11 x64 installer, CPU or NVIDIA. [Windows installation and troubleshooting](electron/docs/WINDOWS.md).
- **[macOS Electron](https://github.com/xD4O/SoundShredder/releases/tag/v1.2.0-electron-macos-preview.1)** — separate Apple Silicon (`arm64`) and Intel (`x64`) DMGs/ZIPs, **macOS 13+**, CPU processing. [macOS installation and troubleshooting](electron/docs/MACOS.md).

These are unsigned previews; macOS builds are not Developer ID signed/notarized. Initial engine/model downloads require internet. Updates are manual through **Help > Check for Electron updates**; the workspace sidebar still checks stable source releases. Each download includes only its matching installation guide. [Electron build instructions and verification](electron/README.md).

## Standalone Windows and Mac previews (v1.1.1)

Standalone previews include Python and a setup screen styled like the main app. Required audio packages install automatically into a private runtime; no manual Python installation or terminal setup is needed. Initial engine/model downloads still require internet. Sessions live outside the application folder.

- **[Windows standalone preview](https://github.com/xD4O/SoundShredder/releases/tag/v1.1.1-windows-preview.1)** - EXE installer for Windows 10/11 x64; CPU or NVIDIA GPU. Allow 4 GiB/14 GiB free for setup, plus models and sessions. [Install and uninstall](desktop/WINDOWS-README.md).
- **[Mac standalone preview](https://github.com/xD4O/SoundShredder/releases/tag/v1.1.1-macos-preview.1)** - separate Apple Silicon and Intel app ZIPs for macOS 12+; CPU only. Allow 3 GiB free plus models/sessions. [Install and uninstall](desktop/MAC-README.md).

Both are **prereleases without publisher signing**. Version 1.1.1 adds native Mac reopening/menu-bar controls and reliable close/relaunch behavior on both platforms. Apple Silicon and Intel CI tests cover setup and repeated launching; consumer Gatekeeper behavior and real Mac inference still need validation. These prereleases are separate from the stable v1.0.3 source downloads below. Setup shows storage location/free space and does not retain duplicate pip downloads. See [build instructions and limitations](desktop/README.md).

**Made by cyr4x · Made for Higgsfield Community.** [X](https://x.com/_cyr4x) · [Higgsfield](https://higgsfield.ai/@cyr4x) · [Instagram](https://www.instagram.com/__cyr4x__/) · [YouTube](https://www.youtube.com/@cyr4xfilms). The interface includes the Higgsfield mark and Space Grotesk typography, bundled locally with the font license; see `static/BRANDING.md` for asset sources.

## Download v1.0.3

[Windows download](https://github.com/xD4O/SoundShredder/releases/download/v1.0.3/SoundShredder.zip) · [Mac download](https://github.com/xD4O/SoundShredder/releases/download/v1.0.3/SoundShredder-Mac.zip) · [Release notes](https://github.com/xD4O/SoundShredder/releases/tag/v1.0.3)

The illustrated Higgsfield Community guide covers setup, cleanup presets, aggressive multi-pass Water bubbles, isolated-track downloads, session management and updates. [Read the updated PDF](output/pdf/SoundShredder-Higgsfield-Community-Guide-2026-09-16.pdf) or [download the self-contained HTML](https://github.com/xD4O/SoundShredder/releases/download/v1.0.3/SoundShredder-Higgsfield-Community-Guide.html). The v1.0.3 source ZIPs include their original guides under `output/`; updated source packaging includes the revised guide and Mac troubleshooting. For standalone installation, use the platform instructions linked above.

Extract the entire ZIP before running the launcher. These are Python source packages with setup launchers, not standalone executables. Python must be installed separately; dependencies and model weights download on first use. Both ZIPs include installation instructions. Release assets also include `SHA256SUMS.txt` for checking download integrity.

## GitHub and updates

The installed version, **GitHub project** link and **Check for updates** live together at the bottom of the left sidebar. On smaller screens, the same card appears at the bottom of the workspace. The project link opens [xD4O/SoundShredder](https://github.com/xD4O/SoundShredder). **Check for updates** compares your installed version with the latest published stable GitHub release. A newer release shows a **Get v…** link to its notes and Windows/Mac downloads. Checks happen only when clicked; no audio, filenames, session information, or credentials are sent. Recent successful results are cached for five minutes, and failed attempts for thirty seconds. Offline or rate-limited checks show a retry message and a Releases link; audio processing continues normally.

Updates are downloaded and installed manually. Finish processing and close SoundShredder, download the matching ZIP, and extract it into a new writable folder. To keep saved sessions, copy the old folder's `data` directory into the new folder while the app is closed. Run the new launcher to set up its environment. Model caches in your home directory are reused. Keep the old folder until you have checked your sessions in the new version.

## Start on Windows

1. Install **Python 3.12** from [python.org](https://www.python.org/downloads/) with **Add Python to PATH** enabled.
2. Double-click **Start SoundShredder.bat**. First launch installs dependencies in this folder's `.venv` and opens [the local app](http://127.0.0.1:7860).
3. Drop in an audio file, choose a preset, and click **Separate audio**.
4. Listen to each track and the cleaned mix. Adjust levels, click **Update mix**, then download a WAV or ZIP containing all tracks.

Keep the launcher window open while using the app. Close it or press Ctrl+C to stop the server; active processing is cancelled on orderly shutdown.

**Remove music** is the default: it keeps dialogue and effects together. Other presets keep only dialogue, keep only effects, remove effects, or remove dialogue. Every layer-separation run saves all three stems; Bubble FX instead saves the cleaned and removed audio. Setting every slider to zero produces a silent file of the same duration.

## Start on Mac

See the Bubble FX instructions below for targeted bubble cleanup. Both download packages include this preset.

Download and extract **SoundShredder-Mac.zip**, then move the entire extracted folder to Documents or another writable location.

1. Install **Python 3.11** with the [macOS universal2 installer](https://www.python.org/downloads/release/python-3119/).
2. Double-click **Start SoundShredder.command**. First launch detects Apple Silicon or Intel, installs the matching dependencies, and opens the same browser interface.
3. Upload a file and separate it using **Auto** or **CPU**. Keep the Terminal window open; press Control+C to stop.

Requires **macOS 12 or newer**. The Mac version uses **CPU**; Apple Metal/MPS acceleration is not implemented. Apple Silicon supports Python 3.10–3.13; Intel supports Python 3.10–3.11. Python 3.11 works for both architectures. Use native Python rather than Rosetta.

If the page opens but processing fails with `CERTIFICATE_VERIFY_FAILED`, stop the app and run Python's certificate installer. For Python 3.11.9: `open "/Applications/Python 3.11/Install Certificates.command"`, then reopen the launcher. See [Python's official Mac setup guide](https://docs.python.org/3/using/mac.html). The updated launcher automatically uses certifi or pip's bundled CA roots only when Python's default store is empty; it keeps explicit certificate settings and TLS verification enabled. First processing may need HTTPS access to Zenodo (Bandit) or Hugging Face (Bubble FX), even though the interface itself is on localhost.

See [Mac certificate troubleshooting](support/mac/README.md) for the complete steps and the included repair launcher ZIP for older source installations. The community HTML/PDF guide also has a dedicated Mac troubleshooting page.

Intel setup pins [PyTorch 2.2.2](https://pypi.org/project/torch/2.2.2/) and NumPy 1.26.4; Apple Silicon uses [PyTorch 2.8.0](https://pypi.org/project/torch/2.8.0/). Intel also needs Python 3.11 or older because the model's disabled compiler calls encounter [PyTorch 2.2's Python 3.12 guard](https://github.com/pytorch/pytorch/blob/v2.2.2/torch/__init__.py#L1638-L1640). The ZIP includes **START HERE - MAC.txt** with first-launch, permission, certificate, and recovery instructions. Python is installed separately; model weights download on first separation. No Homebrew or separate FFmpeg installation is needed.

If Finder will not open the launcher, open Terminal, type `bash `, drag **Start SoundShredder.command** into Terminal, and press Return.

## CPU and GPU

- **Auto:** NVIDIA CUDA if available; CPU otherwise.
- **NVIDIA GPU:** faster, with an up-to-date NVIDIA driver. The provided installer uses PyTorch 2.8 with CUDA 12.8, including support for RTX 50-series cards. Its first download is about 3.2 GB. A separate CUDA Toolkit installation is not needed.
- **CPU:** works without a GPU. It can take several minutes even for short clips. Use **Setup CPU.bat** to install a smaller CPU-only runtime.
- **Setup NVIDIA GPU.bat** switches an existing CPU installation to CUDA. A CUDA installation can still process on CPU using the app selector.
- **Use CPU if GPU memory runs out** retries a failed GPU run on CPU. Uncheck it to surface the GPU error instead. Unavailable explicitly selected GPUs give an error rather than silently changing devices.
- AMD GPU acceleration and Apple Metal are not implemented; use CPU on those machines.

## Bubble FX preset (experimental)

1. Upload your audio or video and choose **Bubble FX · BETA**.
2. Choose **Water bubbles**, **Bubbling & popping**, **Liquid gurgle**, or **Cartoon boing**, matching the unwanted sound.
3. Enable **Limit cleanup to a time range** and enter seconds (for example, **7** to **11**). Leave it unchecked to process the whole clip.
4. Start at **85% reduction**, then click **Clean up bubbles**.
5. Compare the original and cleaned previews. Listen to **Removed sounds**: if it contains effects you want, lower reduction or narrow the range. With a single pass, **Update mix** applies either change without running the model again.

For stubborn **Water bubbles**, enable **Aggressive multi-pass**. Start with **2 passes**; **3** and **4** are stronger options. Each pass runs the model again on the previous pass's cleaned audio and applies your reduction level inside the selected range. One pass remains the default. Extra passes take longer, especially on CPU, and may remove more wanted effects. The **Removed sounds** track contains the combined removal from all passes; compare it with the original before keeping the result.

Changing the number of passes, the sound type, or the strength/range of a multi-pass cleanup needs fresh inference. Click **Clean up again** to reuse the saved original upload in a new session; the previous session and exports are retained. Reopening a session restores its pass count. Multi-pass works with Auto, NVIDIA GPU, and CPU (including Mac), using the existing model and dependencies. If a GPU runs out of memory and CPU fallback is enabled, the failed pass continues on CPU. Restart the updated app to enable the new controls.

This preset uses the pretrained [AudioSep sound separator](https://github.com/Audio-AGI/AudioSep), with four fixed text prompts. It estimates the selected sound and subtracts a shared stereo spectral mask from the original mix. It keeps music, dialogue, and other content in the original; it does not rebuild those parts from Bandit stems. AudioSep is a separate model, not a fine-tuned Bandit v2.

**It cannot promise to remove only bubbles with no collateral effects.** Similar pops, liquid noises, or other overlapping effects can be caught too. This is an experimental preset, not a trained detector for a specific Seedance artifact. A selected time range limits damage: every decoded sample outside that range is copied exactly into the cleaned **32-bit float WAV**, with short fades contained inside the selection. Timing, sample rate, and stereo layout are preserved. No global normalization is applied. Float WAV can retain peaks above full scale; lower playback gain in your editor if necessary.

Bubble exports include **cleaned audio**, **removed sound**, and a report, rather than three dialogue/music/effects stems. First use downloads a SHA-256-verified **1.2 GB** model to `~/.cache/soundshredder/audiosep/`; later runs work offline. No account or API key is required. The preset uses the existing Python dependencies on Windows, Mac, and Linux, with NVIDIA CUDA or CPU. Mac uses CPU; actual Mac hardware testing is still outstanding.

## Listen to each layer

Completed sessions have a dedicated listening panel with **four separate track strips: Dialogue, Music, Sound effects, and Removed sounds**. Each has its own waveform, playback, seeking, volume/mute control, and WAV download. Playing a track pauses the others. Enable **Keep playback position when switching tracks** to compare the same moment; disable it to keep separate playback positions. Preview volume and mute do not alter your exported mix.

For normal layer separation, all four tracks are prepared automatically. **Removed sounds** contains the portions excluded by your dialogue/music/effects sliders at the last export (including partial reductions). It does not include the model's reconstruction residual or differences caused by output headroom. The layer-separation ZIP now includes this track. If all layers are kept at 100%, Removed sounds is silent.

For Bubble FX, Removed sounds is the estimated bubble sound taken out of your mix. Click **Prepare isolated tracks** once to also hear dialogue, music and effects from the **original audio, before bubble cleanup**. This optional Bandit pass uses your session's CPU/GPU choice and fallback setting; CPU can take longer, and first use may download Bandit's separate weights. Your existing cleaned mix, bubble settings and exports stay unchanged. Preparation can be cancelled or retried independently. The bubble ZIP still contains cleaned audio, removed audio and its report; download the additional tracks individually from their strips.

Changing mix levels, bubble strength, or timing marks Removed sounds as the previous export until you click **Update mix**, or **Clean up again** for multi-pass changes. Older sessions can use **Prepare isolated tracks** to fill in missing tracks; existing layer stems are reused when available. Session downloads remain available while you listen. Restart the updated app if an older running server does not offer track preparation.

First separation downloads the official Bandit v2 weights (~426 MB) into `~/.cache/bandit-infer`. Subsequent runs work offline. No uploaded audio is sent to a cloud service.

## Formats and files

WAV, MP3, FLAC, M4A, AAC, OGG, Opus, AIFF, WMA and common video containers are supported. Videos yield audio outputs; this tool does not replace the audio in the source video. FFmpeg is bundled through `imageio-ffmpeg`.

Limits: **500 MB, 10 minutes, mono or stereo, 8–192 kHz**. Surround input is rejected instead of silently downmixed. The decoded source's sample rate, frame count and channel layout are restored after inference. Compressed codecs can contain padding, so “source length” means the decoded audio length.

Downloads are 24-bit PCM WAV for layer separation and 32-bit float WAV for Bubble FX. The local `data/<session-id>/` folder contains the uploaded copy, full-precision stems, exports, processing report, and a worker log. Original files are never overwritten. Sessions survive a restart; unfinished sessions are marked stopped. **Delete this session** removes its local uploaded copy and generated outputs. Files remain on disk until you delete them; each updated mix adds a new WAV/ZIP revision. Move downloads elsewhere before deleting a session.

The web server binds to `127.0.0.1` only and does not provide public hosting or authentication. Run one server per data directory. Change the location with `SOUNDSHREDDER_DATA` if needed.

## What is improved around Bandit v2

This uses the existing pretrained weights; it does **not** claim to retrain or improve the underlying model's source recognition.

- Bounded 20-second inference blocks, 2-second overlapping crossfades, and the model's native internal 8-second / 1-second overlap handler reduce memory growth and smooth block boundaries. Blocked inference may differ slightly from processing the entire clip in one call.
- The optimized inference runner skips padded windows that cannot contribute to any exported sample, and accumulates predictions directly into the output. It retains upstream padding and window weighting. Deterministic padding/fold tests and a real-weight parity check guard this optimization; it changes compute scheduling, not the model's weights.
- Explicit 48 kHz resampling for the model, followed by restoration of source rate and exact frame count.
- Mono/stereo preservation and one shared output gain across all stems, leaving headroom for any mix with track levels from 0–100%. No independent normalization that unexpectedly boosts noise or changes relative levels.
- Isolated cancellable processing, real inference progress, serialized GPU jobs, and optional CPU retry after GPU out-of-memory errors.
- Full-precision stems let you remix repeatedly without rerunning the model or accumulating 24-bit quantization.
- A report verifies source SHA-256, frames, sample rate, channels and output peak. Residual RMS and relative stem levels aid inspection; they do **not** measure audible separation quality. The residual is not added back, since it may contain the sound you removed.

### Real limitations and possible next improvements

The model can confuse breaths, singing, rhythmic impacts and background music. Effects includes ambience. Bandit cannot selectively remove one unwanted whoosh while preserving every other effect in the same stem. Bubble FX uses a separate model for targeted bubble reduction, with the limitations described above. Always audition important dialogue and quiet effects. Returning three tracks with matching lengths proves routing/timing, not perceptual quality.

Bubble FX now provides timed regions and a second, text-conditioned model with fixed bubble prompts. Useful further work would be user-supplied reference sounds, arbitrary text queries, and listening-based comparisons. A genuinely better Bandit model would require a licensed, labelled test/training set of synthetic video audio with known dialogue/music/effects stems, followed by fine-tuning and blind listening tests. Evaluate bleed, missing speech, effects preservation, transient artifacts and multilingual speech independently before claiming improvement. Mixture consistency alone can restore the very noise you wanted removed.

## Manual installation / other operating systems

Use Python 3.10–3.13, or 3.10–3.11 on Intel Macs. Python 3.12 is recommended for Windows/Linux; Python 3.11 works on both Mac architectures. Platform-specific setup is provided for Windows, Linux and macOS; CUDA requires a supported NVIDIA environment. See `VERIFICATION.md` for actual test coverage.

```shell
python setup_runtime.py --device cpu
# Windows:
.venv\Scripts\python.exe app.py
# macOS / Linux:
.venv/bin/python app.py
```

For NVIDIA use `python setup_runtime.py --device cuda`. Optional flags: `app.py --no-browser --port 7860`.

```shell
python -m soundshredder.cli "clip.wav" --device auto --keep speech effects
python -m soundshredder.cli "clip.wav" --device cpu --keep speech --output exports
python -m soundshredder.cli "clip.mp4" --device cuda --keep effects --no-cpu-fallback
python -m soundshredder.cli "clip.mp4" --bubble water --reduction 0.85 --start 7 --end 11 --device auto
python -m soundshredder.cli "clip.mp4" --bubble water --passes 3 --reduction 0.85 --start 7 --end 11 --device cpu
```

Run CLI commands with the `.venv` Python or activate that environment first. Each run creates a unique session folder under the output directory, including its inputs and reports.

## Development and verification

```shell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
```

Tests use small deterministic fixtures for routing, resampling, mix levels, silence, API errors, file safety and the inference block crossfade. They do not substitute for model listening tests. Hardware smoke results, when present, are documented in `VERIFICATION.md`.

## Model attribution

- [AudioSep](https://github.com/Audio-AGI/AudioSep) by Xubo Liu and collaborators powers the experimental Bubble FX preset. Adapted inference code, fixed query vectors, the upstream MIT license, and provenance are in `soundshredder/_audiosep/`. The separately downloaded checkpoint is pinned and hash-verified; no model weights are included in the release ZIPs.

- [Bandit v2 research implementation](https://github.com/kwatcharasupat/bandit-v2) by Karn Watcharasupat and collaborators; [paper](https://arxiv.org/abs/2407.07275).
- [bandit-infer](https://github.com/openmirlab/bandit-infer) packages the inference graph and verifies the official checkpoint. This app pins its source revision for reproducibility.
- Upstream code is Apache-2.0. The official v2 checkpoint is distributed under **CC BY-SA 4.0**, as documented by the adapter and its [Zenodo source](https://zenodo.org/records/12701995). The checkpoint is downloaded separately, not bundled here.

## Preview your footage

Video uploads now have a **Your footage, in sync** panel. Toggle **Show video preview** to show or hide it; your browser remembers the preference. Choose **Original**, **Cleaned mix**, **Dialogue**, **Music**, **Sound effects**, or **Removed sounds** in **Listen to** once that track is available. Play, pause, or scrub under the video; using any existing audio player also makes the footage follow that track. The footage stays muted so you hear only the chosen audio. Hiding it leaves audio playback available.

Saved video sessions can reopen the original footage without uploading it again. Browser codec support varies; H.264 MP4 is the most compatible option. A clip that cannot preview can still be processed for audio. Audio-only uploads hide the video panel. Preview does not change your mix or export a video: downloads remain WAV/ZIP files. For containers with audio/video start offsets, check synchronization against the original in your editor.
