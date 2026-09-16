import hashlib
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from soundshredder import engine, worker
from soundshredder.audio import STEMS, read_json, write_json


@pytest.mark.parametrize("channels", [1, 2])
def test_full_pipeline_preserves_source_and_timing(tmp_path, monkeypatch, channels):
    audio = np.random.default_rng(2).normal(0, 0.1, (3199, channels)).astype(np.float32)
    path = tmp_path / "source.wav"
    sf.write(path, audio, 32000, subtype="FLOAT")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(
        tmp_path / "request.json",
        {
            "source": "source.wav",
            "filename": "source.wav",
            "device": "cpu",
            "gains": dict(speech=1, music=0, effects=1),
        },
    )
    monkeypatch.setattr(worker, "choose_device", lambda _: "cpu")

    def separate(values, device, progress):
        assert len(values) == 4799
        assert values.shape[1] == channels
        assert device == "cpu"
        return {stem: values * scale for stem, scale in zip(STEMS, (0.3, 0.5, 0.2), strict=True)}

    monkeypatch.setattr(worker, "run_model", separate)
    worker.process(tmp_path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    report = read_json(tmp_path / "separation.json")
    assert report["source_sha256"] == before
    assert report["source_unchanged"]
    assert report["device"] == "cpu"
    assert "diagnostics" in report
    for stem in STEMS:
        info = sf.info(tmp_path / "output" / f"{stem}.wav")
        assert (info.frames, info.samplerate, info.channels) == (3199, 32000, channels)
    assert read_json(tmp_path / "progress.json")["status"] == "complete"


def test_gpu_oom_retries_cpu_and_records_it(tmp_path, monkeypatch):
    import torch

    sf.write(tmp_path / "source.wav", np.ones((2400, 1), dtype=np.float32) * 0.1, 48000)
    write_json(
        tmp_path / "request.json",
        {
            "source": "source.wav",
            "filename": "source.wav",
            "device": "cuda",
            "cpu_fallback": True,
            "gains": dict(speech=1, music=0, effects=0),
        },
    )
    monkeypatch.setattr(worker, "choose_device", lambda _: "cuda")
    calls = []

    def separate(audio, device, progress):
        calls.append(device)
        if device == "cuda":
            raise torch.cuda.OutOfMemoryError("test memory exhaustion")
        return {stem: audio / 3 for stem in STEMS}

    monkeypatch.setattr(worker, "run_model", separate)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    worker.process(tmp_path)
    assert calls == ["cuda", "cpu"]
    report = read_json(tmp_path / "separation.json")
    assert report["device"] == "cpu" and report["warnings"]


def test_block_crossfade_has_no_gaps_or_level_change(monkeypatch):
    import bandit_infer

    class Session:
        def __init__(self, *args, **kwargs):
            self.hook = None
            self._runtime = SimpleNamespace(model=self, handler=SimpleNamespace(_get_n_chunks=lambda _: 1))

        def register_forward_hook(self, hook):
            self.hook = hook
            return SimpleNamespace(remove=lambda: None)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def infer(self, values, sample_rate):
            self.hook(None, None, None)
            return {stem: values * scale for stem, scale in zip(STEMS, (0.3, 0.5, 0.2), strict=True)}

    monkeypatch.setattr(bandit_infer, "BanditSession", Session)
    monkeypatch.setattr(
        engine,
        "infer_active_windows",
        lambda runtime, audio, progress: {
            stem: audio * scale for stem, scale in zip(STEMS, (0.3, 0.5, 0.2), strict=True)
        },
    )
    monkeypatch.setattr(engine, "MODEL_RATE", 100)
    monkeypatch.setattr(engine, "BLOCK_SECONDS", 2)
    monkeypatch.setattr(engine, "OVERLAP_SECONDS", 1)
    values = np.random.default_rng(4).normal(size=(407, 2)).astype(np.float32)
    output = engine.run_model(values, "cpu", lambda *_: None)
    for stem, scale in zip(STEMS, (0.3, 0.5, 0.2), strict=True):
        np.testing.assert_allclose(output[stem], values * scale, atol=2e-7)


def test_explicit_gpu_does_not_silently_fall_back(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert engine.choose_device("auto") == "cpu"
    with pytest.raises(ValueError, match="unavailable"):
        engine.choose_device("cuda")


@pytest.mark.parametrize("frames", [2, 13, 150, 300, 500])
@pytest.mark.parametrize("channels", [1, 2])
def test_active_window_optimization_matches_upstream_padding_and_fold(frames, channels):
    import torch
    from bandit_infer._v2.inference import StandardTensorChunkedInferenceHandler

    class Model(torch.nn.Module):
        stems = ("speech", "music", "sfx")

        def __init__(self):
            super().__init__()
            self.passes = 0

        def forward(self, batch):
            self.passes += 1
            # Window-dependent nonlinear output catches incorrect window offsets,
            # skipped context, incorrect cropping, and boundary weighting.
            audio = batch["mixture"]["audio"]
            values = torch.tanh(audio - audio.mean(dim=-1, keepdim=True))
            return {
                "estimates": {
                    name: {"audio": values * scale} for name, scale in zip(self.stems, (0.2, 0.3, 0.5), strict=True)
                }
            }

    handler = StandardTensorChunkedInferenceHandler(8, 1, 1, 10)
    model = Model()
    audio = np.random.default_rng(12).normal(size=(frames, channels)).astype(np.float32)
    reference = handler(torch.from_numpy(audio.T.copy())[None], model)["estimates"]
    original_passes = model.passes
    model.passes = 0
    runtime = SimpleNamespace(handler=handler, model=model, device=torch.device("cpu"))
    result = engine.infer_active_windows(runtime, audio, lambda *_: None)
    assert model.passes < original_passes
    for name, source in zip(STEMS, ("speech", "music", "sfx"), strict=True):
        np.testing.assert_allclose(result[name], reference[source]["audio"][0].numpy().T, atol=2e-7)
