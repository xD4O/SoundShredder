import io
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from soundshredder import lab_api, mixing, server
from soundshredder.audio import read_json, write_json


def setup_session(root, rate=8000, duration=3):
    folder = root / ("a" * 32)
    (folder / "output").mkdir(parents=True)
    frames = round(rate * duration)
    source = np.column_stack([.1 * np.sin(np.arange(frames) / 8), .08 * np.cos(np.arange(frames) / 5)]).astype(np.float32)
    sf.write(folder / "source.wav", source, rate, subtype="FLOAT")
    sf.write(folder / "output/original.wav", source, rate, subtype="FLOAT")
    for index, name in enumerate(("speech", "music", "effects"), 1):
        sf.write(folder / "output" / f"{name}.wav", source * index, rate, subtype="FLOAT")
    write_json(folder / "request.json", dict(source="source.wav", filename="reference.wav", mode="inspect", device="cpu"))
    write_json(folder / "source.json", dict(filename="reference.wav", frames=frames, sample_rate=rate, channels=2, duration=duration))
    write_json(folder / "progress.json", dict(status="complete", progress=1, message="Ready"))
    lab = folder / "lab"
    lab.mkdir()
    state = mixing.initial_state(folder)
    for name in ("speech", "music", "effects"):
        state["tracks"][name]["asset"] = mixing.add_asset(lab, state, folder / "output" / f"{name}.wav", name, name, "original")
    state["revision"] = 1
    write_json(lab / "state.json", state)
    return folder, state


@pytest.mark.parametrize("bad", [[dict(start=2, end=1, db=-6)], [dict(start=-1, end=1, db=0)],
    [dict(start=0, end=4, db=0)], [dict(start=0, end=1, db=7)], [dict(start=0, end=1, db=float('nan'))],
    [dict(start=0, end=2, db=0), dict(start=1, end=3, db=-3)], [dict(start=False, end=1, db=0)]])
def test_invalid_time_edits_rejected(bad):
    with pytest.raises(ValueError):
        mixing.validate_regions(bad, 3)


def test_scope_restores_baseline_and_fades_only_inside_selection():
    times = np.arange(0, 3, .0001)
    gain = mixing.envelope([dict(start=1, end=2, db=-12)], times)
    assert np.all(gain[times < 1] == 1) and np.all(gain[times >= 2] == 1)
    assert gain[10000] == 1
    assert gain[15000] == pytest.approx(10 ** (-12 / 20))
    mute = mixing.envelope([dict(start=1, end=1 + 1/24, db=None)], times)
    assert mute[10200] == 0 and mute[11000] == 1


def test_export_timing_headroom_and_unchanged_other_stems(tmp_path):
    folder, state = setup_session(tmp_path, rate=44100)
    lab = folder / "lab"
    state["tracks"]["music"]["regions"] = [dict(start=1, end=2, db=-9)]
    original = sf.read(mixing.asset_path(lab, state["tracks"]["music"]["asset"]), dtype="float32")[0]
    output = tmp_path / "export"
    result = mixing.render(lab, state, output, lambda *_: None)
    music, rate = sf.read(output / "music.wav", always_2d=True)
    expected = original * result["output_gain"]
    np.testing.assert_allclose(music[:rate], expected[:rate], atol=2e-7)
    np.testing.assert_allclose(music[2*rate:], expected[2*rate:], atol=2e-7)
    np.testing.assert_allclose(music[rate+500:2*rate-500], expected[rate+500:2*rate-500] * 10 ** (-9/20), atol=2e-7)
    total = sum(sf.read(output / f"{name}.wav", always_2d=True)[0] for name in ("speech", "music", "effects"))
    mix, _ = sf.read(output / "mix.wav", always_2d=True)
    assert mix.shape == original.shape and np.max(np.abs(mix)) <= .98
    np.testing.assert_allclose(total, mix, atol=4e-7)
    np.testing.assert_array_equal(original, sf.read(mixing.asset_path(lab, state["tracks"]["music"]["asset"]), dtype="float32")[0])
    for track in state["tracks"].values():
        track["regions"] = [dict(start=0, end=3, db=6)]
    assert mixing.protection(state) == result["output_gain"] < 1


def test_browser_chunks_match_across_boundary_and_stay_bounded(tmp_path):
    folder, state = setup_session(tmp_path, rate=44100, duration=42)
    asset = state["tracks"]["effects"]["asset"]
    def audio(start, seconds):
        data = mixing.segment(folder / "lab", state, asset, start, seconds)
        values, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
        assert rate == 48000
        return values
    left, right = audio(0, 20), audio(20, 20)
    boundary = audio(19.5, 1)
    np.testing.assert_allclose(np.concatenate([left[-24000:], right[:24000]]), boundary, atol=1e-6)
    assert left.shape == (960000, 2)
    with pytest.raises(ValueError):
        audio(0, 21)


class Process:
    def __init__(self, *_, **__):
        self.returncode = None
    def poll(self):
        return self.returncode


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    for name in ("PROCESSES", "LISTENING_PROCESSES", "LAB_PROCESSES"):
        monkeypatch.setattr(server, name, {})
    monkeypatch.setattr(lab_api, "subprocess", SimpleNamespace(Popen=Process, STDOUT=-2))
    monkeypatch.setattr(lab_api, "stop_process", lambda process: setattr(process, "returncode", -1))
    folder, state = setup_session(tmp_path)
    with TestClient(server.app) as api:
        yield api, folder, state


def finish(api, folder):
    info = read_json(folder / "lab/task.json")
    task = folder / "lab/tasks" / info["id"]
    mixing.work(task)
    # A complete progress file must not expose a version until the worker exits.
    assert api.get(f"/api/jobs/{folder.name}/lab").json()["task"]["active"]
    server.LAB_PROCESSES[folder.name].returncode = 0
    return api.get(f"/api/jobs/{folder.name}/lab").json()


def test_api_stale_tabs_origin_validation_and_asset_paths(client):
    api, folder, state = client
    url = f"/api/jobs/{folder.name}/lab"
    payload = dict(revision=1, tracks=deepcopy(state["tracks"]))
    payload["tracks"]["speech"]["regions"] = [dict(start=1, end=2, db=None)]
    assert api.put(url, json=payload, headers={"Origin": "https://elsewhere.test"}).status_code == 403
    assert api.put(url, json=payload).json()["state"]["revision"] == 2
    assert api.put(url, json=payload).status_code == 409
    payload["revision"] = 2
    payload["tracks"]["speech"]["asset"] = state["tracks"]["music"]["asset"]
    assert api.put(url, json=payload).status_code == 400
    assert api.get(url + "/assets/missing").status_code == 404
    assert api.get(url + "/assets/..%2F..%2Fsource.wav").status_code == 404
    asset = state["tracks"]["speech"]["asset"]
    assert api.get(url + f"/assets/{asset}?start=0&seconds=21").status_code == 400
    assert api.get(url + f"/assets/{asset}?start=0&seconds=1").headers["content-type"] == "audio/wav"


def test_close_and_reopen_persist_without_touching_audio_mix_or_workers(client):
    api, folder, state = client
    url = f"/api/jobs/{folder.name}/lab/view"
    before = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    process = Process()
    server.LAB_PROCESSES[folder.name] = process
    assert api.get("/api/lab/sessions").json()[0]["closed"] is False
    assert api.put(url, json={"closed": True}).status_code == 200
    assert api.put(url, json={"closed": True}).status_code == 200
    # Another client (or a restarted browser) reads the same on-disk view state.
    reopened = TestClient(server.app)
    item = reopened.get("/api/lab/sessions").json()[0]
    assert item["closed"] is True and item["lab_running"] is True
    reopened.close()
    assert process.poll() is None
    for name, content in before.items():
        assert (folder / name).read_bytes() == content
    assert api.put(url, json={"closed": False}).status_code == 200
    assert api.get("/api/lab/sessions").json()[0]["closed"] is False
    assert read_json(folder / "lab/state.json") == state
    assert api.put(url, json={"closed": "yes"}).status_code == 422
    assert api.put(url, json={"closed": True}, headers={"Origin": "https://elsewhere.test"}).status_code == 403
    assert api.put("/api/jobs/missing/lab/view", json={"closed": True}).status_code == 404


def test_closed_lab_sessions_remain_accessible_beyond_recent_history_limit(client):
    api, folder, _ = client
    assert api.put(f"/api/jobs/{folder.name}/lab/view", json={"closed": True}).status_code == 200
    for number in range(21):
        other = folder.parent / f"{number:032x}"
        other.mkdir()
        for filename in ("request.json", "progress.json"):
            (other / filename).write_bytes((folder / filename).read_bytes())
    assert len(api.get("/api/jobs").json()) == 20
    sessions = api.get("/api/lab/sessions").json()
    assert len(sessions) == 22
    assert next(item for item in sessions if item["id"] == folder.name)["closed"] is True


@pytest.fixture
def layer_separator(monkeypatch):
    from soundshredder import worker

    inputs = []

    def separate(directory):
        audio, rate = sf.read(directory / "source.wav", dtype="float32", always_2d=True)
        inputs.append(audio.copy())
        output = directory / "output"
        output.mkdir()
        for kind, fraction in (("speech", .2), ("music", .35), ("effects", .3)):
            sf.write(output / f"{kind}.wav", audio * fraction, rate, subtype="FLOAT")

    monkeypatch.setattr(worker, "process", separate)
    return inputs


def test_recursive_layers_keep_parent_audio_edits_and_export_only_active_leaves(client, layer_separator):
    api, folder, state = client
    url = f"/api/jobs/{folder.name}/lab"
    state["tracks"]["effects"]["regions"] = [dict(start=1, end=2, db=-9)]
    write_json(folder / "lab/state.json", state)
    parent_id = state["tracks"]["effects"]["asset"]
    parent_path = mixing.asset_path(folder / "lab", parent_id)
    original_bytes = parent_path.read_bytes()
    original, rate = sf.read(parent_path, dtype="float32", always_2d=True)
    assert api.post(url + "/actions/split", json=dict(revision=1, track="effects", device="cpu")).status_code == 202
    second = finish(api, folder)["state"]
    layer2 = second["layers"][second["last_layer"]]
    assert layer2["depth"] == 2 and len(layer2["children"]) == 4
    assert second["tracks"]["effects"] == state["tracks"]["effects"]
    assert second["tracks"]["speech"] == state["tracks"]["speech"]
    assert second["tracks"]["music"] == state["tracks"]["music"]
    children = [sf.read(mixing.asset_path(folder / "lab", second["tracks"][name]["asset"]),
                        dtype="float64", always_2d=True)[0] for name in layer2["children"]]
    np.testing.assert_allclose(sum(children), original, atol=3e-8)
    np.testing.assert_array_equal(layer_separator[0], original)
    for name in layer2["children"]:
        assert second["tracks"][name]["regions"] == state["tracks"]["effects"]["regions"]
    child = layer2["children"][1]
    assert api.post(url + "/actions/split", json=dict(revision=2, track=child, device="cpu")).status_code == 202
    third = finish(api, folder)["state"]
    layer3 = third["layers"][third["last_layer"]]
    assert layer3["depth"] == 3 and layer3["parent_track"] == child
    np.testing.assert_array_equal(layer_separator[1], children[1].astype(np.float32))
    leaves = mixing.active_tracks(third)
    assert "effects" not in leaves and child not in leaves and len(leaves) == 9
    assert parent_path.read_bytes() == original_bytes
    target = folder / "lab/test-export"
    result = mixing.render(folder / "lab", third, target, lambda *_: None)
    report = read_json(target / "mix-report.json")
    assert set(report["tracks"]) == set(leaves) and report["layers"] == third["layers"]
    assert all(result["file_labels"][name].startswith("Layer ") for name in result["file_labels"])
    total = sum(sf.read(target / report["track_files"][name], always_2d=True)[0] for name in leaves)
    master, exported_rate = sf.read(target / "mix.wav", always_2d=True)
    assert exported_rate == rate and master.shape == original.shape
    np.testing.assert_allclose(total, master, atol=2e-6)
    expected_effects = original * mixing.envelope(state["tracks"]["effects"]["regions"], np.arange(len(original))/rate)[:, None]
    expected = (expected_effects + layer_separator[0]/3 + layer_separator[0]*2/3) * result["output_gain"]
    np.testing.assert_allclose(master, expected, atol=3e-7)
    restore = dict(revision=3, layer=layer2["id"], enabled=False)
    assert api.put(url + "/layer", json={**restore, "revision": 1}).status_code == 409
    response = api.put(url + "/layer", json=restore)
    assert response.status_code == 200
    restored = response.json()["state"]
    assert set(mixing.active_tracks(restored)) == {"speech", "music", "effects"}
    assert restored["tracks"] == third["tracks"]
    assert api.put(url + "/layer", json=dict(revision=4, layer=layer3["id"], enabled=True)).status_code == 400
    reused = api.put(url + "/layer", json={**restore, "revision": 4, "enabled": True}).json()["state"]
    assert set(mixing.active_tracks(reused)) == set(leaves)


def test_layer_cancel_and_invalid_operations_preserve_saved_mix(client, layer_separator):
    api, folder, state = client
    url = f"/api/jobs/{folder.name}/lab"
    assert api.post(url + "/actions/split", json=dict(revision=1, track="ambience")).status_code == 400
    assert api.post(url + "/actions/split", json=dict(revision=1, track="effects")).status_code == 202
    assert api.post(url + "/cancel").json()["state"] == state
    assert api.post(url + "/actions/split", json=dict(revision=1, track="effects")).status_code == 202
    deeper = finish(api, folder)["state"]
    assert api.post(url + "/actions/split", json=dict(revision=2, track="effects")).status_code == 400
    changed = deepcopy(deeper["tracks"])
    changed["effects"]["regions"] = [dict(start=1, end=2, db=-6)]
    assert api.put(url, json=dict(revision=2, tracks=changed)).status_code == 400
    layer = deeper["layers"][deeper["last_layer"]]
    restored = api.put(url + "/layer", json=dict(revision=2, layer=layer["id"], enabled=False)).json()["state"]
    restored["tracks"]["effects"]["regions"] = [dict(start=1, end=2, db=-3)]
    assert api.put(url, json=dict(revision=3, tracks=restored["tracks"])).status_code == 200
    assert api.put(url + "/layer", json=dict(revision=4, layer=layer["id"], enabled=True)).status_code == 400
    asset = state["tracks"]["speech"]["asset"]
    state["assets"][asset]["role"] = "preview"
    with pytest.raises(ValueError, match="full stem"):
        mixing.split_source(state, "speech")
    state["assets"][asset]["role"] = "original"
    state["track_info"] = {"speech": dict(label="Dialogue", depth=8)}
    with pytest.raises(ValueError, match="Layer 8"):
        mixing.split_source(state, "speech")


def test_import_fit_exact_and_cancellation_preserve_saved_state(client):
    api, folder, state = client
    url = f"/api/jobs/{folder.name}/lab"
    wav = io.BytesIO()
    sf.write(wav, np.full((4000, 1), .1, np.float32), 8000, format="WAV", subtype="FLOAT")
    body = dict(revision=1, track="ambience", fit="fit")
    assert api.post(url + "/import", data=body, files={"file": ("room.wav", wav.getvalue())}).status_code == 202
    assert api.delete(f"/api/jobs/{folder.name}").status_code == 409
    assert api.put(url, json=dict(revision=1, tracks=state["tracks"])).status_code == 409
    result = finish(api, folder)
    new = result["state"]
    assert new["revision"] == 2 and new["tracks"]["music"] == state["tracks"]["music"]
    asset = new["tracks"]["ambience"]["asset"]
    fitted, rate = sf.read(mixing.asset_path(folder / "lab", asset), always_2d=True)
    assert fitted.shape == (24000, 2) and rate == 8000
    np.testing.assert_allclose(fitted[:4000], .1)
    assert not fitted[4000:].any()
    assert api.post(url + "/actions/export", json=dict(revision=2)).status_code == 202
    api.post(url + "/cancel")
    assert api.get(url).json()["state"] == new
    assert api.get(url).json()["task"]["status"] == "cancelled"


def test_targeted_stem_preview_then_apply_keeps_other_channels_and_removed_separate(client):
    api, folder, state = client
    url = f"/api/jobs/{folder.name}/lab"
    payload = dict(revision=1, track="effects", prompt="water bubbling", strength=0, passes=2,
                   start=1, end=2, preview=True, device="cpu")
    assert api.post(url + "/actions/cleanup", json=payload).status_code == 202
    preview = finish(api, folder)["state"]
    selected = preview["assets"][preview["tracks"]["effects"]["asset"]]
    assert selected["role"] == "preview"
    assert preview["tracks"]["speech"] == state["tracks"]["speech"]
    assert preview["tracks"]["music"] == state["tracks"]["music"]
    assert api.post(url + "/actions/export", json=dict(revision=2)).status_code == 409
    changed = deepcopy(preview["tracks"])
    changed["effects"]["asset"] = selected["removed"]
    assert api.put(url, json=dict(revision=2, tracks=changed)).status_code == 400
    assert api.post(url + "/actions/cleanup", json={**payload, "revision": 2, "preview": False}).status_code == 202
    applied = finish(api, folder)["state"]
    clean = applied["assets"][applied["tracks"]["effects"]["asset"]]
    assert clean["parent"] == state["tracks"]["effects"]["asset"]
    assert clean["role"] == "cleaned" and clean["cleanup"]["passes"] == 2
    assert api.post(url + "/actions/export", json=dict(revision=3)).status_code == 202
    rendered = finish(api, folder)["state"]["export"]
    assert api.get(url + f"/exports/{rendered['id']}/mix.wav").status_code == 200
    assert "removed.wav" not in rendered["files"]


def test_import_exact_rejects_mismatch_without_changing_sources(tmp_path):
    folder, state = setup_session(tmp_path)
    task = folder / "lab/tasks" / ("b" * 32)
    task.mkdir(parents=True)
    sf.write(task / "upload.wav", np.zeros((10, 1)), 8000)
    write_json(task / "request.json", dict(operation="import", state=state, track="ambience", fit="exact",
                                           upload="upload.wav", filename="room.wav"))
    with pytest.raises(ValueError, match="different duration"):
        mixing.work(task)
    assert read_json(folder / "lab/state.json") == state


def test_failed_video_mux_keeps_audio_export_available(tmp_path, monkeypatch):
    import subprocess

    folder, state = setup_session(tmp_path)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("ffmpeg", 180)
    monkeypatch.setattr(mixing.subprocess, "run", timeout)
    result = mixing.render(folder / "lab", state, tmp_path / "export", lambda *_: None, video=folder / "bad.mp4")
    assert result["video_error"]
    assert "mix.wav" in result["files"] and "mixed-video.mp4" not in result["files"]
    assert (tmp_path / "export/mixing-lab.zip").is_file()


def test_finalization_recovers_after_state_was_saved_before_task_marker(client, monkeypatch):
    api, folder, state = client
    url = f"/api/jobs/{folder.name}/lab"
    assert api.post(url + "/actions/export", json=dict(revision=1)).status_code == 202
    info = read_json(folder / "lab/task.json")
    task = folder / "lab/tasks" / info["id"]
    mixing.work(task)
    server.LAB_PROCESSES[folder.name].returncode = 0
    original_write = lab_api.write_json
    failures = []
    def interrupted(path, value):
        if path.name == "task.json" and not failures:
            failures.append(True)
            raise OSError("Simulated interruption after saving state")
        original_write(path, value)
    monkeypatch.setattr(lab_api, "write_json", interrupted)
    with pytest.raises(OSError, match="Simulated"):
        api.get(url)
    saved = read_json(folder / "lab/state.json")
    assert saved["last_task"] == task.name
    recovered = api.get(url).json()
    assert recovered["task"]["status"] == "complete"
    assert recovered["state"] == saved
