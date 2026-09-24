# Target a Sound: development guide

**Unreleased source prototype.** These controls are not in the published 1.2.2 installers. See the [main guide](../README.md) for current installation. Developers running this branch should rerun their platform's normal setup to install the updated engine dependencies.

## Choose a mode

**Quick Cleanup · Easy** keeps the familiar dialogue, music, effects and Bubble FX presets. Bubble FX's sound type, strength and aggressive passes are under **More control**.

Choose **Target a Sound · Guided** for a particular unwanted sound. For example, a generation may have bubbling underneath wanted movement and impacts. Describe the bubbling, preview its removal and listen for changes to the other effects.

## A first cleanup

1. Drop an MP4/video or audio file. The app prepares its waveform without separating every layer. Enable the footage monitor to see the scene while listening.
2. Drag across the source waveform or enter start/end times. For the original bubble example, try **7–11 seconds**. Clear the interval option to target the whole clip.
3. Enter a short description such as **Water bubbling**. Name one sound in English, up to 200 characters. This is sound conditioning, not a general editing assistant or individual-speaker selector.
4. Start with **one pass** and choose **Preview cleanup**. It processes at most ten seconds from your selection's start. The displayed interval shows what was processed.
5. Compare input, cleaned audio and **Removed sounds**. Listening controls can keep playback position when switching. If wanted effects appear in Removed sounds, reduce strength, narrow the interval or change the description.
6. Choose **Save cleanup version** to process the full intended interval. Download the cleaned WAV, removed WAV or ZIP with its report.

Example descriptions are starting points to try, not guarantees of clean isolation from every recording.

## Strength and repeated passes

**Strength** controls how much of the estimated sound is subtracted each time. **Passes** controls how many times the remaining audio is analyzed and cleaned, from one to four.

For stubborn bubbles, compare two passes against one before trying three or four. More aggressive settings may reduce residual bubbling, but can also thin ambience or other wanted sounds. Audition Removed sounds after each change. Changed settings require a new preview or saved version; previous downloads are hidden until the displayed settings match a completed result.

## Versions and a second target

Every attempt is separate. Open an entry under **Your cleanup versions** to return to its audio and settings. Input defaults to the original upload, so another description does not silently stack changes.

To build on a result, open a completed full cleanup, choose **Current cleaned version** as the next input, then describe the next sound. Previews cannot become the input to a later step. For chained steps, the input player and isolated layers refer to that step's input audio; Removed sounds is what that step subtracts. The report records the parent and source choice.

Each version owns its source copies. Deleting an earlier session does not break a later version, but keeping many versions uses more disk space. **New session** clears the workspace for another file. **Delete this session** removes that saved version from disk; download results you want to keep first.

## Processing and exports

Descriptions and footage stay on your computer. First custom use downloads a verified tokenizer of about 1.4 MB, plus the existing AudioSep model if uncached. Initial setup/downloads need internet access; cached descriptions and models are reused locally. CPU works without an NVIDIA card. Auto can use CUDA on supported Windows machines; optional CPU fallback retries a pass if GPU memory fills.

Targeted exports are full-length 32-bit float WAVs. A preview changes only its displayed interval; it is not a fully processed whole-clip result. Samples outside a restricted interval are verified unchanged against decoded input. The original upload is retained. This feature does not export a new video file; place the cleaned WAV under the footage in your editor.

Cancel stops the owned processing job. Retry from the saved source without uploading again. After audio is saved, a brief **Finishing up** state waits for the engine to exit before enabling another cleanup.

The [development plan](NEXT-RELEASE-PLAN.md) lists listening, visual and packaged-platform checks still needed before release.
