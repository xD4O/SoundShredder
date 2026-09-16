"""Decode, preserve timing, and export audio without changing the source file."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
import uuid
import zipfile
from contextlib import suppress
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

STEMS = ("speech", "music", "effects")
LABELS = {"speech": "Dialogue", "music": "Music", "effects": "Sound effects"}
MAX_SECONDS = 600
MAX_BYTES = 500 * 1024 * 1024
EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".aif",
    ".aiff",
    ".wma",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
}

# Windows readers/scanners can briefly deny replacing an otherwise writable file.
# Retry for at most 1.81 seconds; permanent errors must still reach the caller.
_JSON_RETRY_DELAYS = (0.01, 0.02, 0.04, 0.08, 0.16, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    payload = json.dumps(value, indent=2)
    # Each writer owns its temporary file. Keep it beside the destination so
    # replacement is atomic and readers always see a complete JSON document.
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(payload)
        for attempt in range(len(_JSON_RETRY_DELAYS) + 1):
            try:
                temporary.replace(path)
                return
            except OSError as exc:
                if getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == len(_JSON_RETRY_DELAYS):
                    raise
                time.sleep(_JSON_RETRY_DELAYS[attempt])
    finally:
        # Cleanup must not mask the original error if a scanner holds the temp.
        with suppress(OSError):
            temporary.unlink(missing_ok=True)


def decode(source: Path, work: Path) -> tuple[np.ndarray, int]:
    """Keep the original sample rate and mono/stereo layout, including on FFmpeg fallback."""
    path = source
    try:
        info = sf.info(path)
    except (sf.LibsndfileError, RuntimeError):
        import imageio_ffmpeg

        path = work / "decoded.wav"
        result = subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-t",
                str(MAX_SECONDS + 1),
                "-c:a",
                "pcm_f32le",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise ValueError(
                "This file could not be read. Upload a valid audio file or a video with an audio track."
            ) from None
        info = sf.info(path)
    if info.channels not in (1, 2):
        raise ValueError("Please export a mono or stereo file first. Surround audio is not supported.")
    if info.frames < 2 or info.duration > MAX_SECONDS:
        raise ValueError("Upload a non-empty clip no longer than 10 minutes.")
    if not 8000 <= info.samplerate <= 192000:
        raise ValueError("Supported sample rates are 8–192 kHz.")
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    if not np.isfinite(audio).all():
        raise ValueError("The audio contains invalid samples. Re-export it as a WAV and try again.")
    return audio, rate


def resample(audio: np.ndarray, source_rate: int, target_rate: int, frames: int | None = None) -> np.ndarray:
    if source_rate != target_rate:
        divisor = math.gcd(source_rate, target_rate)
        audio = resample_poly(audio, target_rate // divisor, source_rate // divisor, axis=0).astype(np.float32)
    if frames is not None:
        audio = audio[:frames]
        if len(audio) < frames:
            audio = np.pad(audio, ((0, frames - len(audio)), (0, 0)))
    return np.ascontiguousarray(audio)


def waveform(audio: np.ndarray, count: int = 180) -> list[float]:
    mono = np.max(np.abs(audio), axis=1)
    return [round(float(np.max(chunk)), 5) if len(chunk) else 0.0 for chunk in np.array_split(mono, count)]


def validate_gains(gains: dict) -> dict[str, float]:
    if set(gains) != set(STEMS):
        raise ValueError("Choose a level for dialogue, music, and sound effects.")
    result = {key: float(gains[key]) for key in STEMS}
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in result.values()):
        raise ValueError("Track levels must be between 0 and 100 percent.")
    return result


def render_layers(job_dir: Path, report: dict, gains: dict) -> tuple[np.ndarray, np.ndarray]:
    audio = np.zeros((report["frames"], report["channels"]), dtype=np.float32)
    removed = np.zeros_like(audio)
    for stem in STEMS:
        values, rate = sf.read(job_dir / "work" / f"{stem}.wav", dtype="float32", always_2d=True)
        if values.shape != audio.shape or rate != report["sample_rate"]:
            raise ValueError("A saved stem is incomplete. Separate the source again.")
        audio += values * gains[stem]
        removed += values * (1 - gains[stem])
    audio *= report["output_gain"]
    removed *= report["output_gain"]
    return audio, removed


def export_mix(job_dir: Path, gains: dict) -> dict:
    """Render kept and excluded layers; every mix is an immutable revision."""
    gains = validate_gains(gains)
    report = read_json(job_dir / "separation.json")
    audio, removed = render_layers(job_dir, report, gains)
    revision = uuid.uuid4().hex[:12]
    mix_name = f"cleaned-{revision}.wav"
    removed_name = f"removed-{revision}.wav"
    bundle_name = f"soundshredder-{revision}.zip"
    report_name = f"report-{revision}.json"
    output = job_dir / "output"
    sf.write(output / mix_name, audio, report["sample_rate"], subtype="PCM_24")
    sf.write(output / removed_name, removed, report["sample_rate"], subtype="PCM_24")
    info = sf.info(output / mix_name)
    if (info.frames, info.samplerate, info.channels) != (report["frames"], report["sample_rate"], report["channels"]):
        raise RuntimeError("Output timing verification failed.")
    details = {
        **report,
        "mix_levels": gains,
        "mix_file": mix_name,
        "removed_file": removed_name,
        "removed_definition": "Excluded portions of the separated stems at the shared output gain; does not include model residual or source-level normalization.",
        "mix_peak": float(np.max(np.abs(audio))),
        "timing_verified": True,
    }
    write_json(output / report_name, details)
    with zipfile.ZipFile(output / bundle_name, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.write(output / mix_name, "Cleaned mix.wav")
        archive.write(output / removed_name, "Removed sounds.wav")
        for stem in STEMS:
            archive.write(output / f"{stem}.wav", f"{LABELS[stem]}.wav")
        archive.write(output / report_name, "separation-report.json")
    result = {
        "mix": mix_name,
        "removed": removed_name,
        "bundle": bundle_name,
        "report": report_name,
        "gains": gains,
        "waveform": waveform(audio),
        "removed_waveform": waveform(removed),
        "revision": revision,
    }
    write_json(job_dir / "mix.json", result)
    return result
