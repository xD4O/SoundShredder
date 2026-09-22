"""Shared, versioned content for the community HTML and PDF guide."""

REPO = 'https://github.com/xD4O/SoundShredder'
RELEASE = REPO + '/releases/tag/v1.2.2'
ASSETS = REPO + '/releases/download/v1.2.2/'

def link(url, label): return f'<link href="{url}" color="#79f6d3">{label}</link>'
def p(text): return {'type': 'p', 'text': text}
def fig(name, caption, maxh=240): return {'type': 'figure', 'name': name, 'caption': caption, 'maxh': maxh}
def note(title, text): return {'type': 'note', 'title': title, 'text': text}
def cards(items): return {'type': 'cards', 'items': items}
def steps(items): return {'type': 'steps', 'items': items}
def page(id, title, blocks, cover=False): return {'id': id, 'label': 'SOUNDSHREDDER / COMMUNITY FIELD GUIDE', 'title': title, 'blocks': blocks, 'cover': cover}

WINDOWS = link(ASSETS + 'SoundShredder-Electron-1.2.2-Windows-x64-Setup.exe', 'Download Windows EXE')
ARM = link(ASSETS + 'SoundShredder-Electron-1.2.2-macOS-arm64.dmg', 'Download Apple Silicon DMG')
INTEL = link(ASSETS + 'SoundShredder-Electron-1.2.2-macOS-x64.dmg', 'Download Intel Mac DMG')
WARNINGS = link(REPO + '/blob/main/docs/WINDOWS-DOWNLOADS.md', 'Windows download verification and warning guide')

PAGES = [
    page('start', 'Keep the shot.\nClean the sound.', [
        p('Clean distracting audio in Seedance, Genjutsu and other generations, or work with existing MP4, MP3 and WAV files. Drop one file, choose what stays, compare the layers and download audio for your edit.'),
        fig('akira-video-preview', 'Akira example: a real completed session, with the cleaned mix synchronized to the footage.', 205),
        cards([
            ('REMOVE A GENERATED SCORE', 'Keep estimated dialogue and effects while making room for your own music.'),
            ('CONTROL VOICES AND EFFECTS', 'Isolate dialogue, music or scene effects, or exclude an unwanted layer.'),
            ('TARGET STUBBORN BUBBLES', 'Use Water bubbles and optional aggressive multi-pass for persistent remnants.'),
            ('SEE AND HEAR THE RESULT', 'Toggle video preview, audition four tracks and save WAVs independently.'),
        ]),
        p(WINDOWS + ' / ' + ARM + ' / ' + INTEL),
        p('<b>Made by cyr4x. Made for the Higgsfield Community.</b><br/>Version 1.2.2 / Documentation refreshed September 22, 2026.<br/>Community-created; not an official Higgsfield product.'),
    ], cover=True),
    page('windows-install', 'Install on Windows.', [
        p('<b>Windows 10/11 x64 / Electron desktop app.</b> Python is bundled. Engine and model downloads happen inside the app on first use.'),
        note('WINDOWS SIGNING IS PENDING', 'The 1.2.2 EXE is unsigned. Edge may show an uncommon-download warning; Windows may show SmartScreen or an unknown publisher. Use the official xD4O/SoundShredder release and compare checksums. See the next page before running the installer.'),
        steps([
            ('Download the EXE', WINDOWS + ' from the official release. Read the Windows warning page and verify the downloaded file.'),
            ('Quit old copies, then install', 'Quit an older app or use Close SoundShredder on its standalone setup page. Run the EXE, choose the app installation folder, and finish. No separate Python, PATH edits or administrator rights are needed.'),
            ('Open and choose storage', 'Open SoundShredder from Start or its desktop shortcut. Use <b>Choose folder...</b> for engines, models and sessions, or keep the current location. This storage choice is separate from the app installation folder.'),
            ('Set up the engine', 'Select CPU or a compatible NVIDIA GPU, then <b>Set up SoundShredder</b>. Keep internet connected. Allow at least <b>4 GiB free for CPU</b> or <b>14 GiB for NVIDIA</b>, plus the app, models and media. NVIDIA needs a compatible driver; no separate CUDA Toolkit is needed.'),
            ('Use it, quit and reopen', 'The workspace opens automatically. Finish or cancel processing before quitting. Reopen the same shortcut next time; compatible engines and saved sessions are reused.'),
        ]),
        p('<b>Uninstall:</b> quit, then use <b>Uninstall SoundShredder</b> in Start or Windows Settings &gt; Apps. Sessions and engines are retained. ' + link(REPO + '/blob/main/electron/docs/WINDOWS.md', 'Full Windows guide and removal instructions') + '.'),
    ]),
    page('windows-warnings', 'Understand the warning.', [
        p('Our official download source is <b>github.com/xD4O/SoundShredder/releases/latest</b>. The Windows installer is still unsigned. The signed Mac release does not sign the Windows EXE.'),
        note('COMMON MESSAGE', 'Edge: <b>isn\'t commonly downloaded</b>.<br/>Windows: <b>Windows protected your PC</b> or an unknown publisher.<br/>These can be reputation warnings, rather than a report of a specific detected threat.'),
        steps([
            ('Confirm the exact source', 'Use the xD4O/SoundShredder repository and its release Assets. Avoid reuploaded installers and lookalike projects. ' + link(RELEASE, 'Open the official release') + '.'),
            ('Match the checksum', 'Download the EXE and SHA256SUMS.txt from the same release. Run <b>Get-FileHash -Algorithm SHA256 -LiteralPath</b> followed by the quoted path to your downloaded EXE. Compare the entire hash against its filename in the checksum file. ' + WARNINGS + ' includes a copyable command.'),
            ('Keep protections enabled', 'A matching hash checks the bytes against the published file; it is not a malware scan. A named threat detection or a mismatched hash needs investigation. Do not run a mismatched download or disable security protection.'),
            ('Choose whether to continue', 'Only after verifying and trusting the download, Edge may offer <b>Keep &gt; Show more &gt; Keep anyway</b>; Windows may offer <b>More info &gt; Run anyway</b>. Availability varies. If blocked without an override, use the source version where permitted or contact your administrator.'),
        ]),
        note('WHAT WE CAN VERIFY', 'The official installer passed functional install, uninstall, processing and reopen tests. Those checks are not a security audit, and GitHub hosting alone does not guarantee safety. Windows signing is planned; newly signed downloads can still need reputation.'),
        p(link('https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation', 'Microsoft: how SmartScreen reputation works') + ' / ' + link(REPO + '/blob/main/ROADMAP.md', 'Windows signing roadmap')),
    ]),
    page('mac-install', 'Install on your Mac.', [
        p('<b>macOS 13 or newer / Electron desktop app.</b> Current 1.2.2 Apple Silicon and Intel builds are Developer ID signed and Apple-notarized. Mac audio processing uses CPU; Metal/MPS is not enabled.'),
        cards([('APPLE SILICON', ARM + '<br/>For M-series chips. Check Apple menu &gt; About This Mac.'), ('INTEL', INTEL + '<br/>For an Intel processor. Use the matching architecture.')]),
        steps([
            ('Quit any older SoundShredder copy', 'Use its Quit command or, for older browser standalones, Close SoundShredder on the setup page. Keep your saved engine and session folders.'),
            ('Move the app into Applications', 'Open the matching DMG, drag SoundShredder into Applications, replace the old app if needed, then eject the disk image. Open SoundShredder from Applications.'),
            ('Choose storage and set up', 'Optionally use <b>Choose folder...</b>, then <b>Set up SoundShredder</b>. Allow at least <b>3 GiB free</b>, plus the app, models and saved media. Internet is required initially. No Homebrew, separate Python or developer membership is needed to use the app.'),
            ('Quit and return', 'Finish or cancel audio work before quitting. During setup, Cancel setup and quit is available. Reopen from Applications or the Dock; completed sessions remain saved.'),
        ]),
        note('IF FINDER REPORTS DAMAGE', 'The old 1.2.0 preview was unsigned and unnotarized. Download the current 1.2.2 build, check its checksum and architecture, then copy it into Applications. If the warning persists, report the exact message. Do not disable Gatekeeper or remove quarantine as an installation step.'),
        p('<b>Uninstall:</b> quit and move SoundShredder.app to Trash. Saved data remains in the chosen folder and the user profile. ' + link(REPO + '/blob/main/electron/docs/MACOS.md', 'Mac storage, removal and troubleshooting') + '.'),
    ]),
    page('source-install', 'Prefer your browser?', [
        p('The Python source version runs on your own computer at localhost. It uses the same workspace. Choose this route if you want source access; Electron is the easier installation for most users.'),
        p(link(REPO + '/archive/refs/heads/main.zip', 'Download the source ZIP') + '. Extract the entire folder into a writable location such as Documents. Keep all files together.'),
        cards([
            ('WINDOWS SOURCE', 'Install <b>Python 3.12</b> from python.org with <b>Add Python to PATH</b>. Run <b>Setup CPU.bat</b> or <b>Setup NVIDIA GPU.bat</b>. When finished, run <b>Start SoundShredder.bat</b>.'),
            ('MAC SOURCE', 'Use <b>macOS 12+</b> and the Python <b>3.11 universal2</b> installer. Run <b>Start SoundShredder.command</b>. If Finder will not run the launcher, type <b>bash </b> in Terminal, drag the file into that window and press Return.'),
        ]),
        steps([
            ('Wait for initial setup', 'The launcher downloads the CPU or selected NVIDIA engine. First processing also downloads model weights. The browser normally opens <b>http://127.0.0.1:7860</b>.'),
            ('Keep the launcher window open', 'Closing the browser tab does not stop the server. Use <b>Ctrl+C</b> on Windows or <b>Control+C</b> on Mac to stop it. Reopen the same launcher next time.'),
            ('Repair Mac source certificates if needed', 'For Python 3.11.9 with CERTIFICATE_VERIFY_FAILED, run <b>Applications &gt; Python 3.11 &gt; Install Certificates.command</b>, then restart SoundShredder. Keep SSL verification enabled. This repairs the source Python environment, not Electron\'s bundled runtime.'),
        ]),
        p(link(REPO + '#run-the-web-app-locally', 'Complete source installation instructions') + ' / ' + link(REPO + '/blob/main/support/mac/README.md', 'Mac source SSL troubleshooting and repair launcher')),
        note('LOCAL PROCESSING', 'Media stays on your computer. Dependencies and model weights need internet initially; cached processing works offline. No SoundShredder account or API key is required.'),
    ]),
    page('akira', 'Try it with Akira.', [
        p('This worked example uses the supplied <b>TestFootage.mp4</b>: approximately <b>43 seconds</b>, with <b>48 kHz stereo</b> audio. The screenshots show a completed local Windows source-app run; Electron shares these controls.'),
        fig('akira-video-preview', 'Show video preview is enabled. Cleaned mix is selected at 0:12 for comparison.', 260),
        steps([
            ('Drop the MP4 and remove music', 'Choose <b>Remove music</b>: Dialogue 100%, Music 0%, Sound effects 100%. Choose Auto, CPU or NVIDIA GPU, then <b>Separate audio</b>. The example used Auto on an RTX 5090; Mac users choose CPU.'),
            ('Compare with the footage', 'Enable <b>Show video preview</b>. Switch <b>Listen to</b> between Original and Cleaned mix at the same moment. The monitor uses muted video synchronized to the selected audio.'),
            ('Refine the result', 'Audition wanted effects and any voices. If needed, adjust layer levels and click <b>Update mix</b>. Disable Show video preview to return to an audio-only workspace.'),
        ]),
        note('AN EXAMPLE, NOT A QUALITY GUARANTEE', 'This run demonstrates music removal. It does not establish that the Akira clip contains bubbles. Screenshots are included for the walkthrough; the full video and extracted soundtrack are not distributed. Use your own clip to follow along.'),
    ]),
    page('tracks', 'Every layer, its own track.', [
        fig('akira-isolated-tracks', 'The Akira session: four track strips with separate playback controls and WAV downloads.', 243),
        cards([
            ('DIALOGUE + MUSIC', 'Dialogue is the estimated voice layer; it is nearly silent in this example. Music contains the estimated score. A quiet waveform does not necessarily indicate an error.'),
            ('EFFECTS + REMOVED SOUNDS', 'Effects contains estimated scene audio. Removed sounds contains material excluded by your latest mix; here it corresponds to the excluded music layer.'),
        ]),
        steps([
            ('Compare one track at a time', 'Keep <b>Keep playback position when switching tracks</b> enabled to audition the same moment. Starting a track pauses the others. Preview volume/mute does not change the export.'),
            ('Download the layer you need', 'Use the Download control on Dialogue, Music, Sound effects or Removed sounds. Normal separation prepares them automatically.'),
            ('Preparing tracks after Bubble FX', 'Use <b>Prepare isolated tracks</b> to hear dialogue/music/effects from the original audio before bubble cleanup. This extra separation preserves the cleaned bubble result; download its added layers individually.'),
        ]),
        note('LISTEN TO WHAT WAS REMOVED', 'If Removed sounds includes wanted impacts, ambience or vocal detail, reduce the cleanup or revise the mix. AI separation can leave bleed or reduce wanted sounds.'),
    ]),
    page('presets', 'Choose what stays.', [
        p('Layer presets set the estimated dialogue, music and effects levels. <b>0% excludes a layer; 100% keeps it.</b> Intermediate levels reduce it. Change levels after separation and click Update mix to reuse the existing stems.'),
        {'type':'table','headers':['PRESET','KEEPS / TARGETS','USE IT FOR'],'rows':[
            ['Remove music','Dialogue + effects','Replacing an unwanted generated score.'],
            ['Dialogue only','Dialogue','Editing or reusing estimated voices.'],
            ['Effects only','Sound effects','Working with impacts, movement and ambience.'],
            ['Remove effects','Dialogue + music','Reducing an unwanted effects layer.'],
            ['Remove dialogue','Music + effects','Reducing unwanted narration or voices.'],
            ['Bubble FX','Selected bubble-like sound','Targeted cleanup instead of excluding all effects.'],
        ]},
        cards([
            ('SEEDANCE / GENJUTSU', 'Keep a generation whose picture works but soundtrack distracts. Export the video, then drop it into SoundShredder. Choose the preset for the unwanted audio category.'),
            ('OTHER VIDEO OR MP3 SOURCES', 'Apply the same workflow to your existing media. Dialogue removal is not an individual-speaker selector, and Effects only can include ambience.'),
        ]),
        note('MODEL LIMITS', 'The layer model can confuse singing, breaths, rhythmic impacts and music. It cannot identify every arbitrary sound or preserve all overlapping detail. Audition the original, cleaned mix and removed material before editing.'),
        p('<b>Custom text prompts:</b> Bubble FX currently uses four preset sound descriptions. Free-form prompts are not a control in this release.'),
    ]),
    page('bubbles', 'Target stubborn bubbles.', [
        p('Use <b>Bubble FX</b> for a distracting bubble, pop or gurgle while trying to retain other effects. This uses AudioSep separately from the dialogue/music/effects model.'),
        fig('bubble-cleanup', 'Separate bubble-settings example: 85% reduction, two passes and a 7-11 second range. Not the Akira run.', 195),
        steps([
            ('Match the unwanted sound', 'Choose <b>Water bubbles</b>, <b>Bubbling &amp; popping</b>, <b>Liquid gurgle</b> or <b>Cartoon boing</b>. Start near <b>85%</b> reduction and restrict the time range when possible.'),
            ('Try aggressive multi-pass for Water bubbles', 'Enable <b>Aggressive multi-pass</b> and start with <b>2 passes</b>. Each pass rechecks the previous cleaned audio. Try 3 or 4 only if stubborn remnants remain. More passes take longer and can affect similar wanted effects.'),
            ('Check the combined removed sound', 'Compare Original, Cleaned mix and Removed sounds. The latter combines removal across all passes. Reduce strength, narrow the interval or use fewer passes if wanted effects are caught.'),
            ('Rerun when settings need fresh inference', 'Changing sound type, pass count or multi-pass strength/range needs <b>Clean up again</b>, which starts from the saved original in a new session. Single-pass strength/range changes can use <b>Update mix</b>.'),
        ]),
        note('EXPERIMENTAL CLEANUP', 'Multi-pass is available for Water bubbles only. It can reduce persistent remnants, but cannot promise bubble-only removal. Decoded samples outside the chosen interval stay unchanged in the float WAV.'),
    ]),
    page('export', 'Take it into your edit.', [
        p('Download a ready-to-use mix or separate layers for more control. Electron uses a native Save dialog; the source web app uses your browser\'s download behavior.'),
        {'type':'table','headers':['DOWNLOAD','CONTENTS'],'rows':[
            ['Cleaned WAV','Audio retained by your latest settings.'],
            ['Individual track','Dialogue, music, effects or removed audio.'],
            ['Layer-separation ZIP','Stems, cleaned mix, removed audio and processing report.'],
            ['Bubble cleanup ZIP','Cleaned audio, combined removed sound and report. Additional prepared layers are downloaded separately.'],
        ]},
        steps([
            ('Align the WAV to the original', 'Import it into Premiere Pro, DaVinci Resolve or your editor. Place it at the original clip start and mute the original soundtrack. Check sync and transitions.'),
            ('Keep useful isolated layers', 'Put music, voices and effects on their own editor tracks. Build your score or foley around the material you want to retain.'),
            ('Save before deleting a session', 'Download the outputs to your project folder and keep the processing report. Deleting a SoundShredder session removes its local generated files.'),
        ]),
        note('AKIRA TIMING CHECK', 'The example exports preserve the decoded source: <b>2,052,096 frames / 48,000 Hz / 42.752 seconds / stereo</b>. Timing alignment was checked; these numbers do not measure audible separation quality.'),
        p('<b>Audio exports, not a replacement MP4.</b> The footage monitor is for preview. Layer separation exports 24-bit PCM WAV; Bubble FX exports 32-bit float WAV. Original media is preserved.'),
    ]),
    page('sessions', 'The left panel, explained.', [
        cards([
            ('START A NEW SESSION', 'Click <b>Audio separator</b> at the top of the left panel. The workspace resets so you can import another file; completed saved sessions remain.'),
            ('RETURN TO SAVED WORK', 'Click a filename under <b>Recent sessions</b>. The Akira example appears as <b>TestFootage.mp4</b>. Use the refresh control to update the list.'),
            ('THE X DELETES A SESSION', 'The <b>x</b> beside a filename removes that local session after confirmation. It is not a close-tab button. <b>Delete this session</b> has the same purpose.'),
            ('LEAVE WITHOUT DELETING', 'Start a new session or quit the app. Completed work remains. Click <b>Update mix</b> to save slider changes before leaving; unsaved changes are not a new export.'),
        ]),
        steps([
            ('Finish or cancel active work', 'Wait for processing or click Cancel before quitting. During desktop setup, choose Cancel setup and quit if you need to stop.'),
            ('Quit Electron and reopen normally', 'Close its window or use <b>SoundShredder &gt; Quit SoundShredder</b>. Use the Start shortcut or Applications/Dock next time. Opening twice brings the existing window forward.'),
            ('Stop source and older browser launchers correctly', 'Closing a browser tab leaves the server running. Stop the source launcher with Ctrl+C / Control+C; older standalone apps have a Close SoundShredder setup control.'),
        ]),
        note('VERSION, GITHUB AND UPDATES', 'The bottom-left card contains the version, GitHub project link and manual Check for updates button. It checks GitHub when clicked. Desktop Help &gt; Check for Electron updates opens releases.'),
    ]),
    page('support', 'Storage, updates and help.', [
        cards([
            ('CHOOSE YOUR STORAGE', 'Use <b>SoundShredder &gt; Choose storage folder...</b>. The app remembers the choice. Files are not moved; choose your old folder again to return to its sessions. Keep external drives connected.'),
            ('SETUP FEELS SLOW', 'Open Setup details to see package activity. Download bars can pause while packages install. Cancel and retry are available; keep enough free space and an internet connection.'),
            ('UPDATES ARE MANUAL', 'Quit and run a newer Windows EXE or replace the Mac app. Saved profiles and compatible engines remain. The sidebar follows numbered releases and ignores prereleases; no silent auto-install is enabled.'),
            ('FILES AND DEVICES', 'One file at a time: up to <b>500 MB / 10 minutes / mono or stereo</b>. Windows supports CPU or compatible NVIDIA CUDA; Mac uses CPU. AMD GPU and Apple Metal/MPS acceleration are not implemented.'),
        ]),
        p('<b>Models:</b> first use downloads about 426 MB for Bandit layer separation or 1.2 GB for Bubble FX. Cached runs can work offline. CPU processing may take longer than the clip duration.'),
        p('<b>Need help?</b> Include the exact release filename, OS/chip, processing mode and error. Use Setup details or Open logs folder; review private paths before sharing. A named malware detection should be reported separately from an uncommon-download warning.'),
        p(link(REPO + '/issues', 'Report an issue') + ' / ' + link(REPO + '/blob/main/docs/README.md', 'All documentation') + ' / ' + link(REPO + '/blob/main/VERIFICATION.md', 'Verification and limits')),
        p(link(REPO + '/blob/main/electron/docs/WINDOWS.md', 'Windows guide') + ' / ' + link(REPO + '/blob/main/electron/docs/MACOS.md', 'Mac guide') + ' / ' + link(REPO + '/blob/main/support/mac/README.md', 'Mac source SSL repair')),
        note('MADE BY CYR4X', link('https://x.com/_cyr4x', 'X') + ' / ' + link('https://higgsfield.ai/@cyr4x', 'Higgsfield') + ' / ' + link('https://www.instagram.com/__cyr4x__/', 'Instagram') + ' / ' + link('https://www.youtube.com/@cyr4xfilms', 'YouTube') + '<br/>Made for the Higgsfield Community. Community-created; not an official Higgsfield product.'),
    ]),
]
