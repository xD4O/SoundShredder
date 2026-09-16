"""An isolated, cancellable separation process with atomic progress updates."""

from __future__ import annotations

import argparse
import gc
import time
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf

from .audio import STEMS, decode, export_mix, read_json, resample, sha256, waveform, write_json
from .engine import BLOCK_SECONDS, MODEL_RATE, OVERLAP_SECONDS, choose_device, run_model


def process(job_dir: Path) -> None:
    started = time.monotonic()
    request = read_json(job_dir / "request.json")

    def progress(amount: float, message: str, **extra):
        write_json(job_dir / "progress.json", {"status": "running", "progress": amount, "message": message, **extra})

    progress(0.02, "Reading your audio and checking its duration.")
    work = job_dir / "work"
    output = job_dir / "output"
    work.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    source = job_dir / request["source"]
    original_hash = sha256(source)
    audio, rate = decode(source, work)
    sf.write(output / "original.wav", audio, rate, subtype="FLOAT")
    source_info = {
        "filename": request["filename"],
        "sample_rate": rate,
        "frames": len(audio),
        "channels": audio.shape[1],
        "duration": len(audio) / rate,
        "waveform": waveform(audio),
    }
    write_json(job_dir / "source.json", source_info)
    if request.get("mode") == "bubble":
        from .bubble import process_bubble

        process_bubble(job_dir, audio, rate, source_info, request, started, progress, original_hash)
        return
    model_audio = resample(audio, rate, MODEL_RATE)
    selected = choose_device(request["device"])
    warnings = []
    try:
        stems = run_model(model_audio, selected, progress)
    except Exception as exc:
        import torch

        oom = isinstance(exc, torch.cuda.OutOfMemoryError) or "out of memory" in str(exc).lower()
        if selected != "cuda" or not oom or not request.get("cpu_fallback", True):
            raise
        # Release the failed frame's model references before retrying on CPU.
        traceback.clear_frames(exc.__traceback__)
        gc.collect()
        torch.cuda.empty_cache()
        selected = "cpu"
        warnings.append("GPU ran out of memory. Completed on CPU instead.")
        progress(0.08, "GPU memory is full. Retrying on CPU; this will take longer.")
        stems = run_model(model_audio, selected, progress)
    progress(0.90, "Restoring the source sample rate and exporting your tracks.")
    stems = {key: resample(stems[key], MODEL_RATE, rate, len(audio)) for key in STEMS}
    # A common gain preserves relative stem levels and leaves headroom for every
    # possible mix with sliders in [0, 1], without clipping or per-stem boosts.
    bound = np.zeros_like(audio)
    for values in stems.values():
        bound += np.abs(values)
    peak_bound = float(np.max(bound))
    gain = min(1.0, 0.98 / max(peak_bound, 1e-9))
    for name, values in stems.items():
        sf.write(work / f"{name}.wav", values, rate, subtype="FLOAT")
        sf.write(output / f"{name}.wav", values * gain, rate, subtype="PCM_24")
        info = sf.info(output / f"{name}.wav")
        if (info.frames, info.samplerate, info.channels) != (len(audio), rate, audio.shape[1]):
            raise RuntimeError(f"Timing verification failed for {name}.")
    if sha256(source) != original_hash:
        raise RuntimeError("Source integrity verification failed.")
    residual = audio - sum(stems.values())
    source_rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    residual_rms = float(np.sqrt(np.mean(residual.astype(np.float64) ** 2)))
    diagnostics = {
        "source_rms": source_rms,
        "reconstruction_residual_rms": residual_rms,
        "residual_to_source_db": round(float(20 * np.log10(max(residual_rms, 1e-12) / max(source_rms, 1e-12))), 2),
        "stem_rms": {name: float(np.sqrt(np.mean(values.astype(np.float64) ** 2))) for name, values in stems.items()},
        "interpretation": "Residual measures how closely the stems sum to the input, not separation quality. It is not added back because it may contain removed sounds.",
    }
    report = {
        **source_info,
        "source_sha256": original_hash,
        "source_unchanged": True,
        "model": "Bandit v2 multi",
        "model_sample_rate": MODEL_RATE,
        "inference": {
            "adapter_revision": "7ec03cb568811958db65a96a10fdb8879922b2ac",
            "block_seconds": BLOCK_SECONDS,
            "block_overlap_seconds": OVERLAP_SECONDS,
            "skip_noncontributing_padded_windows": True,
        },
        "requested_device": request["device"],
        "device": selected,
        "output_gain": gain,
        "stem_waveforms": {name: waveform(values * gain) for name, values in stems.items()},
        "output_format": "24-bit PCM WAV",
        "processing_seconds": round(time.monotonic() - started, 2),
        "warnings": warnings,
        "diagnostics": diagnostics,
        "notes": [
            "The source is never overwritten. Output length, sample rate and channels match the decoded source.",
            "AI separation may leave bleed or change quiet effects and breaths. Listen before publishing.",
            "The effects track includes ambience. Individual noises within a track are not separately selectable.",
        ],
    }
    write_json(job_dir / "separation.json", report)
    export_mix(job_dir, request["gains"])
    write_json(
        job_dir / "progress.json",
        {
            "status": "complete",
            "progress": 1,
            "message": "Your tracks are ready. Listen, adjust, and download.",
            "device": selected,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir", type=Path)
    args = parser.parse_args()
    try:
        process(args.job_dir)
    except Exception as exc:
        traceback.print_exc()
        message = str(exc) or type(exc).__name__
        if "out of memory" in message.lower():
            message = "There is not enough memory. Try CPU mode, close other GPU apps, or use a shorter clip."
        write_json(args.job_dir / "progress.json", {"status": "failed", "progress": 0, "message": message[:1200]})
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
