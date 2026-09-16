import zipfile

import numpy as np
import pytest
import soundfile as sf

from soundshredder.audio import STEMS, decode, export_mix, read_json, resample, validate_gains, write_json


@pytest.mark.parametrize("rate", [8000, 32000, 44100, 48000, 96000])
@pytest.mark.parametrize("channels", [1, 2])
def test_resampling_restores_exact_shape(rate, channels):
    rng = np.random.default_rng(42)
    audio = rng.normal(0, 0.1, (int(rate * 0.071) + 1, channels)).astype(np.float32)
    model = resample(audio, rate, 48000)
    restored = resample(model, 48000, rate, len(audio))
    assert restored.shape == audio.shape
    assert np.isfinite(restored).all()


@pytest.fixture
def session(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "output").mkdir()
    time = np.arange(801, dtype=np.float32) / 8000
    signals = {
        stem: np.column_stack((0.1 * np.sin(2 * np.pi * freq * time), 0.08 * np.cos(2 * np.pi * freq * time)))
        for stem, freq in zip(STEMS, (180, 620, 1100), strict=True)
    }
    for stem, values in signals.items():
        sf.write(tmp_path / "work" / f"{stem}.wav", values, 8000, subtype="FLOAT")
        sf.write(tmp_path / "output" / f"{stem}.wav", values * 0.8, 8000, subtype="PCM_24")
    write_json(tmp_path / "separation.json", {"frames": 801, "channels": 2, "sample_rate": 8000, "output_gain": 0.8})
    return tmp_path, signals


@pytest.mark.parametrize(
    "levels",
    [dict(speech=1, music=0, effects=1), dict(speech=0, music=0, effects=0), dict(speech=0.2, music=0.7, effects=0)],
)
def test_mix_routing_downloads_and_silence(session, levels):
    path, signals = session
    result = export_mix(path, levels)
    audio, rate = sf.read(path / "output" / result["mix"], always_2d=True)
    expected = sum(signals[s] * levels[s] for s in STEMS) * 0.8
    np.testing.assert_allclose(audio, expected, atol=2e-7)
    assert rate == 8000
    assert sf.info(path / "output" / result["mix"]).subtype == "PCM_24"
    with zipfile.ZipFile(path / "output" / result["bundle"]) as archive:
        assert set(archive.namelist()) == {
            "Cleaned mix.wav",
            "Removed sounds.wav",
            "Dialogue.wav",
            "Music.wav",
            "Sound effects.wav",
            "separation-report.json",
        }
    assert read_json(path / "output" / result["report"])["timing_verified"]
    assert export_mix(path, levels)["revision"] != result["revision"]


@pytest.mark.parametrize(
    "levels", [{}, {"speech": float("nan"), "music": 0, "effects": 0}, {"speech": 2, "music": 0, "effects": 0}]
)
def test_invalid_mix_rejected(levels):
    with pytest.raises(ValueError):
        validate_gains(levels)


def test_surround_is_not_silently_downmixed(tmp_path):
    source = tmp_path / "surround.wav"
    sf.write(source, np.zeros((800, 6)), 8000)
    with pytest.raises(ValueError, match="mono or stereo"):
        decode(source, tmp_path)
