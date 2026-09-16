import io
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from soundshredder import server
from soundshredder.audio import read_json, write_json


class FakeProcess:
    def __init__(self, *args, **kwargs):
        self.code = None

    def poll(self):
        return self.code

    def terminate(self):
        self.code = -1

    def wait(self, timeout):
        return self.code

    def kill(self):
        self.code = -9


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    monkeypatch.setattr(server, "PROCESSES", {})
    monkeypatch.setattr(server, "LISTENING_PROCESSES", {})
    # Mock the server's worker launcher without changing subprocess for PyTorch imports.
    monkeypatch.setattr(server, "subprocess", SimpleNamespace(
        Popen=FakeProcess, STDOUT=server.subprocess.STDOUT,
        TimeoutExpired=server.subprocess.TimeoutExpired,
        CREATE_NO_WINDOW=getattr(server.subprocess, "CREATE_NO_WINDOW", 0),
    ))
    with TestClient(server.app) as instance:
        yield instance


def wav():
    stream = io.BytesIO()
    sf.write(stream, np.zeros((80, 1)), 8000, format="WAV")
    return stream.getvalue()


def test_update_check_is_explicit_and_same_origin(client, monkeypatch):
    from soundshredder import __version__

    calls = []
    monkeypatch.setattr(server, "check_latest", lambda: calls.append(True) or {"status": "current"})
    system = client.get("/api/system").json()
    assert system["version"] == __version__ and system["features"]["update_check"]
    assert system["repository_url"] == "https://github.com/xD4O/SoundShredder"
    assert not calls
    assert client.post("/api/updates/check", headers={"Origin": "https://external.example"}).status_code == 403
    assert not calls
    assert client.post("/api/updates/check").json()["status"] == "current"
    assert len(calls) == 1


def test_upload_cancel_and_delete(client):
    response = client.post("/api/jobs", files={"file": ("../../clip.wav", wav())})
    assert response.status_code == 202
    job = response.json()["id"]
    status = client.get(f"/api/jobs/{job}").json()
    assert status["filename"] == "clip.wav" and status["status"] == "running"
    assert client.post("/api/jobs", files={"file": ("clip.wav", wav())}).status_code == 409
    assert client.delete(f"/api/jobs/{job}").status_code == 409
    assert client.post(f"/api/jobs/{job}/cancel").json()["status"] == "cancelled"
    assert client.delete(f"/api/jobs/{job}").status_code == 200
    assert client.get(f"/api/jobs/{job}").status_code == 404


def test_invalid_upload_and_levels(client, monkeypatch):
    assert client.post("/api/jobs", files={"file": ("script.py", b"anything")}).status_code == 400
    assert client.post("/api/jobs", files={"file": ("clip.wav", b"")}).status_code == 400
    assert client.post("/api/jobs", files={"file": ("clip.wav", wav())}, data={"speech": "nan"}).status_code == 400
    monkeypatch.setattr(server, "MAX_BYTES", 4)
    assert client.post("/api/jobs", files={"file": ("clip.wav", wav())}).status_code == 413
    assert client.get("/api/jobs").json() == []


def test_local_origin_and_download_paths(client):
    assert (
        client.post(
            "/api/jobs", headers={"Origin": "https://external.example"}, files={"file": ("clip.wav", wav())}
        ).status_code
        == 403
    )
    job = client.post("/api/jobs", files={"file": ("clip.wav", wav())}).json()["id"]
    assert client.get(f"/api/jobs/{job}/files/source.wav").status_code == 404
    assert client.get(f"/api/jobs/{job}/files/worker.log").status_code == 404
    assert client.get("/api/jobs/not-an-id").status_code == 404
    assert client.post(f"/api/jobs/{job}/mix", json={"speech": 1, "music": 0, "effects": 0}).status_code == 409
    assert client.post(f"/api/jobs/{job}/mix", json={"speech": 9, "music": 0, "effects": 0}).status_code == 422


@pytest.mark.parametrize("settings", [{"mode": "bad"}, {"mode": "bubble", "range_start": 11, "range_end": 7},
                                     {"bubble_strength": "nan"}, {"bubble_type": "bad"},
                                     {"bubble_passes": 0}, {"bubble_passes": 5},
                                     {"bubble_type": "popping", "bubble_passes": 2}])
def test_invalid_bubble_settings(client, settings):
    response = client.post("/api/jobs", files={"file": ("clip.wav", wav())}, data=settings)
    assert response.status_code == 400
    assert client.get("/api/jobs").json() == []


def test_bubble_api_remix_and_removed_download(client):
    job = client.post("/api/jobs", files={"file": ("clip.wav", wav())},
                      data={"mode": "bubble", "music": 0}).json()["id"]
    folder = server.DATA / job
    assert read_json(folder / "request.json")["gains"] == dict(speech=1, music=1, effects=1)
    (folder / "output").mkdir()
    (folder / "work").mkdir()
    sf.write(folder / "output/original.wav", np.ones((8000, 2), np.float32) * 0.1, 8000, subtype="FLOAT")
    sf.write(folder / "work/bubble-candidate.wav", np.ones((8000, 2), np.float32) * 0.05, 8000, subtype="FLOAT")
    write_json(folder / "separation.json", {"mode": "bubble", "bubble_type": "water"})
    write_json(folder / "progress.json", {"status": "complete"})
    levels = dict(speech=1, music=1, effects=1, bubble_strength=0.5, range_start=0.2, range_end=0.8)
    response = client.post(f"/api/jobs/{job}/mix", json=levels)
    assert response.status_code == 200
    mix = response.json()
    assert client.get(f"/api/jobs/{job}/files/{mix['removed']}").status_code == 200
    preview = client.get(f"/api/jobs/{job}/files/{mix['removed']}?preview=true", headers={"Range": "bytes=0-63"})
    assert preview.status_code == 206 and len(preview.content) == 64
    assert preview.headers["content-disposition"].startswith("inline;")
    assert client.get(f"/api/jobs/{job}/files/{mix['removed']}").headers["content-disposition"].startswith("attachment;")
    assert client.get(f"/api/jobs/{job}/files/bubble-candidate.wav").status_code == 404
    assert client.post(f"/api/jobs/{job}/mix", json={**levels, "range_end": 2}).status_code == 400
    assert read_json(folder / "mix.json") == mix
    assert client.post(f"/api/jobs/{job}/mix", json={**levels, "bubble_passes": 2}).status_code == 400
    assert read_json(folder / "mix.json") == mix


def test_listening_lifecycle_preserves_completed_cleanup(client):
    job = client.post("/api/jobs", files={"file": ("clip.wav", wav())}, data={"mode": "bubble"}).json()["id"]
    assert client.post(f"/api/jobs/{job}/listening").status_code == 409
    folder = server.DATA / job
    (folder / "output").mkdir()
    sf.write(folder / "output/removed-0123456789ab.wav", np.zeros((80, 1)), 8000)
    write_json(folder / "progress.json", {"status": "complete"})
    write_json(folder / "separation.json", {"mode": "bubble"})
    write_json(folder / "mix.json", {"revision": "0123456789ab", "removed": "removed-0123456789ab.wav"})
    server.PROCESSES[job].code = 0
    state = client.get(f"/api/jobs/{job}/listening").json()
    assert state["missing"] == ["speech", "music", "effects"]
    assert client.post(f"/api/jobs/{job}/listening").status_code == 202
    process = server.LISTENING_PROCESSES[job]
    assert client.post(f"/api/jobs/{job}/listening").json()["status"] == "running"
    assert server.LISTENING_PROCESSES[job] is process
    assert client.get(f"/api/jobs/{job}").json()["status"] == "complete"
    assert client.post("/api/jobs", files={"file": ("clip.wav", wav())}).status_code == 409
    assert client.post(f"/api/jobs/{job}/mix", json=dict(speech=1, music=1, effects=1)).status_code == 409
    assert client.delete(f"/api/jobs/{job}").status_code == 409
    assert client.post(f"/api/jobs/{job}/listening/cancel").json()["status"] == "cancelled"
    assert read_json(folder / "progress.json")["status"] == "complete"
    assert client.post(f"/api/jobs/{job}/listening").json()["status"] == "running"
    server.LISTENING_PROCESSES[job].code = 1
    assert client.get(f"/api/jobs/{job}/listening").json()["status"] == "failed"


def test_rerun_saved_source_creates_new_session_and_retains_previous(client):
    job = client.post("/api/jobs", files={"file": ("clip.wav", wav())}, data={"mode": "bubble"}).json()["id"]
    settings = dict(mode="bubble", device="cpu", cpu_fallback=True, bubble_type="water",
                    bubble_passes=3, bubble_strength=0.9, range_start=0.001, range_end=0.009)
    assert client.post(f"/api/jobs/{job}/rerun", json=settings).status_code == 409
    folder = server.DATA / job
    write_json(folder / "progress.json", {"status": "complete"})
    server.PROCESSES[job].code = 0
    before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    assert client.post(f"/api/jobs/{job}/rerun", json={**settings, "bubble_type": "cartoon"}).status_code == 400
    assert client.post(f"/api/jobs/{job}/rerun", json={**settings, "bubble_passes": 2.5}).status_code == 422
    assert len(client.get("/api/jobs").json()) == 1
    result = client.post(f"/api/jobs/{job}/rerun", json=settings)
    assert result.status_code == 202
    new = result.json()["id"]
    assert new != job
    request = read_json(server.DATA / new / "request.json")
    assert request["cleanup"] == dict(kind="water", passes=3, strength=0.9, start=0.001, end=0.009)
    assert request["device"] == "cpu" and request["filename"] == "clip.wav"
    assert (server.DATA / new / "source.wav").read_bytes() == before["source.wav"]
    assert {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()} == before
    assert client.post(f"/api/jobs/{job}/rerun", json=settings).status_code == 409
    client.post(f"/api/jobs/{new}/cancel")
    (folder / "source.wav").unlink()
    assert client.post(f"/api/jobs/{job}/rerun", json=settings).status_code == 404

def test_video_preview_streams_saved_upload_and_ranges(client):
    payload = b'0123456789abcdef'
    response = client.post('/api/jobs', files={'file': ('clip.mp4', payload, 'video/mp4')})
    job = response.json()['id']
    assert client.get(f'/api/jobs/{job}').json()['video_preview'] is True
    preview = client.get(f'/api/jobs/{job}/video')
    assert preview.status_code == 200 and preview.content == payload
    assert preview.headers['content-type'] == 'video/mp4'
    part = client.get(f'/api/jobs/{job}/video', headers={'Range': 'bytes=2-5'})
    assert part.status_code == 206 and part.content == b'2345'
    assert part.headers['content-range'] == 'bytes 2-5/16'
    (server.DATA / job / 'source.mp4').unlink()
    assert client.get(f'/api/jobs/{job}/video').status_code == 404


def test_video_preview_rejects_audio_and_source_outside_session(client, tmp_path):
    job = client.post('/api/jobs', files={'file': ('clip.wav', wav())}).json()['id']
    assert client.get(f'/api/jobs/{job}').json()['video_preview'] is False
    assert client.get(f'/api/jobs/{job}/video').status_code == 404
    outside = server.DATA / 'outside.mp4'
    outside.write_bytes(b'private')
    path = server.DATA / job / 'request.json'
    request = read_json(path)
    request['source'] = '../outside.mp4'
    write_json(path, request)
    assert client.get(f'/api/jobs/{job}/video').status_code == 404
    assert client.get('/api/jobs/not-a-session/video').status_code == 404
