import zipfile

import numpy as np
import pytest
import soundfile as sf

from soundshredder import listening
from soundshredder.audio import STEMS, export_mix, read_json, sha256, waveform, write_json


def bubble_session(path):
    (path / "output").mkdir()
    audio = np.random.default_rng(8).normal(0, 0.05, (3199, 2)).astype(np.float32)
    sf.write(path / "output/original.wav", audio, 32000, subtype="FLOAT")
    sf.write(path / "output/cleaned-0123456789ab.wav", audio * 0.8, 32000, subtype="FLOAT")
    sf.write(path / "output/removed-0123456789ab.wav", audio * 0.2, 32000, subtype="FLOAT")
    write_json(path / "request.json", {"device": "cpu", "cpu_fallback": True})
    write_json(path / "separation.json", {"mode": "bubble"})
    write_json(path / "progress.json", {"status": "complete"})
    write_json(path / "mix.json", {"revision": "0123456789ab", "mix": "cleaned-0123456789ab.wav",
                                  "removed": "removed-0123456789ab.wav"})
    write_json(path / "listening.json", {"status": "running", "generate_stems": True})
    return audio


def test_bubble_tracks_prepare_without_mutating_cleanup(tmp_path, monkeypatch):
    audio = bubble_session(tmp_path)
    protected = [tmp_path / name for name in ("mix.json", "separation.json", "progress.json",
                 "output/original.wav", "output/cleaned-0123456789ab.wav", "output/removed-0123456789ab.wav")]
    before = {p: sha256(p) for p in protected}

    def separate(values, device, progress):
        assert device == "cpu" and values.shape == (4799, 2)
        progress(0.5, "Working")
        return {name: values * weight for name, weight in zip(STEMS, (0.2, 0.3, 0.5), strict=True)}

    monkeypatch.setattr(listening, "run_model", separate)
    listening.prepare(tmp_path)
    result = listening.manifest(tmp_path)
    assert result["status"] == "complete" and not result["missing"]
    assert all(sha256(p) == value for p, value in before.items())
    for name in STEMS:
        info = sf.info(tmp_path / "output" / result["tracks"][name]["file"])
        assert (info.frames, info.samplerate, info.channels) == (len(audio), 32000, 2)
        assert len(result["tracks"][name]["waveform"]) == 180
    assert result["tracks"]["removed"]["file"] == "removed-0123456789ab.wav"


def test_partial_bubble_tracks_are_hidden_until_success(tmp_path):
    audio = bubble_session(tmp_path)
    for name in STEMS:
        sf.write(tmp_path / "output" / f"{name}.wav", audio, 32000)
    for status in ("running", "cancelled", "failed"):
        write_json(tmp_path / "listening.json", {"status": status})
        result = listening.manifest(tmp_path)
        assert result["missing"] == list(STEMS)
        assert result["tracks"]["removed"]["file"]


def test_listening_oom_fallback_and_disabled_fallback(tmp_path, monkeypatch):
    import torch

    bubble_session(tmp_path)
    monkeypatch.setattr(listening, "choose_device", lambda _: "cuda")
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    devices = []

    def run(values, device, progress):
        devices.append(device)
        if device == "cuda":
            raise torch.cuda.OutOfMemoryError("Test memory exhaustion")
        return {name: values / 3 for name in STEMS}

    monkeypatch.setattr(listening, "run_model", run)
    listening.prepare(tmp_path)
    assert devices == ["cuda", "cpu"]
    assert read_json(tmp_path / "listening.json")["warnings"]
    write_json(tmp_path / "request.json", {"device": "cuda", "cpu_fallback": False})
    write_json(tmp_path / "listening.json", {"status": "running", "generate_stems": True})
    with pytest.raises(torch.cuda.OutOfMemoryError):
        listening.prepare(tmp_path)


@pytest.mark.parametrize("levels", [dict(speech=1, music=0, effects=1), dict(speech=0.2, music=0.7, effects=0),
                                    dict(speech=1, music=1, effects=1)])
def test_removed_track_contains_excluded_layers_and_refreshes(tmp_path, levels):
    (tmp_path / "work").mkdir()
    (tmp_path / "output").mkdir()
    signals = {}
    for index, name in enumerate(STEMS):
        signals[name] = np.ones((801, 2), dtype=np.float32) * (index + 1) * 0.1
        sf.write(tmp_path / "work" / f"{name}.wav", signals[name], 8000, subtype="FLOAT")
        sf.write(tmp_path / "output" / f"{name}.wav", signals[name] * 0.8, 8000, subtype="PCM_24")
    write_json(tmp_path / "separation.json", dict(frames=801, channels=2, sample_rate=8000, output_gain=0.8))
    mix = export_mix(tmp_path, levels)
    removed, _ = sf.read(tmp_path / "output" / mix["removed"], always_2d=True)
    expected = sum(signals[name] * (1 - levels[name]) for name in STEMS) * 0.8
    np.testing.assert_allclose(removed, expected, atol=2e-7)
    with zipfile.ZipFile(tmp_path / "output" / mix["bundle"]) as archive:
        assert "Removed sounds.wav" in archive.namelist()
    first_removed = mix["removed"]
    mix = export_mix(tmp_path, dict(speech=0, music=0, effects=0))
    assert mix["removed"] != first_removed
    assert listening.manifest(tmp_path)["tracks"]["removed"]["file"] == mix["removed"]
    assert waveform(expected)  # Finite waveform metadata remains available even for silence.


def test_legacy_removed_preparation_reuses_stems_and_preserves_existing_mix(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    (tmp_path / "output").mkdir()
    for name in STEMS:
        samples = np.ones((800, 1), np.float32) * 0.1
        sf.write(tmp_path / "work" / f"{name}.wav", samples, 8000, subtype="FLOAT")
        sf.write(tmp_path / "output" / f"{name}.wav", samples, 8000)
    write_json(tmp_path / "request.json", {"device": "cpu"})
    write_json(tmp_path / "separation.json", dict(frames=800, channels=1, sample_rate=8000, output_gain=1))
    write_json(tmp_path / "mix.json", dict(revision="0123456789ab", gains=dict(speech=1, music=0, effects=1)))
    write_json(tmp_path / "listening.json", {"status": "running", "generate_stems": False})
    before = (tmp_path / "mix.json").read_bytes()
    monkeypatch.setattr(listening, "run_model", lambda *_: pytest.fail("Existing stems must be reused"))
    listening.prepare(tmp_path)
    assert (tmp_path / "mix.json").read_bytes() == before
    result = listening.manifest(tmp_path)
    assert not result["missing"]
    assert all(len(track["waveform"]) == 180 for track in result["tracks"].values())
