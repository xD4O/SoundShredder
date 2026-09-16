"""Prepare independent audition tracks without changing the user's cleaned mix."""

from __future__ import annotations

import argparse
import gc
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf

from .audio import STEMS, read_json, render_layers, resample, sha256, validate_gains, waveform, write_json
from .engine import MODEL_RATE, choose_device, run_model


def manifest(directory: Path) -> dict:
    mix = read_json(directory / "mix.json")
    report = read_json(directory / "separation.json")
    state_path = directory / "listening.json"
    state = read_json(state_path) if state_path.is_file() else {}
    is_bubble = report.get("mode") == "bubble"
    ready = not is_bubble or state.get("status") == "complete"
    peaks = state.get("waveforms", {}) if is_bubble else (report.get("stem_waveforms") or state.get("waveforms", {}))
    tracks = {}
    for stem in STEMS:
        filename = f"{stem}.wav"
        tracks[stem] = {"file": filename if ready and (directory / "output" / filename).is_file() else None,
                        "waveform": peaks.get(stem)}
    removed = mix.get("removed") or f"removed-{mix['revision']}.wav"
    removed_peaks = mix.get("removed_waveform")
    if removed_peaks is None and state.get("mix_revision") == mix["revision"]:
        removed_peaks = state.get("removed_waveform")
    tracks["removed"] = {"file": removed if (directory / "output" / removed).is_file() else None,
                         "waveform": removed_peaks}
    missing = [name for name, track in tracks.items() if not track["file"]]
    status = state.get("status", "idle")
    if not missing and status != "running":
        status = "complete"
    return {"status": status, "progress": state.get("progress", 0), "message": state.get("message", ""),
            "tracks": tracks, "missing": missing, "mix_revision": mix["revision"],
            "basis": "original", "removed_definition": "Estimated bubble sound removed from the original." if is_bubble
            else "Excluded portions of the separated tracks at your last exported levels."}


def prepare(directory: Path) -> None:
    request = read_json(directory / "request.json")
    state = read_json(directory / "listening.json")
    report = read_json(directory / "separation.json")
    mix = read_json(directory / "mix.json")
    output = directory / "output"
    peaks, warnings = {}, []
    device = None

    def progress(amount, message, **_extra):
        write_json(directory / "listening.json", {**state, "status": "running", "progress": amount,
                                                 "message": message})

    if state.get("generate_stems"):
        import torch

        original = output / "original.wav"
        before = sha256(original)
        audio, rate = sf.read(original, dtype="float32", always_2d=True)
        model_audio = resample(audio, rate, MODEL_RATE)
        device = choose_device(request["device"])
        try:
            values = run_model(model_audio, device, progress)
        except Exception as exc:
            if device != "cuda" or not request.get("cpu_fallback", True) or not (
                isinstance(exc, torch.cuda.OutOfMemoryError) or "out of memory" in str(exc).lower()
            ):
                raise
            traceback.clear_frames(exc.__traceback__)
            gc.collect()
            torch.cuda.empty_cache()
            device = "cpu"
            warnings.append("GPU memory filled up; isolated tracks were prepared on CPU.")
            progress(0.05, "GPU memory is full. Preparing listening tracks on CPU.")
            values = run_model(model_audio, device, progress)
        values = {name: resample(values[name], MODEL_RATE, rate, len(audio)) for name in STEMS}
        bound = np.zeros_like(audio)
        for samples in values.values():
            if not np.isfinite(samples).all():
                raise ValueError("The separation model returned invalid samples.")
            bound += np.abs(samples)
        gain = min(1.0, 0.98 / max(float(np.max(bound)), 1e-9))
        for name, samples in values.items():
            sf.write(output / f"{name}.wav", samples * gain, rate, subtype="PCM_24")
            info = sf.info(output / f"{name}.wav")
            if (info.frames, info.samplerate, info.channels) != (len(audio), rate, audio.shape[1]):
                raise RuntimeError("Listening-track timing verification failed.")
            peaks[name] = waveform(samples * gain)
        if sha256(original) != before:
            raise RuntimeError("The original preview changed during track preparation.")
    else:
        for name in STEMS:
            filename = output / f"{name}.wav"
            if filename.is_file():
                samples, _ = sf.read(filename, dtype="float32", always_2d=True)
                peaks[name] = waveform(samples)

    # Older layer-separation sessions may predate removed-sound exports.
    removed = mix.get("removed") or f"removed-{mix['revision']}.wav"
    if not (output / removed).is_file():
        if report.get("mode") == "bubble":
            raise ValueError("The removed-sound file is missing. Update the cleanup mix to recreate it.")
        _, samples = render_layers(directory, report, validate_gains(mix["gains"]))
        sf.write(output / removed, samples, report["sample_rate"], subtype="PCM_24")
    removed_audio, _ = sf.read(output / removed, dtype="float32", always_2d=True)
    write_json(directory / "listening.json", {
        "status": "complete", "progress": 1, "message": "Your isolated tracks are ready.",
        "waveforms": peaks, "removed_waveform": waveform(removed_audio), "mix_revision": mix["revision"],
        "device": device, "warnings": warnings, "basis": "original", "timing_verified": True,
    })


def main():
    parser = argparse.ArgumentParser(description="Prepare tracks for the listening panel")
    parser.add_argument("job_dir", type=Path)
    directory = parser.parse_args().job_dir
    try:
        prepare(directory)
    except Exception as exc:
        traceback.print_exc()
        write_json(directory / "listening.json", {"status": "failed", "progress": 0, "message": str(exc)[:1200]})
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
