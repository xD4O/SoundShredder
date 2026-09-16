import json
import os
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from desktop.bootstrap import Manager, acquire_lock, default_home, handler_for


@pytest.fixture
def setup_server(tmp_path):
    manager = Manager(tmp_path / "user", tmp_path / "app")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(manager))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield manager, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_setup_requires_token_and_rejects_cross_origin_and_host(setup_server):
    manager, url = setup_server
    for headers in ({}, {"X-Setup-Token": "wrong"}, {"Host": "evil.example", "X-Setup-Token": manager.token}):
        with pytest.raises(HTTPError) as exc:
            urlopen(Request(url + "/api/state", headers=headers))
        assert exc.value.code == 403
    with urlopen(Request(url + "/api/state", headers={"X-Setup-Token": manager.token})) as response:
        assert json.load(response)["status"] == "idle"
    with pytest.raises(HTTPError) as exc:
        urlopen(Request(url + "/api/start", data=b'{"device":"cpu"}',
                        headers={"X-Setup-Token": manager.token, "Origin": "https://evil.example"}))
    assert exc.value.code == 403


def test_setup_rejects_invalid_device_and_duplicate_start(tmp_path, monkeypatch):
    manager = Manager(tmp_path)
    with pytest.raises(ValueError):
        manager.start("shell")
    monkeypatch.setattr(manager, "setup", lambda: None)
    manager.start("cpu")
    with pytest.raises(ValueError, match="already"):
        manager.start("cuda")
    with pytest.raises(ValueError, match="Wait"):
        manager.stop()


def test_failed_setup_can_retry_without_ready_marker(tmp_path):
    manager = Manager(tmp_path / "user", tmp_path / "missing-app")
    manager.setup()
    assert manager.state()["status"] == "error"
    assert not list(manager.home.rglob("ready.json"))
    assert "FileNotFoundError" in manager.diagnostics()


def test_embedded_runtime_is_private_and_can_follow_moved_app(tmp_path):
    root = tmp_path / "app with spaces"
    (root / "python").mkdir(parents=True)
    (root / "python" / "python.exe").write_bytes(b"fixture")
    manager = Manager(tmp_path / "user", root)
    runtime = manager.prepare_runtime("cpu")
    assert runtime.is_relative_to(manager.home)
    assert str(root) in (runtime / "python313._pth").read_text()
    (runtime / "sentinel").write_text("keep dependencies")
    moved = Manager(manager.home, tmp_path / "new app")
    moved.prepare_runtime("cpu")
    assert str(moved.root) in (runtime / "python313._pth").read_text()
    assert (runtime / "sentinel").read_text() == "keep dependencies"
    assert "import site" not in (runtime / "python313._pth").read_text()


def test_stopped_app_is_reported_as_retryable(tmp_path):
    from types import SimpleNamespace
    manager = Manager(tmp_path)
    manager.status, manager.url = "ready", "http://127.0.0.1:1234"
    manager.process = SimpleNamespace(poll=lambda: 1)
    assert manager.state()["status"] == "error"
    assert manager.url is None


def test_close_refuses_to_interrupt_audio_job(tmp_path, monkeypatch):
    from contextlib import closing
    from io import BytesIO
    from types import SimpleNamespace
    manager = Manager(tmp_path)
    manager.status, manager.url = "ready", "http://127.0.0.1:1234"
    stopped = []
    manager.process = SimpleNamespace(poll=lambda: None, terminate=lambda: stopped.append(True))
    monkeypatch.setattr("desktop.bootstrap.urllib.request.urlopen", lambda *a, **k: closing(BytesIO(b'{"active_jobs":["job"]}')))
    with pytest.raises(ValueError, match="Finish or cancel"):
        manager.stop()
    assert not stopped and not manager.stopping


@pytest.mark.skipif(os.name != "nt", reason="Windows byte-range instance lock")
def test_second_process_does_not_read_the_locked_byte(tmp_path):
    lock = acquire_lock(tmp_path)
    assert lock is not None
    try:
        result = subprocess.run([sys.executable, "-c",
            "from pathlib import Path; import sys; from desktop.bootstrap import acquire_lock; "
            "assert acquire_lock(Path(sys.argv[1])) is None", str(tmp_path)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
    finally:
        lock.close()
    replacement = acquire_lock(tmp_path)
    assert replacement is not None
    replacement.close()


def mac_fixture(tmp_path, machine="arm64"):
    root = tmp_path / "Sound Shredder.app" / "Contents" / "Resources"
    (root / "python/bin").mkdir(parents=True)
    (root / "python/bin/python3.11").write_bytes(b"fixture")
    (root / "desktop/wheels").mkdir(parents=True)
    (root / "desktop/platform.json").write_text(json.dumps({"machine": machine}))
    (root / "desktop/requirements.txt").write_text("fastapi\n")
    (root / "desktop/wheels/bandit_infer-0.1.0-py3-none-any.whl").write_bytes(b"wheel fixture")
    return Manager(tmp_path / "Library/Application Support/SoundShredder", root, system="darwin", machine=machine)


def test_mac_storage_and_cpu_only(tmp_path):
    assert str(default_home("darwin")).endswith(str(os.path.join("Library", "Application Support", "SoundShredder")))
    manager = mac_fixture(tmp_path)
    with pytest.raises(ValueError, match="CPU"):
        manager.start("cuda")
    state = manager.state()
    assert state["platform"] == "darwin" and not state["nvidia"]
    assert state["required_gib"]["cpu"] == 3
    assert state["home"] == str(manager.home) and state["free_gib"] >= 0


def test_mac_runtime_is_private_and_follows_moved_bundle(tmp_path):
    manager = mac_fixture(tmp_path)
    runtime = manager.prepare_runtime("cpu")
    assert runtime.is_relative_to(manager.home)
    assert manager.runtime_python(runtime).exists()
    path_file = runtime / "lib/python3.11/site-packages/soundshredder-app.pth"
    assert path_file.read_text().strip() == str(manager.root)
    moved_root = tmp_path / "Applications/New name.app/Contents/Resources"
    (moved_root / "desktop").mkdir(parents=True)
    (moved_root / "desktop/platform.json").write_text('{"machine":"arm64"}')
    moved = Manager(manager.home, moved_root, system="darwin", machine="arm64")
    assert moved.prepare_runtime("cpu") == runtime
    assert path_file.read_text().strip() == str(moved_root)
    assert moved.python_command(moved.runtime_python(runtime))[-1] == "-I"
    moved.machine = "x86_64"
    with pytest.raises(ValueError, match="different Mac processor"):
        moved.prepare_runtime("cpu")


@pytest.mark.parametrize("machine,torch", [("arm64", "2.8.0"), ("x86_64", "2.2.2")])
def test_mac_setup_uses_native_wheels_no_shared_cache_and_reuses_engine(tmp_path, monkeypatch, machine, torch):
    from types import SimpleNamespace
    manager = mac_fixture(tmp_path, machine)
    calls, launches = [], []
    monkeypatch.setattr("desktop.bootstrap.shutil.disk_usage", lambda _: SimpleNamespace(free=20 * 1024**3))
    monkeypatch.setattr(manager, "run", lambda args, **kwargs: calls.append(args))
    monkeypatch.setattr(manager, "launch", lambda python: launches.append(python))
    manager.setup()
    assert len(calls) == 3 and len(launches) == 1
    for command in calls[:2]:
        assert command[1:4] == ["-I", "-m", "pip"]
        assert "--no-cache-dir" in command and "--only-binary=:all:" in command
        assert "--isolated" in command and f"torch=={torch}" in command
        assert "https://pypi.org/simple" in command
        assert not any("cu128" in arg for arg in command)
    calls.clear()
    # A cached engine can reopen without reserving the full installation budget.
    monkeypatch.setattr("desktop.bootstrap.shutil.disk_usage", lambda _: SimpleNamespace(free=500 * 1024**2))
    manager.setup()
    assert len(calls) == 1 and len(launches) == 2
    assert calls[0][2] == "-c"


def test_mac_low_space_does_not_download_packages(tmp_path, monkeypatch):
    from types import SimpleNamespace
    manager = mac_fixture(tmp_path)
    monkeypatch.setattr("desktop.bootstrap.shutil.disk_usage", lambda _: SimpleNamespace(free=1024**3))
    calls = []
    monkeypatch.setattr(manager, "run", lambda *a, **k: calls.append(a))
    manager.setup()
    assert manager.status == "error" and "3 GiB" in manager.message
    assert not calls


def test_posix_lock_is_nonblocking_and_released_on_conflict(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from desktop import bootstrap
    calls = []
    def flock(fd, flags):
        calls.append((fd, flags))
        if len(calls) > 1:
            raise BlockingIOError("busy")
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(flock=flock, LOCK_EX=2, LOCK_NB=4))
    monkeypatch.setattr(bootstrap.sys, "platform", "darwin")
    lock = acquire_lock(tmp_path)
    try:
        assert lock is not None
        assert acquire_lock(tmp_path) is None
        assert calls[0][1] == 6
    finally:
        lock.close()
