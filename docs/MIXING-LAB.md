# Mixing Lab — development guide

The Mixing Lab is an **unreleased source feature**, approved during planning for the next major SoundShredder release. Published 1.2.2 installers do not contain it. It uses the existing local Python server and the same interface inside Electron; new installers still need platform testing before release.

## Open a scene

Choose **Mixing Lab** in the left panel. Upload a video/audio file, or open a completed session. The source upload is preserved. Uploading prepares the file; it does not start stem extraction automatically.

Use the **Stem Extraction** area directly above the reference video and mixer. Choose Auto, CPU or NVIDIA GPU, then click **Extract stems**. Follow progress or cancel from that area. Dialogue, Music and Effects each show their availability; Play becomes available when at least one track is ready. If extraction stops, **Retry extraction** is available there too. You can also follow **Or import your own stems** to bring in tracks from an editor.

If stems are already available, the Lab reuses copies of them and the area shows **Your stems are ready**. Partial sessions offer **Extract missing stems**, preserving existing tracks. Extraction uses Bandit; ordinary fader changes do not run a model again.

The reference video shares a playhead with all active stems. Use Play, the scrubber or the waveform lanes to navigate. The Video checkbox hides the picture when you want more focus on audio. For audio-only sources, the transport and channels work without a picture.

The Lab starts from the session's saved **input** audio. For a Bubble FX or Target a Sound session, that means the input before that session's cleanup, which is labeled in the Lab. To mix its already-cleaned result instead, export the cleaned audio and open it as a new source or import it into the appropriate channel.

**Close session** returns to the Lab's start screen and removes that session from the active sidebar list. You can also use the **×** beside a session to close it without opening it first. Your source, extracted tracks, edits and exports are retained. Expand **Closed sessions** in the sidebar and select a saved mix to reopen it; it returns to the active list. Closed sessions stay closed after refreshing or restarting the app.

Closing a session view stops its playback and leaves the upload control ready for another file. It does not cancel background processing; use **Cancel extraction** or **Cancel processing** first if you want to stop a job. The engine still processes one job at a time. To delete local session data, use the separate session-delete control in Audio separator.

## Change one moment

Select the scope before moving a fader:

| Scope | What changes |
| --- | --- |
| This second | The second containing the playhead; for example, 7.3 seconds selects 7–8 seconds. |
| This frame | One frame interval based on the video's nominal frame rate. Disabled when frame rate is unavailable. |
| Selected range | The numeric From/To interval, or a range dragged across a waveform lane. |

For example, lower Music to **−9 dB** while the playhead is at 7.3 seconds in **This second** mode. The music returns to its previous level at 8 seconds. Another edit elsewhere remains intact. A new edit replaces only the overlapping portion of older edits.

**0 dB is unchanged gain**, not silence. **M** mutes only the selected interval. **Reset interval** restores 0 dB in that interval. **Undo edit** restores the previous track settings during the current visit. Edits save automatically; a revision indicator confirms saving. Reopening restores saved edits, but the temporary undo history does not survive a page reload.

Fader edits pause playback so you can work at a deliberate position. Playback reads the saved automation, and each fader follows the playhead. Five-millisecond fades inside edit boundaries soften clicks; very short edits use shorter fades. Variable-frame-rate footage may not align with every nominal frame step—use a time range when exact frame correspondence is uncertain.

## Read the channels

| Channel | Source |
| --- | --- |
| Dialogue | Bandit's speech estimate, or an imported replacement. |
| Music | Bandit's music estimate, or an imported replacement. |
| Effects | Bandit's combined effects/environment estimate, or an imported replacement. |
| Ambience | An optional imported track. Automatic ambience extraction is future research. |

The channel meters show **peak level in dBFS**, separate from fader gain in dB. During playback they measure audio passing through each channel. While paused, they show a short 100 ms peak window at the playhead. This is a digital peak meter, not a LUFS/loudness measurement.

**S** solos a channel for audition only; solo does not affect exports. Each channel's version selector changes which complete asset feeds the channel. Its existing time edits still apply. **No track** removes that channel from the whole mix until a version is selected again.

The displayed **Output protection** trim reserves headroom for the full +6 dB fader range. It is shared across tracks and used identically in mix playback and export. Volume edits do not recalculate that trim, so a boost in one interval does not turn down the rest of the timeline. Adding/replacing assets or changing which split branches are active can change the reserved headroom. Before/Cleaned/Removed auditions play the asset itself, before fader automation and shared output trim.

Bandit's estimates can contain leakage or missing detail. A mixer changes their balance; it cannot recover detail that separation failed to capture. The Lab does not claim perfect reconstruction of the original recording.

## Split a stem into deeper layers

**Layer 1** is the original set of Dialogue, Music, Effects and optional Ambience. Each channel has **Split again**. This reruns Bandit on that channel's selected full stem, rather than on the original video again.

1. Click **Split again** on the stem you want to explore.
2. Choose Auto, CPU or NVIDIA GPU, then **Split into Layer 2**. This processes the whole stem; the frame/second/range selection controls later volume edits.
3. The new layer contains **Dialogue, Music, Effects and Remainder**. Remainder retains the difference between the parent and the three model estimates, so their combined unedited audio preserves the parent signal within floating-point precision. It can contain useful sound, artifacts or very little audio; audition it before muting it.
4. Mix, solo, download, import into or target-clean the child tracks. Their starting time edits are copied from the parent. Each child has its own controls after that.
5. Click **Split again** on a child to create **Layer 3**, and continue from an active child when needed. Layer numbers count depth, not removal strength or a guaranteed quality improvement.

Use **Explore your layers** to move between branches. Changing the viewed layer does not change what plays: the master includes all active branches. Once a split is active, its children replace its parent in playback and export; the parent is not added a second time. The parent's faders and version selector are locked while its split is in use. **Open Layer** takes you to its child controls. During playback the parent meter/solo follows its active descendants; while paused its meter label points to the child layer.

**Listen to parent** auditions the saved source before time edits and output protection. **Use parent in mix** restores the parent with its saved time edits. The deeper tracks and their edits remain saved; **Use this split in mix** restores that branch. Activate an ancestor before reactivating a deeper saved branch. If you change the parent's source or time edits after returning to it, split that changed parent again; an older split retains the settings it was made from.

Higher layers still use the same dialogue/music/effects model. They do not introduce instrument-specific models or guarantee cleaner isolation. Repeated separation can add leakage or artifacts. Compare the parent and children with your footage. Normal prompt cleanup remains available for individual active children through **Target a sound**.

The development build allows up to **Layer 8**, **16 active tracks** and **64 stored track slots** per session. Each split adds four stored child tracks. These limits bound playback and project growth; saved parent layers and source audio remain available. Each split is an explicit processing job, with the usual progress, cancellation and retry behavior. Gain Undo history restarts when the layer structure or active branch changes; use the parent/split controls to change branches.

## Target a sound inside one stem

1. Choose the affected stem and time interval.
2. Describe one sound, such as **water bubbling** or **a ringing phone**.
3. Set removal strength and **1–4 repeated passes** independently. Each pass processes the previous pass's result.
4. Choose **Preview ≤10 s**. The preview begins at the selected start and is capped at ten seconds; its processed interval is displayed.
5. Audition **Before**, **Cleaned** and **Removed sounds** against the same footage. These audition buttons play only the processed interval. Listen for wanted audio in Removed sounds.
6. Choose **Apply cleanup** for the intended full interval. Applying while a preview is selected starts from that preview's parent asset, avoiding an accidental extra pass over the preview.

Cleanup saves a new stem version. Other channels and their automation are retained. Previous versions remain available in the channel selector. A selected preview blocks mix export until you apply cleanup or select a full version. **Reuse these settings** restores a saved cleanup's prompt, strength, passes and range into the controls.

Removed sounds have their own audition and download; they are not added to the master mix. Cleanup uses the existing local AudioSep/text-encoder path. Auto/CPU/NVIDIA selection and GPU-memory fallback follow the main app. Mac processing remains CPU. First use can download model assets; no prompt or footage is sent to a cloud processor.

More passes can help persistent unwanted sounds, including bubbles, but can also remove wanted detail. Targeted separation remains experimental; workflow completion does not establish perceptual quality.

## Import or replace a stem

Choose a channel, then import audio from an editor or sound library. Imports begin at 0:00 and retain the session's full timeline. Choose a duration rule explicitly:

- **Match footage exactly:** reject a duration mismatch rather than silently changing it.
- **Pad / trim to footage:** append silence to a short file or trim a long file's tail. No looping or time stretching occurs.

Imports are resampled to the session rate. Mono is duplicated for a stereo session; stereo is averaged for mono. Existing assets remain available as versions. An ambience file is added as a fourth channel; it does not automatically subtract ambience already present in Effects.

## Export

**Export mix & stems** produces full-length 24-bit WAVs for the master and each active automated channel, an edit/provenance report, and a ZIP containing those files. With deeper layers, exports include active child tracks instead of their parent; child filenames include the layer, stem type and a short unique identifier. The report records the layer tree and active selections. The source-stem download arrow on a channel instead downloads the selected asset **before** fader edits. Use the exported channel WAV for a track with its automation applied.

For video sources, **Include footage with the new soundtrack** also creates an MP4. The picture stream is copied without re-encoding, and the replacement audio is encoded as AAC. If the original picture cannot be copied into MP4, the WAV mix remains the editor-friendly alternative; read the export status. The original embedded soundtrack is replaced, not layered underneath the new mix.

Exports keep their revision. After further edits, the download area marks the older export as out of date until you export again. The exported report includes the selected assets, time edits and shared output gain. It is a record, not an importable project format.

## Recovery and current limits

Processing runs in an owned worker process. Cancellation stops that worker and its child processes and keeps the previous saved state. Failed or partial worker outputs do not become selected versions. Retrying is explicit. Concurrent processing is blocked, and stale edits from another tab are rejected rather than overwriting a newer saved mix.

Playback buffers up to two 20-second chunks per active channel, instead of decoding every full-length track into browser memory. If buffering falls behind, playback pauses with a retry message. All stems use one Web Audio clock; video follows that playhead. Backend inference still has the existing model and memory requirements.

No EQ, compression, stereo panning, instrument-specific stems, automatic ambience separation, or automatic update installation is included. Windows/Mac installer and native lifecycle tests remain release gates. See [verification](../VERIFICATION.md), [release plan](NEXT-RELEASE-PLAN.md) and [future work](../ROADMAP.md).
