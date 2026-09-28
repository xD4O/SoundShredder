<div align="center">

<img src="desktop/icon-256.png" alt="SoundShredder" width="76" height="76">

# SoundShredder

### Keep the shot. Clean the sound.

Remove unwanted dialogue, music and sound effects from your videos.<br>
Preview the result with your footage. Download the mix or each isolated track.

**Local processing · Windows & macOS · CPU & NVIDIA GPU**

<p>
  <a href="https://github.com/xD4O/SoundShredder/releases/download/v1.3.0/SoundShredder-Electron-1.3.0-Windows-x64-Setup.exe"><strong>Download for Windows</strong></a>
  &nbsp; · &nbsp;
  <a href="https://github.com/xD4O/SoundShredder/releases/download/v1.3.0/SoundShredder-Electron-1.3.0-macOS-arm64.dmg"><strong>Mac · Apple Silicon</strong></a>
  &nbsp; · &nbsp;
  <a href="https://github.com/xD4O/SoundShredder/releases/download/v1.3.0/SoundShredder-Electron-1.3.0-macOS-x64.dmg"><strong>Mac · Intel</strong></a>
</p>

[Latest release: 1.3.0](https://github.com/xD4O/SoundShredder/releases/latest) · [Install the desktop app](#install-the-desktop-app) · [Run in your browser](#run-the-web-app-locally) · [How it works](#from-clip-to-cleaned-audio) · [Guides](#guides-and-support)

Made by **cyr4x** for the **Higgsfield Community**.

</div>

![Mixing Lab with reference footage at 7.5 seconds, extracted dialogue, music and effects, and an imported ambience track](docs/images/readme-mixing-lab.png)

<p align="center"><sub>Mixing Lab: your footage, extracted stems and levels at the playhead, together. Ambience is an optional imported track.</sub></p>

## Your footage. Your soundtrack.

Built for Seedance, Genjutsu and other generations where the shot works but the audio needs cleaning. Drop in an MP4, MOV, MP3 or WAV directly; SoundShredder extracts the audio for you.

| Separate the layers | Target unwanted bubbles | See and hear the result |
| :--- | :--- | :--- |
| Keep or remove dialogue, music and effects. Remix without separating again. | Reduce bubble-like sounds with a selected time range and optional aggressive multi-pass. | Toggle the video monitor, audition individual tracks and export WAVs for your editor. |

Audio stays on your computer. Initial engine/model downloads need internet; cached processing works offline. No account or API key is required.

## Describe a sound. Shape the scene.

**Target a Sound · Guided** adds local text prompts, time ranges, short previews and 1–4 cleanup passes. Describe one unwanted sound—such as “water bubbling” or “footsteps”—then compare Before, Cleaned and Removed before saving a version. More passes can catch remnants and can also remove wanted audio. [Prompt cleanup guide](docs/TARGETED-CLEANUP.md).

**Mixing Lab** puts your reference video beside Dialogue, Music, Effects and optional imported Ambience. Upload a file, use the visible **Extract stems** area, then adjust one second, one nominal frame or a selected range. Levels return to their saved values outside that interval. Solo tracks, target one stem, and export channel WAVs, a master, a ZIP or an MP4 with your mix. Automatic ambience extraction and recursive splits are not included. [Mixing Lab guide](docs/MIXING-LAB.md).

![Target a Sound guided workflow with Water bubbling, a 7–11 second interval, 85 percent strength and two cleanup passes](docs/images/readme-targeted-cleanup.png)

<p align="center"><sub>Describe one sound, select its time range, then preview. This saved bubble-cleanup example uses two passes; always audition what was removed.</sub></p>

## Install the desktop app

**Recommended for Windows and Mac.** The Electron app includes Python and installs its audio engine automatically. You get the same interface in a dedicated window, with native menus, Save dialogs and saved sessions.

> [!TIP]
> **The Mac 1.3.0 downloads are Developer ID signed and Apple-notarized.** Use the current downloads below to replace an older Mac preview. Published Mac packages require Gatekeeper, installed-app lifecycle and signed update checks on both architectures.

| Platform | Download | Requirements |
| :--- | :--- | :--- |
| **Windows** | [EXE installer](https://github.com/xD4O/SoundShredder/releases/download/v1.3.0/SoundShredder-Electron-1.3.0-Windows-x64-Setup.exe) | Windows 10/11 x64 · CPU or compatible NVIDIA GPU |
| **Mac · Apple Silicon** | [DMG installer](https://github.com/xD4O/SoundShredder/releases/download/v1.3.0/SoundShredder-Electron-1.3.0-macOS-arm64.dmg) | macOS 13+ · M-series Mac · CPU |
| **Mac · Intel** | [DMG installer](https://github.com/xD4O/SoundShredder/releases/download/v1.3.0/SoundShredder-Electron-1.3.0-macOS-x64.dmg) | macOS 13+ · Intel Mac · CPU |

### Windows EXE

> [!IMPORTANT]
> **Windows 1.3.0 is unsigned.** Edge may say the EXE is not commonly downloaded; Windows may show SmartScreen or an unknown publisher. Use only the official **xD4O/SoundShredder** release and compare its SHA-256 checksum. This reputation warning is not a specific malware finding; GitHub hosting alone is not a safety guarantee. [Download verification and warning instructions](docs/WINDOWS-DOWNLOADS.md).

1. **Download the EXE** above. Quit an older SoundShredder standalone through its setup screen before installing.
2. **Run the installer.** Choose the app folder and finish setup. No separate Python installation, PATH changes or administrator rights are needed.
3. **Open SoundShredder** from Start or the desktop shortcut. Use **Choose folder…** to pick a drive for engines, models and sessions, or keep the current location.
4. **Choose CPU or NVIDIA GPU**, then select **Set up SoundShredder**. Keep internet connected for the initial downloads. The workspace opens when ready.

Allow **4 GiB free for CPU** or **14 GiB for NVIDIA** setup, plus the app, models and saved media. NVIDIA needs a compatible GPU and current driver; a separate CUDA Toolkit is not required.

**Choose your storage:** use **SoundShredder → Choose storage folder…** to change the location later. Your choice survives updates and reopening. Existing files stay in their original folder; select that folder again to return to its saved work. Keep external drives connected. [Storage guide](electron/docs/WINDOWS.md#choose-where-your-files-live).

**First setup:** watch live download progress, open Setup details, or use **Cancel setup**. Closing during setup offers **Cancel setup and quit**. Reopen and retry to repair an interrupted engine; saved sessions are kept. See the [setup recovery guide](electron/docs/WINDOWS.md#follow-or-cancel-first-setup).

**Uninstall:** quit the app, then choose **Uninstall SoundShredder** in Start or remove it through **Windows Settings → Apps**. Saved sessions and engines are kept. See the [Windows uninstall guide](electron/docs/WINDOWS.md#uninstall-the-windows-app) for full removal.

### macOS DMG

1. **Download the matching DMG** above. Check Apple menu → About This Mac: use Apple Silicon for M-series chips, or Intel for Intel processors.
2. **Quit any older standalone.** Open the DMG, drag **SoundShredder** into **Applications**, then eject the disk image.
3. **Open SoundShredder** from Applications. Optionally use **Choose folder…** for engines, models and sessions, then select **Set up SoundShredder**. The CPU engine downloads automatically. No Homebrew or separate Python is needed.

Allow **3 GiB free for setup**, plus the app, models and saved media. Mac processing currently uses CPU; Apple Metal/MPS is not enabled. ZIP alternatives, Mac instructions and checksums are on the [current release page](https://github.com/xD4O/SoundShredder/releases/tag/v1.3.0).

> [!IMPORTANT]
> The Windows installer is unsigned and may show SmartScreen. The current Mac builds are signed and notarized; macOS may still ask for the usual confirmation when opening an app downloaded from the internet. Read the [Windows guide](electron/docs/WINDOWS.md) or [Mac guide](electron/docs/MACOS.md) for installation and troubleshooting.

**Close and return:** finish or cancel setup/processing, then close the window or choose **SoundShredder → Quit SoundShredder**. Reopen the same shortcut or app to return to your saved sessions. Opening it twice brings the existing window forward.

## Run the web app locally

Prefer the interface in your browser? Use the Python source version. It runs on **your computer at localhost**; there is no hosted website to sign into.

**[Download the web app source ZIP](https://github.com/xD4O/SoundShredder/archive/refs/heads/main.zip)** → extract the entire ZIP into a writable folder such as Documents. Keep the extracted files together and follow your platform below.

<a id="source-setup-on-windows"></a>

### Windows browser setup

1. Install **Python 3.12** from [python.org](https://www.python.org/downloads/), with **Add Python to PATH** enabled.
2. In the extracted SoundShredder folder, run **Setup CPU.bat** for CPU, or **Setup NVIDIA GPU.bat** for a compatible NVIDIA GPU. Wait for installation to finish.
3. Double-click **Start SoundShredder.bat**. It opens the app in your browser, normally at **http://127.0.0.1:7860**.

Keep the launcher window open while using the web app. Close it or press **Ctrl+C** to stop the server; reopen the same Start file next time. Closing only the browser tab leaves the server running.

<a id="source-setup-on-mac"></a>

### Mac browser setup

1. Use **macOS 12+** and install **Python 3.11** with the [macOS universal2 installer](https://www.python.org/downloads/release/python-3119/). It works on Apple Silicon and Intel.
2. Open **Start SoundShredder.command** in the extracted folder. The first run installs the CPU dependencies and opens the browser interface.
3. Keep its Terminal window open. Press **Control+C** to stop; reopen the same launcher to return.

If Finder will not run the `.command` file, type `bash ` in Terminal, drag the launcher into that window, and press Return. For `CERTIFICATE_VERIFY_FAILED`, follow the [Mac source certificate repair guide](support/mac/README.md).

Both browser setups need internet for the first engine/model downloads. Run one server per session folder. For Linux or command-line use, see the [manual setup reference](docs/REFERENCE.md#manual-installation--other-operating-systems).

## From clip to cleaned audio

1. **Drop your video or audio.** No separate audio extraction is needed.
2. **Pick a preset.** Remove music, keep dialogue only, keep effects only, remove effects, remove dialogue, or target Bubble FX.
3. **Process and compare.** Toggle **Show video preview** and switch between the original, cleaned mix and available tracks.
4. **Download your result.** Save the cleaned WAV, individual tracks or a ZIP. Import the audio into your editor and mute the original soundtrack.

**The separator exports audio; Mixing Lab can also export an MP4 with your new mix.** Inputs support up to **500 MB / 10 minutes / mono or stereo**. AI separation can affect wanted sounds too; audition the result before using it in your final edit.

### Try it with the Akira example

The [Akira walkthrough](docs/AKIRA-EXAMPLE.md) uses **TestFootage.mp4**, a roughly 43-second clip: select **Remove music**, keep dialogue/effects at 100%, preview **Original** versus **Cleaned mix**, then download the WAV or isolated tracks. The screenshots show a real completed session, including a nearly silent dialogue track. Use your own footage to follow along; the video itself is not bundled.

### Stubborn bubbles, meet another pass

Choose **Bubble FX → Water bubbles**, enable **Aggressive multi-pass**, and start with **2 passes**. Try 3 or 4 for stronger cleanup. Limit the range when possible, such as **7–11 seconds**, and listen to **Removed sounds** to check what was taken away.

More passes take longer and may reduce similar effects. Bubble FX uses preset sound descriptions. For your own description, use **Target a Sound · Guided** or a selected stem's cleanup controls in Mixing Lab. Prompt cleanup remains experimental; preview the removed audio before applying it.

### Every layer, its own track

Listen to **Dialogue**, **Music**, **Sound effects** and **Removed sounds** independently, with waveforms and individual WAV downloads. Keep playback positions linked to compare the same moment.

Normal separation prepares the tracks automatically. In a Bubble FX session, use **Prepare isolated tracks** to separate dialogue, music and effects from the original audio; the cleaned result stays intact.

In **Mixing Lab**, use each channel's download arrow for its selected source stem. Choose **Export mix & stems** to include your volume edits in channel WAVs and the master mix, plus an optional video with the new soundtrack.

![Mixing Lab export panel with separate channel WAVs, a WAV mix, edit report, video and ZIP downloads](docs/images/readme-stem-exports.png)

<p align="center"><sub>Take individual tracks back to your editor, or download the complete mix. The reminder appears when an export predates your latest edits—export again to include them.</sub></p>

## Sessions and updates

| Task | Where to go |
| :--- | :--- |
| Start a new session | **Audio separator** in the left panel. Completed sessions remain saved. |
| Reopen a result | Choose a filename under **Recent sessions**. |
| Delete a separator session | Use its **×** or **Delete this session**. Save wanted downloads elsewhere first. |
| Close a Mixing Lab session | **Close session** or its **×** moves it into **Closed sessions**, where you can reopen it. |
| Update Electron | **Help → Check for Electron updates → Download update → Restart & update**. Choose Later while working. |
| Update the browser version | Download a fresh source ZIP. With both apps stopped, copy the old `data` folder into the new folder and run its launcher. Keep the old folder until checked. |

Electron checks stable GitHub releases automatically. Use **Help → Check for Electron updates** or the sidebar to review release notes and download size, then **Download update**. Progress and **Cancel** stay available while you work. Choose **Restart & update** when finished or **Later** to keep working; normal Quit does not install. Active processing, uploads, saves and file downloads block the restart. Sessions, storage choice and compatible engines are retained.

**Coming from 1.2.2?** Install 1.3.0 manually once to gain the new updater. The browser edition continues to update manually. [Desktop update guide](electron/docs/UPDATES.md).

<a id="community-guide"></a>

## Guides and support

- **[Illustrated community guide (PDF)](output/pdf/SoundShredder-Higgsfield-Community-Guide.pdf)** · [Save the HTML guide](https://raw.githubusercontent.com/xD4O/SoundShredder/main/output/html/SoundShredder-Higgsfield-Community-Guide.html) and open it in a browser.
- **[Akira walkthrough](docs/AKIRA-EXAMPLE.md)** · [Windows download warnings](docs/WINDOWS-DOWNLOADS.md) · [All guides](docs/README.md).
- **[Windows desktop help](electron/docs/WINDOWS.md)** · **[Mac desktop help](electron/docs/MACOS.md)** · [Mac source SSL repair](support/mac/README.md).
- [Detailed usage, CLI and model reference](docs/REFERENCE.md) · [Build Electron](electron/README.md) · [Tested behavior and limitations](VERIFICATION.md).
- [Report an issue](https://github.com/xD4O/SoundShredder/issues) · [Roadmap](ROADMAP.md) · [Release history](RELEASE_NOTES.md).

Layer separation uses [Bandit v2](https://github.com/kwatcharasupat/bandit-v2); targeted Bubble FX uses [AudioSep](https://github.com/Audio-AGI/AudioSep). Model weights download separately. See [model attribution and licenses](docs/REFERENCE.md#model-attribution) and [branding credits](static/BRANDING.md).

---

<div align="center">

**Made by cyr4x · Made for the Higgsfield Community**

[X](https://x.com/_cyr4x) · [Higgsfield](https://higgsfield.ai/@cyr4x) · [Instagram](https://www.instagram.com/__cyr4x__/) · [YouTube](https://www.youtube.com/@cyr4xfilms)

<sub>Community-created. Not an official Higgsfield product. Screenshots show details of the shared interface.</sub>

</div>
