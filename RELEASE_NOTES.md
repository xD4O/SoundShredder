# SoundShredder v1.0.3 — Video preview

- Toggleable footage monitor with a remembered show/hide preference.
- Preview original, cleaned, dialogue, music, effects, or removed audio against the same footage.
- Shared play/pause and seeking; audio players drive the muted video clock.
- Reopen saved video sessions without uploading again, with byte-range support for seeking.
- Audio-only sessions hide the monitor. Unsupported browser video codecs show an explanation while audio cleanup remains available.
- Preview only: existing WAV/ZIP exports are unchanged. Browser codec support varies; H.264 MP4 is recommended. Containers with audio/video start offsets may need alignment checked in an editor.
- Local Windows/Mac source packages; no cloud deployment. Updated eleven-page HTML/PDF community guides cover detailed Windows PC installation, Mac setup, video preview and the future installation roadmap.

Validation: 131 Python tests passed, Ruff and JavaScript syntax checks passed. Browser checks used a saved MP4 session with all six audio choices available. Mac hardware testing remains outstanding.

## Downloads and updating

Download SoundShredder.zip for Windows or SoundShredder-Mac.zip for Mac from the assets below. Both ZIPs include installation instructions, README, ROADMAP and the HTML/PDF guides. Python is still installed separately. Finish processing and close the old app, extract the new ZIP into a fresh folder, and copy your old data folder into it to retain sessions. Run the new launcher; cached models are reused. Keep the old folder until the new installation is checked.
