"""Bandit v2 adapter. This module is imported only inside the job subprocess."""

from __future__ import annotations

import gc
import os
from collections.abc import Callable

import numpy as np

from .audio import STEMS
from .certificates import configure_macos_certificates

MODEL_RATE = 48000
BLOCK_SECONDS = 20
OVERLAP_SECONDS = 2


def infer_active_windows(runtime, audio: np.ndarray, on_pass: Callable[[int, int], None]) -> dict[str, np.ndarray]:
    """Keep upstream padding/window math; skip windows cropped out of its final output.

    Bandit is stateless between windows. A window wholly outside [front_pad,
    front_pad + frames) cannot contribute to any exported sample. Accumulating
    just the intersecting samples also avoids keeping every prediction on GPU.
    The adapter is pinned; tests compare this against its native fold handler.
    """
    import torch

    handler = runtime.handler
    mixture = torch.from_numpy(np.ascontiguousarray(audio.T)).to(runtime.device)[None]
    with torch.inference_mode():
        windows, frames, _ = handler._pad_and_unfold(mixture)
        channels = audio.shape[1]
        left = handler.front_pad_samples
        right = left + frames
        chunk = handler.chunk_size_samples
        hop = handler.hop_size_samples
        indices = [i for i in range(windows.shape[1]) if i * hop < right and i * hop + chunk > left]
        accum = {name: torch.zeros((channels, frames), device=runtime.device) for name in runtime.model.stems}
        window = handler.scaled_window.reshape(1, chunk)
        for count, index in enumerate(indices, 1):
            prediction = runtime.model(
                {"mixture": {"audio": windows[:, index : index + 1].reshape(channels, 1, chunk)}}
            )
            start = index * hop
            lo, hi = max(start, left), min(start + chunk, right)
            for name in runtime.model.stems:
                values = prediction["estimates"][name]["audio"].reshape(channels, chunk)
                accum[name][:, lo - left : hi - left] += (values * window)[:, lo - start : hi - start]
            del prediction
            on_pass(count, len(indices))
        return {
            "speech": accum["speech"].T.cpu().numpy(),
            "music": accum["music"].T.cpu().numpy(),
            "effects": accum["sfx"].T.cpu().numpy(),
        }


def choose_device(requested: str) -> str:
    import torch

    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError("Choose Auto, CPU, or NVIDIA GPU.")
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError(
            "NVIDIA GPU is unavailable. Choose CPU, or run Setup NVIDIA GPU.bat and update your NVIDIA driver."
        )
    return (
        "cuda" if requested == "auto" and torch.cuda.is_available() else ("cpu" if requested == "auto" else requested)
    )


def run_model(audio: np.ndarray, device: str, progress: Callable[[float, str], None]) -> dict[str, np.ndarray]:
    """Bound accelerator memory using blocks and crossfade their overlapping edges."""
    configure_macos_certificates()
    import torch
    from bandit_infer import BanditSession

    torch.set_num_threads(max(1, min(8, (os.cpu_count() or 2) // 2)))
    block = BLOCK_SECONDS * MODEL_RATE
    overlap = OVERLAP_SECONDS * MODEL_RATE
    step = block - overlap
    starts = [0]
    while starts[-1] + block < len(audio):
        starts.append(starts[-1] + step)
    output = {name: np.zeros_like(audio) for name in STEMS}
    weights = np.zeros((len(audio), 1), dtype=np.float32)
    progress(0.08, "Loading Bandit v2. First use downloads the model (about 426 MB).")
    with BanditSession("v2-multi", device=device) as session:
        for index, start in enumerate(starts):
            stop = min(start + block, len(audio))
            segment = audio[start:stop]

            def tick(counter, expected, index=index):
                fraction = (index + counter / expected) / len(starts)
                progress(
                    0.12 + 0.76 * fraction,
                    f"Separating on {'GPU' if device == 'cuda' else 'CPU'} · block {index + 1}/{len(starts)} · pass {counter}/{expected}",
                )

            prediction = infer_active_windows(session._runtime, segment, tick)
            window = np.ones((len(segment), 1), dtype=np.float32)
            if start:
                n = min(overlap, len(segment))
                window[:n, 0] *= np.linspace(0, 1, n, dtype=np.float32)
            if stop < len(audio):
                n = min(overlap, len(segment))
                window[-n:, 0] *= np.linspace(1, 0, n, dtype=np.float32)
            for stem in STEMS:
                values = prediction[stem]
                if values.shape != segment.shape or not np.isfinite(values).all():
                    raise RuntimeError(f"The model returned invalid {stem} samples.")
                output[stem][start:stop] += values * window
            weights[start:stop] += window
    if np.any(weights <= 0):
        raise RuntimeError("Audio overlap coverage failed.")
    for stem in STEMS:
        output[stem] /= weights
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    return output
