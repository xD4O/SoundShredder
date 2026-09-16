"""Experimental sound-specific cleanup that subtracts from the original mix."""
from __future__ import annotations

import gc
import json
import math
import os
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import istft, stft

from .audio import read_json, resample, sha256, waveform, write_json
from .engine import choose_device

MODEL_RATE = 32000
MAX_PASSES = 4
MODEL_SHA = "f8cda01bfd0ebd141eef45d41db7a3ada23a56568465840d3cff04b8010ce82c"
MODEL_URL = (
    "https://huggingface.co/spaces/Audio-AGI/AudioSep/resolve/"
    "5638854dccfaea5c5fa4f634c00fe74fbb119244/checkpoint/audiosep_base_4M_steps.ckpt"
)
PROMPTS = json.loads((Path(__file__).parent / "_audiosep/bubble-prompts.json").read_text(encoding="utf-8"))


def validate_settings(kind="water", strength=0.85, start=0.0, end=None, passes=1):
    if kind not in PROMPTS:
        raise ValueError("Choose a supported bubble sound type.")
    if isinstance(passes, bool) or not isinstance(passes, int) or not 1 <= passes <= MAX_PASSES:
        raise ValueError(f"Choose between 1 and {MAX_PASSES} cleanup passes.")
    if passes > 1 and kind != "water":
        raise ValueError("Multi-pass cleanup is available for Water bubbles only.")
    strength, start = float(strength), float(start)
    end = None if end is None else float(end)
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("Bubble reduction must be between 0 and 100 percent.")
    if not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
        raise ValueError("Choose a valid time range: end must be after start.")
    return {"kind": kind, "strength": strength, "start": start, "end": end, "passes": passes}


def checkpoint(progress):
    folder = Path.home() / ".cache/soundshredder/audiosep"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "audiosep_base_4M_steps.ckpt"
    if path.is_file() and sha256(path) == MODEL_SHA:
        return path
    temporary = folder / f"audiosep-{os.getpid()}.part"
    try:
        progress(0.05, "First bubble cleanup downloads AudioSep (about 1.2 GB). Your audio stays local.")
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response, temporary.open("wb") as output:
            total = int(response.headers.get("Content-Length", 1264844076))
            received, next_update = 0, 0
            while chunk := response.read(4 * 1024 * 1024):
                output.write(chunk)
                received += len(chunk)
                if received >= next_update:
                    progress(0.05 + 0.12 * min(1, received / total), f"Downloading bubble model: {received // 1048576} / {total // 1048576} MB")
                    next_update = received + 32 * 1024 * 1024
        if sha256(temporary) != MODEL_SHA:
            raise RuntimeError("The bubble model download did not pass verification. Retry cleanup.")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def load_model(path, device):
    import torch

    from ._audiosep.resunet import ResUNet30

    model = ResUNet30(1, 1, 512)
    state = torch.load(path, map_location="cpu", weights_only=True)["state_dict"]
    # The frozen Fourier kernels are replaced by equivalent native transforms.
    state = {
        k.removeprefix("ss_model."): v for k, v in state.items()
        if k.startswith("ss_model.") and not k.startswith(("ss_model.base.stft.", "ss_model.base.istft."))
    }
    model.load_state_dict(state, strict=True)
    return model.eval().to(device)


def estimate_target(audio, kind, device, model, progress):
    import torch

    torch.set_num_threads(max(1, min(8, (os.cpu_count() or 2) // 2)))
    block, overlap = 5 * MODEL_RATE, MODEL_RATE
    starts = [0]
    while starts[-1] + block < len(audio):
        starts.append(starts[-1] + block - overlap)
    target, weights = np.zeros_like(audio), np.zeros((len(audio), 1), np.float32)
    condition = torch.tensor(PROMPTS[kind]["vector"], device=device)[None]
    with torch.inference_mode():
        for index, start in enumerate(starts):
            stop = min(start + block, len(audio))
            segment = audio[start:stop]
            padded = np.pad(segment, ((0, max(0, 2048 - len(segment))), (0, 0)))
            channels = []
            # Separate channels serially to bound VRAM on smaller GPUs.
            for channel in range(audio.shape[1]):
                signal = torch.from_numpy(padded[:, channel].copy()).to(device)[None, None]
                predicted = model({"mixture": signal, "condition": condition})["waveform"]
                channels.append(predicted[0, 0, :len(segment)].cpu().numpy())
                progress(0.2 + 0.62 * (index + (channel + 1) / audio.shape[1]) / len(starts),
                         f"Finding bubble sounds on {'GPU' if device == 'cuda' else 'CPU'} · block {index + 1}/{len(starts)} · channel {channel + 1}/{audio.shape[1]}")
            values = np.stack(channels, axis=1)
            if not np.isfinite(values).all():
                raise RuntimeError("The bubble model returned invalid audio.")
            window = np.ones((len(segment), 1), np.float32)
            if start:
                n = min(overlap, len(segment))
                window[:n, 0] *= np.linspace(0, 1, n, dtype=np.float32)
            if stop < len(audio):
                window[-overlap:, 0] *= np.linspace(1, 0, overlap, dtype=np.float32)
            target[start:stop] += values * window
            weights[start:stop] += window
    if np.any(weights <= 0):
        raise RuntimeError("Bubble model overlap coverage failed.")
    return target / weights


def removal_candidate(original, estimate, rate):
    """Apply a shared stereo mask with original phase; no synthesized background."""
    if estimate.shape != original.shape or not np.isfinite(estimate).all():
        raise ValueError("The bubble estimate does not match the source.")
    nfft = 2 ** math.ceil(math.log2(0.064 * rate))
    hop = nfft // 4
    block, overlap = 8 * rate, rate // 4
    output, weights = np.zeros_like(original), np.zeros((len(original), 1), np.float32)
    starts = [0]
    while starts[-1] + block < len(original):
        starts.append(starts[-1] + block - overlap)
    for start in starts:
        stop = min(start + block, len(original))
        length = stop - start
        padding = ((0, max(0, nfft - length)), (0, 0))
        source = np.pad(original[start:stop], padding).T
        target = np.pad(estimate[start:stop], padding).T
        _, _, mix_spec = stft(source, fs=rate, nperseg=nfft, noverlap=nfft - hop)
        _, _, target_spec = stft(target, fs=rate, nperseg=nfft, noverlap=nfft - hop)
        target_power = np.sum(np.abs(target_spec) ** 2, axis=0)
        other_power = np.sum(np.abs(mix_spec - target_spec) ** 2, axis=0)
        mask = np.clip(target_power / (target_power + other_power + 1e-12), 0, 1)
        _, removed = istft(mix_spec * mask[None], fs=rate, nperseg=nfft, noverlap=nfft - hop)
        window = np.ones((length, 1), np.float32)
        if start:
            window[:overlap, 0] *= np.linspace(0, 1, overlap, dtype=np.float32)
        if stop < len(original):
            window[-overlap:, 0] *= np.linspace(1, 0, overlap, dtype=np.float32)
        output[start:stop] += removed.T[:length] * window
        weights[start:stop] += window
    return output / weights


def selection_bounds(original, rate, settings):
    duration = len(original) / rate
    start = settings["start"]
    end = duration if settings["end"] is None else settings["end"]
    if start >= duration or end > duration + 1 / rate:
        raise ValueError(f"The selected range is outside this {duration:.3f}-second clip.")
    lo, hi = round(start * rate), min(len(original), round(end * rate))
    if hi <= lo:
        raise ValueError("Choose a time range at least one sample long.")
    return lo, hi


def apply_selection(original, candidate, rate, settings):
    lo, hi = selection_bounds(original, rate, settings)
    removed = np.zeros_like(original)
    removed[lo:hi] = candidate[lo:hi] * settings["strength"]
    # Fades live entirely inside the selected interval. Outside samples are copied.
    fade = min(round(0.04 * rate), (hi - lo) // 2)
    if fade and lo:
        removed[lo:lo + fade] *= np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    if fade and hi < len(original):
        removed[hi - fade:hi] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    cleaned = original.copy()
    cleaned[lo:hi] -= removed[lo:hi]
    return cleaned, removed, (lo, hi)


def export_cleanup(job_dir, strength, start=0, end=None, passes=None):
    report = read_json(job_dir / "separation.json")
    completed_passes = report.get("passes", 1)
    settings = validate_settings(report["bubble_type"], strength, start, end,
                                 completed_passes if passes is None else passes)
    if settings["passes"] != completed_passes or (completed_passes > 1 and settings != report.get("analysis_cleanup")):
        raise ValueError("Multi-pass settings changed. Run cleanup again so each pass uses the new settings.")
    original, rate = sf.read(job_dir / "output/original.wav", dtype="float32", always_2d=True)
    candidate, candidate_rate = sf.read(job_dir / "work/bubble-candidate.wav", dtype="float32", always_2d=True)
    if candidate_rate != rate or candidate.shape != original.shape:
        raise ValueError("The saved bubble estimate is incomplete. Run cleanup again.")
    if completed_passes > 1:
        # The saved candidate already contains every pass's strength and in-range
        # fades. Applying them again would double-process the selection edges.
        lo, hi = selection_bounds(original, rate, settings)
        removed = candidate
        cleaned = original - removed
    else:
        cleaned, removed, (lo, hi) = apply_selection(original, candidate, rate, settings)
    if not np.isfinite(cleaned).all():
        raise ValueError("Bubble cleanup produced invalid audio.")
    revision = uuid.uuid4().hex[:12]
    names = {"mix": f"cleaned-{revision}.wav", "removed": f"removed-{revision}.wav",
             "bundle": f"soundshredder-{revision}.zip", "report": f"report-{revision}.json"}
    output = job_dir / "output"
    for key, values in (("mix", cleaned), ("removed", removed)):
        sf.write(output / names[key], values, rate, subtype="FLOAT")
    stored, stored_rate = sf.read(output / names["mix"], dtype="float32", always_2d=True)
    preserved = np.array_equal(stored[:lo], original[:lo]) and np.array_equal(stored[hi:], original[hi:])
    if stored_rate != rate or stored.shape != original.shape or not preserved:
        raise RuntimeError("Bubble cleanup timing or outside-selection verification failed.")
    details = {**report, "cleanup": settings, "mix_file": names["mix"], "removed_file": names["removed"],
               "mix_peak": float(np.max(np.abs(cleaned))), "timing_verified": True,
               "outside_selection_bit_exact": preserved, "selected_sample_range": [lo, hi],
               "removed_rms": float(np.sqrt(np.mean(removed.astype(np.float64) ** 2)))}
    write_json(output / names["report"], details)
    with zipfile.ZipFile(output / names["bundle"], "w", compression=zipfile.ZIP_STORED) as archive:
        archive.write(output / names["mix"], "Bubble cleanup.wav")
        archive.write(output / names["removed"], "Removed sound - check this.wav")
        archive.write(output / names["report"], "cleanup-report.json")
    result = {**names, "mode": "bubble", "cleanup": settings, "revision": revision,
              "gains": dict(speech=1, music=1, effects=1), "waveform": waveform(cleaned),
              "removed_waveform": waveform(removed)}
    write_json(job_dir / "mix.json", result)
    return result


def process_bubble(job_dir, audio, rate, source_info, request, started, progress, original_hash):
    import torch

    settings = validate_settings(**request["cleanup"])
    # Validate the selected interval before any model download or inference.
    selection_bounds(audio, rate, settings)
    selected = choose_device(request["device"])
    path = checkpoint(progress)
    progress(0.18, "Loading the bubble sound model. Other sounds remain in the original mix.")
    warnings = ["Experimental: similar pops, liquid sounds, or other effects may be reduced. Listen to the removed-sound preview."]
    if settings["passes"] > 1:
        warnings.append("Aggressive multi-pass cleanup can also reduce wanted effects. Compare the original and combined removed-sound track.")
    current = audio.copy()
    model = None
    pass_details = []
    for index in range(settings["passes"]):
        label = f"Bubble cleanup · pass {index + 1}/{settings['passes']}"

        def pass_progress(amount, message, *, index=index, label=label):
            fraction = min(1, max(0, (amount - 0.2) / 0.62))
            progress(0.2 + 0.65 * (index + 0.9 * fraction) / settings["passes"], f"{label} · {message}")

        # Re-infer from the actual previous result, with strength and range already
        # applied. This is not repeated attenuation of the first prediction.
        model_audio = resample(current, rate, MODEL_RATE)
        try:
            if model is None:
                model = load_model(path, selected)
            target = estimate_target(model_audio, settings["kind"], selected, model, pass_progress)
        except Exception as exc:
            import traceback

            if selected != "cuda" or not request.get("cpu_fallback", True) or not (
                isinstance(exc, torch.cuda.OutOfMemoryError) or "out of memory" in str(exc).lower()
            ):
                raise
            traceback.clear_frames(exc.__traceback__)
            model = None
            gc.collect()
            torch.cuda.empty_cache()
            selected = "cpu"
            warnings.append(f"GPU ran out of memory on pass {index + 1}. Retried that pass on CPU.")
            model = load_model(path, selected)
            target = estimate_target(model_audio, settings["kind"], selected, model, pass_progress)
        progress(0.2 + 0.65 * (index + 0.95) / settings["passes"], f"{label} · applying reduction inside the selected range.")
        target = resample(target, MODEL_RATE, rate, len(audio))
        candidate = removal_candidate(current, target, rate)
        current, removed, _ = apply_selection(current, candidate, rate, settings)
        if not np.isfinite(current).all():
            raise RuntimeError("Bubble cleanup produced invalid audio.")
        pass_details.append({"pass": index + 1, "device": selected,
                             "removed_rms": float(np.sqrt(np.mean(removed.astype(np.float64) ** 2)))})
        progress(0.2 + 0.65 * (index + 1) / settings["passes"], f"{label} · complete.")
    del model
    gc.collect()
    if selected == "cuda":
        torch.cuda.empty_cache()
    progress(0.88, "Preserving the original stereo image and preparing the removed-sound preview.")
    if settings["passes"] > 1:
        candidate = audio - current
    sf.write(job_dir / "work/bubble-candidate.wav", candidate, rate, subtype="FLOAT")
    if sha256(job_dir / request["source"]) != original_hash:
        raise RuntimeError("Source integrity verification failed.")
    report = {
        **source_info, "mode": "bubble", "bubble_type": settings["kind"],
        "passes": settings["passes"], "analysis_cleanup": settings, "pass_details": pass_details,
        "model": "AudioSep - fixed bubble sound prompt", "prompt": PROMPTS[settings["kind"]]["prompt"],
        "model_sha256": MODEL_SHA, "model_sample_rate": MODEL_RATE,
        "source_sha256": original_hash, "source_unchanged": True,
        "device": selected, "requested_device": request["device"], "output_format": "32-bit float WAV",
        "processing_seconds": round(time.monotonic() - started, 2), "warnings": warnings,
        "notes": ["Only the estimated target is subtracted from the original mix; Bandit stem reconstruction is not used.",
                  "Outside the selected interval, decoded source samples are preserved exactly in the float WAV.",
                  "Numerical preservation outside a range does not prove that all other sounds inside it are untouched."],
    }
    write_json(job_dir / "separation.json", report)
    export_cleanup(job_dir, settings["strength"], settings["start"], settings["end"], settings["passes"])
    write_json(job_dir / "progress.json", {"status": "complete", "progress": 1, "device": selected,
                                          "message": "Bubble cleanup is ready. Audition the removed sound before using the mix."})
