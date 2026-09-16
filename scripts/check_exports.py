"""Read-only verification of downloaded outputs from a running local app."""

import io
import json
import zipfile
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf


def main():
    client = httpx.Client(base_url="http://127.0.0.1:7860", timeout=60)
    jobs = client.get("/api/jobs").json()
    jobs = [job for job in jobs if job["status"] == "complete" and job["report"].get("mode") != "bubble"]
    assert jobs
    evidence = []
    for job in jobs:
        report = job["report"]
        prefix = f"/api/jobs/{job['id']}/files/"
        tracks = {}
        filenames = ["speech.wav", "music.wav", "effects.wav", job["mix"]["mix"]]
        if job["mix"].get("removed"):
            filenames.append(job["mix"]["removed"])
        for name in filenames:
            response = client.get(prefix + name)
            response.raise_for_status()
            audio, rate = sf.read(io.BytesIO(response.content), always_2d=True)
            assert rate == report["sample_rate"]
            assert audio.shape == (report["frames"], report["channels"])
            assert np.isfinite(audio).all() and np.max(np.abs(audio)) <= 1
            tracks[name] = audio
        expected = sum(tracks[stem + ".wav"] * job["mix"]["gains"][stem] for stem in ("speech", "music", "effects"))
        np.testing.assert_allclose(tracks[job["mix"]["mix"]], expected, atol=4e-7)
        if job["mix"].get("removed"):
            excluded = sum(tracks[stem + ".wav"] * (1 - job["mix"]["gains"][stem]) for stem in ("speech", "music", "effects"))
            np.testing.assert_allclose(tracks[job["mix"]["removed"]], excluded, atol=4e-7)
        archive = client.get(prefix + job["mix"]["bundle"])
        archive.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
            assert len(bundle.namelist()) == (6 if job["mix"].get("removed") else 5)
            assert bundle.testzip() is None
        evidence.append(
            {
                "job": job["id"],
                "device": report["device"],
                "frames": report["frames"],
                "channels": report["channels"],
                "sample_rate": report["sample_rate"],
                "processing_seconds": report["processing_seconds"],
                "downloads_and_mix_verified": True,
            }
        )
    Path("artifacts/download-verification.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
