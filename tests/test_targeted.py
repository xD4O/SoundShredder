import json
import zipfile

import numpy as np
import pytest
import soundfile as sf
from test_api import client as client
from test_api import wav

from soundshredder import bubble, prompts, server, targeted, worker
from soundshredder.audio import read_json, sha256, write_json


@pytest.mark.parametrize("text", ["", "  ", "x" * 201, "water\nnoise", "ring\x00", "foo\u202ebar", None])
def test_invalid_prompt_rejected_before_download(text):
    with pytest.raises(ValueError):
        prompts.validate_prompt(text)


def test_prompt_cache_checks_identity_shape_and_finite_values(tmp_path, monkeypatch):
    model = tmp_path / "model.ckpt"
    vector = np.zeros(512, np.float32)
    vector[0] = 1
    calls = []
    monkeypatch.setattr(prompts, "tokenizer_file", lambda *_: tmp_path / "tokenizer.json")
    monkeypatch.setattr(prompts, "encode_text", lambda text, *_: calls.append(text) or vector)
    np.testing.assert_array_equal(prompts.prompt_vector("water bubbling", model, lambda *_: None), vector)
    prompts.prompt_vector("water bubbling", model, lambda *_: None)
    assert calls == ["water bubbling"]
    cache = next((tmp_path / "prompts").glob("*.json"))
    saved = json.loads(cache.read_text())
    saved["vector"] = [float("nan")] * 512
    cache.write_text(json.dumps(saved))
    prompts.prompt_vector("water bubbling", model, lambda *_: None)
    prompts.prompt_vector("a ringing phone", model, lambda *_: None)
    assert calls == ["water bubbling", "water bubbling", "a ringing phone"]


@pytest.mark.parametrize("preview,passes", [(True, 2), (False, 3)])
def test_targeted_multipass_context_preservation_and_exports(tmp_path, monkeypatch, preview, passes):
    rate = 8000
    audio = np.random.default_rng(123).normal(0, .1, (rate * 20, 2)).astype(np.float32)
    audio[0, 0] = 1.25
    sf.write(tmp_path / "source.wav", audio, rate, subtype="FLOAT")
    digest = sha256(tmp_path / "source.wav")
    write_json(tmp_path / "request.json", dict(source="source.wav", filename="clip.wav", mode="targeted", device="cpu",
               cleanup=targeted.validate_settings("bubbles", .5, 3, 18, passes), preview=preview))
    monkeypatch.setattr(bubble, "checkpoint", lambda *_: tmp_path / "dummy")
    monkeypatch.setattr(targeted, "prompt_vector", lambda *_: np.ones(512, np.float32) / np.sqrt(512))
    monkeypatch.setattr(bubble, "load_model", lambda *_: object())
    observed = []
    monkeypatch.setattr(bubble, "estimate_target", lambda samples, *_: observed.append(samples.copy()) or samples * .5)
    monkeypatch.setattr(bubble, "removal_candidate", lambda source, target, rate: source * .5)
    worker.process(tmp_path)
    assert len(observed) == passes
    # Later passes receive the modified signal, not another copy of the original.
    assert np.linalg.norm(observed[1]) < np.linalg.norm(observed[0])
    mix, report = read_json(tmp_path / "mix.json"), read_json(tmp_path / "separation.json")
    end = 13 if preview else 18
    assert report["selected_sample_range"] == [3 * rate, end * rate]
    assert len(observed[0]) == (end + 2 - 1) * bubble.MODEL_RATE
    result, sr = sf.read(tmp_path / "output" / mix["mix"], dtype="float32", always_2d=True)
    removed, _ = sf.read(tmp_path / "output" / mix["removed"], dtype="float32", always_2d=True)
    assert sr == rate and result.shape == audio.shape
    assert np.array_equal(result[:3 * rate], audio[:3 * rate])
    assert np.array_equal(result[end * rate:], audio[end * rate:])
    assert result[0, 0] == 1.25 and sha256(tmp_path / "source.wav") == digest
    np.testing.assert_allclose(result + removed, audio, atol=3e-8)
    assert report["preview"] == preview and report["passes"] == passes
    with zipfile.ZipFile(tmp_path / "output" / mix["bundle"]) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == 3


def test_zero_strength_skips_models_and_inspect_never_removes_audio(tmp_path, monkeypatch):
    sf.write(tmp_path / "source.wav", np.ones((100, 1), np.float32) * .1, 8000, subtype="FLOAT")
    monkeypatch.setattr(bubble, "checkpoint", lambda *_: pytest.fail("No model should load"))
    request = dict(source="source.wav", filename="clip.wav", device="cpu", mode="inspect")
    write_json(tmp_path / "request.json", request)
    worker.process(tmp_path)
    assert read_json(tmp_path / "progress.json")["status"] == "complete"
    assert not (tmp_path / "mix.json").exists()
    write_json(tmp_path / "request.json", {**request, "mode": "targeted", "cleanup": targeted.validate_settings("water", 0)})
    worker.process(tmp_path)
    mix = read_json(tmp_path / "mix.json")
    original, _ = sf.read(tmp_path / "output/original.wav", dtype="float32")
    cleaned, _ = sf.read(tmp_path / "output" / mix["mix"], dtype="float32")
    assert np.array_equal(original, cleaned)


@pytest.mark.parametrize("fallback", [True, False])
def test_targeted_gpu_memory_failure_respects_fallback_and_keeps_previous_pass(tmp_path, monkeypatch, fallback):
    import torch

    sf.write(tmp_path / "source.wav", np.full((8000, 1), .1, np.float32), 8000, subtype="FLOAT")
    write_json(tmp_path / "request.json", dict(source="source.wav", filename="clip.wav", mode="targeted",
               device="cuda", cpu_fallback=fallback, cleanup=targeted.validate_settings("water", .5, passes=2)))
    monkeypatch.setattr(targeted, "choose_device", lambda *_: "cuda")
    monkeypatch.setattr(bubble, "checkpoint", lambda *_: tmp_path / "dummy")
    monkeypatch.setattr(targeted, "prompt_vector", lambda *_: np.ones(512, np.float32) / np.sqrt(512))
    monkeypatch.setattr(bubble, "load_model", lambda *_: object())
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    monkeypatch.setattr(bubble, "removal_candidate", lambda source, *_: source * .5)
    calls = []

    def estimate(samples, kind, device, *_):
        calls.append((device, samples.copy()))
        if len(calls) == 2:
            raise torch.cuda.OutOfMemoryError("out of memory")
        return samples * .5

    monkeypatch.setattr(bubble, "estimate_target", estimate)
    if not fallback:
        with pytest.raises(torch.cuda.OutOfMemoryError):
            worker.process(tmp_path)
        assert not (tmp_path / "mix.json").exists()
        return
    worker.process(tmp_path)
    assert [device for device, _ in calls] == ["cuda", "cuda", "cpu"]
    np.testing.assert_array_equal(calls[1][1], calls[2][1])
    assert np.linalg.norm(calls[1][1]) < np.linalg.norm(calls[0][1])
    assert read_json(tmp_path / "separation.json")["device"] == "cpu"


def complete(job, mix=None):
    folder = server.DATA / job
    server.PROCESSES[job].code = 0
    write_json(folder / "progress.json", {"status": "complete"})
    if mix:
        (folder / "output").mkdir(exist_ok=True)
        write_json(folder / "mix.json", mix)
        (folder / "output" / mix["mix"]).write_bytes(wav())
    return folder


def test_completed_worker_must_exit_before_starting_another_version(client):
    job = client.post("/api/jobs", files={"file": ("clip.wav", wav())}, data={"mode": "inspect"}).json()["id"]
    write_json(server.DATA / job / "progress.json", {"status": "complete"})
    assert client.get(f"/api/jobs/{job}").json()["worker_active"] is True
    assert client.post(f"/api/jobs/{job}/rerun", json={"mode": "inspect"}).status_code == 409
    assert len(list(server.DATA.iterdir())) == 1
    server.PROCESSES[job].code = 0
    assert client.get(f"/api/jobs/{job}").json()["worker_active"] is False
    assert client.post(f"/api/jobs/{job}/rerun", json={"mode": "inspect"}).status_code == 202


def test_targeted_api_versions_preview_guards_and_independent_sources(client):
    before = client.post("/api/jobs", files={"file": ("clip.mp4", wav())}, data={"mode": "inspect"}).json()["id"]
    base = complete(before)
    assert client.get(f"/api/jobs/{before}/listening").status_code == 409
    assert client.post(f"/api/jobs/{before}/mix", json=dict(speech=1, music=1, effects=1)).status_code == 409
    settings = dict(mode="targeted", prompt="water bubbling", bubble_passes=2, preview=True)
    preview = client.post(f"/api/jobs/{before}/rerun", json=settings).json()["id"]
    complete(preview, {"mix": "cleaned-123456789abc.wav", "preview": True})
    assert client.post(f"/api/jobs/{preview}/rerun", json={**settings, "source_basis": "cleaned"}).status_code == 400
    full = client.post(f"/api/jobs/{preview}/rerun", json={**settings, "preview": False}).json()["id"]
    full_folder = complete(full, {"mix": "cleaned-123456789abc.wav", "preview": False})
    child = client.post(f"/api/jobs/{full}/rerun", json={**settings, "preview": False, "source_basis": "cleaned"}).json()["id"]
    complete(child)
    saved = read_json(server.DATA / child / "request.json")
    assert saved["parent_id"] == full and saved["root_id"] == before
    assert saved["source"] == "base.wav" and saved["original_source"] == "source.mp4"
    assert (server.DATA / child / "base.wav").read_bytes() == (full_folder / "output/cleaned-123456789abc.wav").read_bytes()
    assert client.get(f"/api/jobs/{child}/video").content == (base / "source.mp4").read_bytes()
    versions = client.get(f"/api/jobs/{child}/versions").json()
    assert len(versions) == 4 and {v["id"] for v in versions} == {before, preview, full, child}
    assert client.delete(f"/api/jobs/{full}").status_code == 200
    assert (server.DATA / child / "base.wav").is_file()
    retry = client.post(f"/api/jobs/{child}/rerun", json={**settings, "preview": False, "source_basis": "original"})
    assert retry.status_code == 202
    assert (server.DATA / retry.json()["id"] / "source.mp4").read_bytes() == wav()


@pytest.mark.parametrize("settings", [{"prompt": ""}, {"prompt": "x" * 201}, {"prompt": "bubble\nnoise"},
    {"prompt": "water", "bubble_passes": 5}, {"prompt": "water", "bubble_strength": "nan"},
    {"prompt": "water", "range_start": 5, "range_end": 2}])
def test_targeted_api_rejects_invalid_settings_before_starting(client, settings):
    assert client.post("/api/jobs", files={"file": ("clip.wav", wav())}, data={"mode": "targeted", **settings}).status_code == 400
    assert client.get("/api/jobs").json() == []
