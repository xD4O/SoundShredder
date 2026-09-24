"""Prompt-guided cleanup with bounded previews and immutable session versions."""
from __future__ import annotations

import gc
import math
import time
import traceback
import uuid
import zipfile

import numpy as np
import soundfile as sf

from . import bubble
from .audio import resample, sha256, waveform, write_json
from .engine import choose_device
from .prompts import prompt_vector, validate_prompt

PREVIEW_SECONDS = 10
CONTEXT_SECONDS = 2


def validate_settings(prompt, strength=0.85, start=0, end=None, passes=1):
    prompt = validate_prompt(prompt)
    if isinstance(passes, bool) or not isinstance(passes, int) or not 1 <= passes <= 4:
        raise ValueError("Choose between 1 and 4 cleanup passes.")
    strength, start = float(strength), float(start)
    end = None if end is None else float(end)
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("Removal strength must be between 0 and 100 percent.")
    if not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
        raise ValueError("Choose a time range with its end after its start.")
    return dict(prompt=prompt, strength=strength, start=start, end=end, passes=passes)


def process_targeted(job_dir, audio, rate, source_info, request, started, progress, original_hash):
    import torch

    settings = validate_settings(**request["cleanup"])
    lo, hi = bubble.selection_bounds(audio, rate, settings)
    preview = request.get("preview", False)
    if preview:
        hi = min(hi, lo + PREVIEW_SECONDS * rate)
    applied = {**settings, "start": lo / rate, "end": hi / rate}
    # Always retain full-length exports for video sync. Only infer the selection
    # with context; the unselected decoded samples are never modified.
    context_lo = max(0, lo - CONTEXT_SECONDS * rate)
    context_hi = min(len(audio), hi + CONTEXT_SECONDS * rate)
    selected = choose_device(request["device"])
    warnings = ["Experimental: similar or overlapping wanted sounds may also be reduced. Listen to Removed sounds."]
    if preview:
        warnings.append(f"Preview only: {lo / rate:.2f}–{hi / rate:.2f} seconds. Audio outside this interval is unchanged.")
    if settings["passes"] > 1:
        warnings.append("Each pass repeats cleanup on the previous result. More passes may remove wanted detail.")
    current = audio.copy()
    details = []
    model = None
    if settings["strength"] > 0 and np.any(audio[context_lo:context_hi]):
        path = bubble.checkpoint(progress)
        vector = prompt_vector(settings["prompt"], path, progress)
        for index in range(settings["passes"]):
            label = f"{'Preview' if preview else 'Cleanup'} · pass {index + 1}/{settings['passes']}"

            def pass_progress(amount, message, *, index=index, label=label):
                fraction = min(1, max(0, (amount - 0.2) / 0.62))
                progress(0.2 + 0.65 * (index + 0.9 * fraction) / settings["passes"], f"{label} · {message}")

            segment = current[context_lo:context_hi]
            model_audio = resample(segment, rate, bubble.MODEL_RATE)
            try:
                if model is None:
                    progress(0.2 + 0.65 * index / settings["passes"], f"{label} · loading the sound model.")
                    model = bubble.load_model(path, selected)
                target = bubble.estimate_target(model_audio, None, selected, model, pass_progress, vector)
            except Exception as exc:
                if selected != "cuda" or not request.get("cpu_fallback", True) or not (
                    isinstance(exc, torch.cuda.OutOfMemoryError) or "out of memory" in str(exc).lower()
                ):
                    raise
                traceback.clear_frames(exc.__traceback__)
                model = None
                gc.collect()
                torch.cuda.empty_cache()
                selected = "cpu"
                warnings.append(f"GPU memory filled on pass {index + 1}; retried that pass on CPU.")
                pass_progress(0.2, "GPU memory is full. Retrying on CPU.")
                model = bubble.load_model(path, selected)
                target = bubble.estimate_target(model_audio, None, selected, model, pass_progress, vector)
            target = resample(target, bubble.MODEL_RATE, rate, len(segment))
            candidate = np.zeros_like(audio)
            candidate[context_lo:context_hi] = bubble.removal_candidate(segment, target, rate)
            current, removed, _ = bubble.apply_selection(current, candidate, rate, applied)
            if not np.isfinite(current).all():
                raise RuntimeError("The cleanup produced invalid audio. Try a different description.")
            details.append({"pass": index + 1, "device": selected,
                            "removed_rms": float(np.sqrt(np.mean(removed.astype(np.float64) ** 2)))})
            progress(0.2 + 0.65 * (index + 1) / settings["passes"], f"{label} · complete.")
    else:
        warnings.append("No inference needed: this selection is silent or removal strength is zero.")
    del model
    gc.collect()
    if selected == "cuda":
        torch.cuda.empty_cache()
    progress(0.89, "Saving a new cleanup version and verifying the unchanged audio.")
    revision = uuid.uuid4().hex[:12]
    names = {"mix": f"cleaned-{revision}.wav", "removed": f"removed-{revision}.wav",
             "bundle": f"soundshredder-{revision}.zip", "report": f"report-{revision}.json"}
    output = job_dir / "output"
    removed = audio - current
    sf.write(output / names["mix"], current, rate, subtype="FLOAT")
    sf.write(output / names["removed"], removed, rate, subtype="FLOAT")
    stored, stored_rate = sf.read(output / names["mix"], dtype="float32", always_2d=True)
    if stored_rate != rate or stored.shape != audio.shape or not (
        np.array_equal(stored[:lo], audio[:lo]) and np.array_equal(stored[hi:], audio[hi:])
    ):
        raise RuntimeError("Cleanup timing or outside-selection verification failed.")
    if sha256(job_dir / request["source"]) != original_hash:
        raise RuntimeError("The saved source changed during cleanup.")
    report = {**source_info, "mode": "targeted", "model": "AudioSep with local text prompts",
              "model_sha256": bubble.MODEL_SHA, "prompt": settings["prompt"], "cleanup": settings,
              "applied_cleanup": applied, "preview": preview, "passes": settings["passes"],
              "pass_details": details, "device": selected, "requested_device": request["device"],
              "source_sha256": original_hash, "source_unchanged": True, "timing_verified": True,
              "outside_selection_bit_exact": True, "selected_sample_range": [lo, hi],
              "source_basis": request.get("source_basis", "original"), "parent_id": request.get("parent_id"),
              "processing_seconds": round(time.monotonic() - started, 2), "warnings": warnings,
              "output_format": "32-bit float WAV"}
    write_json(job_dir / "separation.json", report)
    write_json(output / names["report"], report)
    with zipfile.ZipFile(output / names["bundle"], "w", compression=zipfile.ZIP_STORED) as archive:
        archive.write(output / names["mix"], "Preview cleanup.wav" if preview else "Targeted cleanup.wav")
        archive.write(output / names["removed"], "Removed sound.wav")
        archive.write(output / names["report"], "cleanup-report.json")
    write_json(job_dir / "mix.json", {**names, "mode": "targeted", "revision": revision, "cleanup": settings,
                                     "applied_cleanup": applied, "preview": preview,
                                     "gains": dict(speech=1, music=1, effects=1),
                                     "waveform": waveform(current), "removed_waveform": waveform(removed)})
    write_json(job_dir / "progress.json", {"status": "complete", "progress": 1, "device": selected,
                                          "message": "Preview ready." if preview else "Your new cleanup version is ready."})
