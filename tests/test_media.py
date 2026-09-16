import subprocess

import imageio_ffmpeg
import numpy as np
import pytest
import soundfile as sf

from soundshredder.audio import decode, sha256


@pytest.mark.parametrize("suffix", ["m4a", "mp4"])
def test_ffmpeg_decode_keeps_mono_and_sample_rate(tmp_path, suffix):
    wav = tmp_path / "source.wav"
    target = tmp_path / f"source.{suffix}"
    sf.write(wav, 0.1 * np.sin(np.arange(8000) / 10), 32000)
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", str(target)],
        check=True,
        capture_output=True,
    )
    before = sha256(target)
    audio, rate = decode(target, tmp_path)
    assert rate == 32000 and audio.shape[1] == 1 and len(audio) > 0
    assert np.isfinite(audio).all()
    assert sha256(target) == before


def test_corrupt_file_has_actionable_error(tmp_path):
    source = tmp_path / "broken.m4a"
    source.write_bytes(b"this is not an audio file")
    with pytest.raises(ValueError, match="valid audio file"):
        decode(source, tmp_path)
