# Next release plan: targeted cleanup with text prompts

Development update, September 24, 2026. The owner approved the workflow below. A working source prototype is implemented; listening review, rendered UI checks and packaged-platform validation remain before release. No version number or date is committed. Published installers remain 1.2.2.

## Agreed direction

The next major SoundShredder release will focus on **describing an unwanted sound, previewing its removal, and preserving the rest of the scene**. The owner selected this direction during joint planning.

Retain the familiar Electron/web workspace, local processing, Windows CPU/NVIDIA options and Mac CPU support. Original files, existing separation presets, Bubble FX and saved sessions must remain usable.

## Accepted user experience

**Quick Cleanup · Easy** retains the familiar presets with extra Bubble FX controls under More control. **Target a Sound · Guided** provides the step-by-step workflow below. Strength and one-to-four repeated passes are separate controls. Each pass processes the previous result; stronger settings or more passes can also remove wanted detail.

1. Drop in a video or audio file.
2. Select targeted cleanup and enter a short sound description under **What sound should we remove?** Suggested examples could include water bubbling, background laughter or a ringing phone. These are evaluation candidates, not promises of reliable removal.
3. Optionally drag across the waveform to select an affected interval while watching the footage. Retain numeric time inputs for precise and accessible editing.
4. Choose **Preview cleanup** for a short selection. Explicitly display the processed interval; do not imply that a preview represents the whole clip.
5. Switch between **Original**, **Cleaned** and **Removed** at the same playback position. Adjust reduction strength and listen for wanted sounds in the removed track.
6. Apply the reviewed settings to the intended interval or whole clip, then save the result as a new version. Preserve the original and previous completed versions.
7. Download cleaned audio or the removed sound. Cleaned-video export remains a proposed companion feature, not agreed scope.

The first wording should guide users toward naming the sound, such as "water bubbling". Complex instructions such as "remove one speaker but preserve another" must not be presented as supported behavior without evidence. English descriptions are the proposed initial validation scope; additional languages require separate evaluation.

## Scope decisions

| Decision | Recommendation | Status |
| --- | --- | --- |
| Number of targets per cleanup | One sound at a time, with saved versions | Accepted; implemented |
| Companion features | Visual interval selection and short previews first | Accepted; implemented |
| Cleaned-video export | Separate follow-up; current exports are WAV/ZIP | Outside this prototype |
| Batch processing | Separate follow-up after single-clip cleanup is proven | Outside this prototype |
| Desktop updates | Automatic checks, background download/cancel, explicit restart after idle checks | Implemented in source; full packaged upgrades on Windows and both Mac architectures remain release gates. [Guide](../electron/docs/UPDATES.md) |
| Release number and date | Choose after prototype results and scope agreement | Open |

If multiple targets are selected, define how each is processed, previewed and undone. A single combined text description must not be assumed equivalent to reliably removing every named sound. Any later cleanup applied to a previous result must make that source choice visible.

## Added scope: Mixing Lab

Following the initial targeted-cleanup prototype, the owner approved a dedicated Mixing Lab. It now has a source implementation: reference video and one audio clock, stem peak meters, frame/second/range automation, per-stem prompt cleanup and saved versions, imported replacements and optional Ambience, and mix/stem/video exports. The [Lab guide](MIXING-LAB.md) describes the actual controls and limitations.

On September 25, the owner paused the experimental recursive **Split deeper** workflow. It is removed from the current prototype; the Lab uses its four main channels. Saved experimental split assets/settings are retained locally for recovery. Reintroducing deeper splits is a future scope decision.

This extends the earlier scope table's video-export deferral **for the Lab**: its export can copy the source picture into an MP4 and replace the soundtrack, with WAV delivery retained if the picture format is incompatible. The earlier Target a Sound workspace continues to export WAV/ZIP. Automatic ambience extraction remains research, not a shipped model capability.

## First milestone: prove that custom prompts are useful

Bubble FX uses four precomputed text embeddings. The new local text encoder reuses RoBERTa/CLAP weights already in the AudioSep checkpoint and downloads a verified 1.4 MB tokenizer on first custom use. Fixed presets retain their existing vectors. No separate language-model weights or cloud prompt service are added.

The [official AudioSep implementation](https://github.com/Audio-AGI/AudioSep) accepts natural-language queries. This supports exploring the feature; it does not establish quality for every SoundShredder use case.

Prototype checks and remaining measurements:

- Reproduce existing preset embeddings with the matching checkpoint, tokenizer, projection and normalization before evaluating new descriptions. Preserve the existing preset path for regression comparisons.
- Measure additional download size, CPU/GPU memory, cold startup, cached startup and processing time. Decide whether the text encoder can be downloaded only when custom cleanup is first requested.
- Keep prompt encoding and audio processing local. Validate prompt length and content as data; do not execute user text as shell commands or introduce a cloud dependency.
- Cache embeddings using the exact prompt and encoder/version identity. Reuse successful model downloads and preserve cancel/retry behavior.
- Process short previews with two seconds of surrounding context. Retain the full timeline in exports, changing only the displayed preview interval. Compare the audio samples with a full cleanup of the same interval.
- Present listening-reviewed input, cleaned and removed examples before release. The interface is implemented, but a completed job is not evidence of perceptual quality.

The encoder reproduced all four preset vectors with maximum absolute error below 1.1e-7. Real Windows CPU/CUDA processing and preview/full-interval sample parity passed. See the [verification record](../VERIFICATION.md), [development usage guide](TARGETED-CLEANUP.md) and [AudioShake research notes](AUDIOSHAKE-RESEARCH.md). New dependencies still need native packaged validation on both Mac architectures.

This extends the use of pretrained models. It is not a claim that Bandit or AudioSep has been retrained or improved.

## Listening and verification set

Use permitted local footage and known-component mixtures. The Akira clip is an existing music-separation regression example, not proof of targeted bubble removal. Do not redistribute private clips or complete third-party soundtracks with tests or documentation.

Cover:

- Bubbles and gurgles alongside wanted impacts, dialogue and ambience.
- A described sound that is present, absent, faint or partly obscured.
- Music, speech and effects that overlap in time and resemble the target.
- Multiple phrasings of the same target to identify unstable behavior.
- Short clips, silence, mono/stereo and intervals at the start/end of a file.

Record both target reduction and damage to wanted audio. Known-component mixtures allow quantitative comparisons; real clips need listening review. Keep unchanged references and the exact settings for every result. More aggressive processing or more passes must not be assumed better.

Define the launch quality threshold from this evidence. Do not substitute matching duration, a completed job or an attractive waveform for audible quality.

## Delivery stages and release checks

1. **Prototype and scope review:** evaluate prompts, overhead and listening results; agree which targets and companion features are ready.
2. **Complete the workflow:** implement the agreed prompt, selection, preview and saved-version behavior. Make errors, cancellation and stale previews clear when settings change.
3. **Desktop release candidate:** verify the packaged Windows, Apple Silicon and Intel applications, not only the source server.

Release checks must include:

- Existing presets and completed 1.2.2 sessions remain usable after upgrade.
- Originals are preserved, exports remain in sync, and samples outside a restricted cleanup interval stay unchanged where the selected export format permits exact preservation.
- Removed audio is associated with the correct prompt, interval, strength and version.
- CPU/GPU work leaves the interface usable; cancellation stops owned work and incomplete outputs are not presented as successful.
- Model-download interruption, insufficient disk space, GPU memory failure, app exit/crash, offline restart and disconnected storage have clear recovery behavior.
- Video export, if included, preserves picture quality without re-encoding when the chosen output container supports it. Unsupported combinations receive an explicit alternative; verify audio sync and duration on real exports.
- Clean installation, upgrade, normal close/reopen, uninstall/reinstall and saved-session retention are exercised on the supported desktop platforms.
- Mac signing/notarization continues to pass. Windows signing remains a separate publisher-enrollment and packaging workstream; do not imply it is enabled or guarantee that SmartScreen warnings disappear.
- Dependency advisories are reviewed and relevant fixes validated before publication.
- Installation guides, use-case walkthroughs, screenshots, release assets and checksums match the final shipped behavior.

## Release boundary

The approved source prototype includes Easy/Guided modes, local prompts, waveform intervals, ten-second previews, one-to-four passes and saved versions. Each version owns its source copies; deleting a parent does not break a child, but retained versions use more disk space. A completed full cleanup can explicitly become another step's input; previews cannot. Listening quality, rendered UI review and native installer validation remain release gates. No installer builds, paid enrollment or GitHub release publication are included in this prototype. Current community HTML/PDF and platform guides continue documenting the published 1.2.2 installers until a new release is ready.
