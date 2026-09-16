import zipfile

import numpy as np
import pytest
import soundfile as sf

from soundshredder import bubble, worker
from soundshredder.audio import read_json, sha256, write_json


@pytest.mark.parametrize("settings", [
    {"strength": -0.1}, {"strength": 1.1}, {"strength": float("nan")},
    {"start": -1}, {"end": float("inf")}, {"start": 4, "end": 3}, {"kind": "unknown"},
    {"passes": 0}, {"passes": 5}, {"passes": 2.5}, {"passes": True},
    {"kind": "popping", "passes": 2}, {"kind": "gurgling", "passes": 3}, {"kind": "cartoon", "passes": 4},
])
def test_invalid_settings(settings):
    with pytest.raises(ValueError):
        bubble.validate_settings(**settings)


def test_selected_samples_only_and_zero_reduction():
    original = np.random.default_rng(3).normal(size=(10000, 2)).astype(np.float32)
    candidate = original * 0.3
    settings = bubble.validate_settings(start=0.25, end=0.75)
    cleaned, removed, (lo, hi) = bubble.apply_selection(original, candidate, 10000, settings)
    assert (lo, hi) == (2500, 7500)
    assert np.array_equal(cleaned[:lo], original[:lo])
    assert np.array_equal(cleaned[hi:], original[hi:])
    assert not removed[:lo].any() and not removed[hi:].any()
    np.testing.assert_allclose(cleaned + removed, original, atol=3e-7)
    bypass = bubble.apply_selection(original, candidate, 10000, {**settings, "strength": 0})[0]
    assert np.array_equal(bypass, original)
    with pytest.raises(ValueError, match="outside"):
        bubble.apply_selection(original, candidate, 10000, {**settings, "end": 2})


@pytest.mark.parametrize("rate", [8000, 44100])
def test_spectral_mask_keeps_unrelated_tone_and_stereo_with_overlap(rate):
    # Opposite-phase stereo cannot be estimated by a mono average. >8 s crosses a mask block boundary.
    t = np.arange(int(8.6 * rate)) / rate
    target = (0.25 * np.sin(2 * np.pi * 700 * t)).astype(np.float32)
    wanted = (0.2 * np.sin(2 * np.pi * 2300 * t)).astype(np.float32)
    original = np.stack([wanted + target, -(wanted + target)], axis=1)
    estimate = np.stack([target, -target], axis=1)
    removed = bubble.removal_candidate(original, estimate, rate)
    error = (original - removed)[rate:-rate, 0] - wanted[rate:-rate]
    assert np.sqrt(np.mean(error ** 2)) < 0.002
    np.testing.assert_allclose(removed[:, 0], -removed[:, 1], atol=1e-6)
    assert np.isfinite(removed).all()


@pytest.mark.parametrize("frames", [101, 160001, 321777])
def test_inference_overlap_and_tiny_input(monkeypatch, frames):
    class Identity:
        def __call__(self, inputs):
            return {"waveform": inputs["mixture"]}

    values = np.random.default_rng(4).normal(0, 0.1, (frames, 2)).astype(np.float32)
    result = bubble.estimate_target(values, "water", "cpu", Identity(), lambda *_: None)
    np.testing.assert_allclose(result, values, atol=1e-7)


def test_native_fourier_roundtrip():
    import torch

    from soundshredder._audiosep.transforms import ISTFT, STFT

    args = dict(n_fft=2048, hop_length=320, win_length=2048, window="hann", center=True,
                pad_mode="reflect", freeze_parameters=True)
    values = torch.randn(2, 5177) * 0.2
    real, imag = STFT(**args)(values)
    restored = ISTFT(**args)(real, imag, values.shape[-1])
    torch.testing.assert_close(restored, values, atol=2e-7, rtol=1e-5)


def test_worker_bubble_export_remix_and_float_preservation(tmp_path, monkeypatch):
    original = np.random.default_rng(6).normal(0, 0.1, (16000, 2)).astype(np.float32)
    original[0, 0] = 1.25  # Do not normalize or clip samples outside the selection.
    sf.write(tmp_path / "source.wav", original, 32000, subtype="FLOAT")
    digest = sha256(tmp_path / "source.wav")
    write_json(tmp_path / "request.json", dict(source="source.wav", filename="clip.wav", mode="bubble",
               device="cpu", cleanup=bubble.validate_settings(start=0.1, end=0.4), gains=dict(speech=1, music=0, effects=0)))
    monkeypatch.setattr(bubble, "checkpoint", lambda _: tmp_path / "dummy")
    monkeypatch.setattr(bubble, "load_model", lambda *_: None)
    monkeypatch.setattr(bubble, "estimate_target", lambda values, *_: values * 0.5)
    monkeypatch.setattr(worker, "run_model", lambda *_: pytest.fail("Bandit must not run for bubble cleanup"))
    worker.process(tmp_path)
    mix = read_json(tmp_path / "mix.json")
    report = read_json(tmp_path / "output" / mix["report"])
    assert report["outside_selection_bit_exact"] and report["timing_verified"]
    assert sha256(tmp_path / "source.wav") == digest
    cleaned, rate = sf.read(tmp_path / "output" / mix["mix"], dtype="float32", always_2d=True)
    removed, _ = sf.read(tmp_path / "output" / mix["removed"], dtype="float32", always_2d=True)
    assert cleaned.shape == original.shape and rate == 32000
    assert cleaned[0, 0] == 1.25
    np.testing.assert_allclose(cleaned + removed, original, atol=1e-7)
    assert sf.info(tmp_path / "output" / mix["mix"]).subtype == "FLOAT"
    with zipfile.ZipFile(tmp_path / "output" / mix["bundle"]) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == 3
    revision = bubble.export_cleanup(tmp_path, 0, 0, None)
    bypass, _ = sf.read(tmp_path / "output" / revision["mix"], dtype="float32", always_2d=True)
    assert np.array_equal(bypass, original)
    assert revision["revision"] != mix["revision"]
    assert (tmp_path / "output" / mix["mix"]).is_file()


def test_bubble_gpu_failure_retries_cpu(tmp_path, monkeypatch):
    import torch

    sf.write(tmp_path / "source.wav", np.zeros((3000, 1), np.float32), 32000)
    write_json(tmp_path / "request.json", dict(source="source.wav", filename="clip.wav", mode="bubble",
               device="cuda", cpu_fallback=True, cleanup=bubble.validate_settings()))
    monkeypatch.setattr(bubble, "choose_device", lambda _: "cuda")
    monkeypatch.setattr(bubble, "checkpoint", lambda _: tmp_path / "dummy")
    monkeypatch.setattr(bubble, "load_model", lambda *_: None)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    calls = []

    def predict(values, kind, device, *_):
        calls.append(device)
        if device == "cuda":
            raise torch.cuda.OutOfMemoryError("test OOM")
        return np.zeros_like(values)

    monkeypatch.setattr(bubble, "estimate_target", predict)
    worker.process(tmp_path)
    assert calls == ["cuda", "cpu"]
    assert read_json(tmp_path / "separation.json")["device"] == "cpu"


@pytest.mark.parametrize("passes", [2, 3, 4])
def test_multipass_reinfers_residual_and_exports_combined_removal(tmp_path, monkeypatch, passes):
    original = np.random.default_rng(16).normal(0, 0.1, (16000, 2)).astype(np.float32)
    original[0, 0] = 1.25
    sf.write(tmp_path / "source.wav", original, 32000, subtype="FLOAT")
    settings = bubble.validate_settings(strength=0.75, start=0.1, end=0.4, passes=passes)
    write_json(tmp_path / "request.json", dict(source="source.wav", filename="clip.wav", mode="bubble",
               device="cpu", cleanup=settings))
    monkeypatch.setattr(bubble, "checkpoint", lambda _: tmp_path / "dummy")
    loads, inputs = [], []
    monkeypatch.setattr(bubble, "load_model", lambda *args: loads.append(args) or object())

    def predict(values, *_):
        inputs.append(values.copy())
        return values * 0.5

    monkeypatch.setattr(bubble, "estimate_target", predict)
    # Isolate iteration/routing from the spectral-mask test above.
    monkeypatch.setattr(bubble, "removal_candidate", lambda _original, target, _rate: target)
    worker.process(tmp_path)
    assert len(loads) == 1 and len(inputs) == passes
    expected = original.copy()
    for values in inputs:
        np.testing.assert_array_equal(values, expected)
        expected = bubble.apply_selection(expected, expected * 0.5, 32000, settings)[0]
    mix = read_json(tmp_path / "mix.json")
    report = read_json(tmp_path / "output" / mix["report"])
    cleaned, rate = sf.read(tmp_path / "output" / mix["mix"], dtype="float32", always_2d=True)
    removed, _ = sf.read(tmp_path / "output" / mix["removed"], dtype="float32", always_2d=True)
    np.testing.assert_allclose(cleaned, expected, atol=1e-7)
    np.testing.assert_allclose(cleaned + removed, original, atol=1e-7)
    np.testing.assert_array_equal(cleaned[:3200], original[:3200])
    np.testing.assert_array_equal(cleaned[12800:], original[12800:])
    assert rate == 32000 and report["passes"] == passes and mix["cleanup"] == settings
    assert len(report["pass_details"]) == passes
    assert report["outside_selection_bit_exact"] and report["source_unchanged"]
    # Re-export must not apply strength/fades again; changed settings need inference.
    same = bubble.export_cleanup(tmp_path, 0.75, 0.1, 0.4, passes)
    stored, _ = sf.read(tmp_path / "output" / same["mix"], dtype="float32", always_2d=True)
    np.testing.assert_array_equal(stored, cleaned)
    for changed in [(0.5, 0.1, 0.4, passes), (0.75, 0, 0.4, passes), (0.75, 0.1, 0.3, passes), (0.75, 0.1, 0.4, 1)]:
        with pytest.raises(ValueError, match="Run cleanup again"):
            bubble.export_cleanup(tmp_path, *changed)
    assert read_json(tmp_path / "mix.json") == same


def test_later_pass_oom_retries_only_that_residual_on_cpu(tmp_path, monkeypatch):
    import torch

    sf.write(tmp_path / "source.wav", np.full((3000, 2), 0.1, np.float32), 32000, subtype="FLOAT")
    write_json(tmp_path / "request.json", dict(source="source.wav", filename="clip.wav", mode="bubble",
               device="cuda", cpu_fallback=True, cleanup=bubble.validate_settings(passes=3)))
    monkeypatch.setattr(bubble, "choose_device", lambda _: "cuda")
    monkeypatch.setattr(bubble, "checkpoint", lambda _: tmp_path / "dummy")
    loads, calls = [], []
    monkeypatch.setattr(bubble, "load_model", lambda _path, device: loads.append(device) or object())
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    monkeypatch.setattr(bubble, "removal_candidate", lambda _original, target, _rate: target)

    def predict(values, kind, device, *_):
        calls.append((device, values.copy()))
        if len(calls) == 2:
            raise torch.cuda.OutOfMemoryError("test later pass OOM")
        return values * 0.5

    monkeypatch.setattr(bubble, "estimate_target", predict)
    worker.process(tmp_path)
    assert loads == ["cuda", "cpu"]
    assert [device for device, _ in calls] == ["cuda", "cuda", "cpu", "cpu"]
    np.testing.assert_array_equal(calls[1][1], calls[2][1])
    assert np.max(calls[3][1]) < np.max(calls[1][1]) < np.max(calls[0][1])
    report = read_json(tmp_path / "separation.json")
    assert [item["device"] for item in report["pass_details"]] == ["cuda", "cpu", "cpu"]
