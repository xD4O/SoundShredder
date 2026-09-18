"""Real child processes exercise slow setup, cancellation and safe retry."""
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from desktop import bootstrap


def wait_for(check, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.025)
    raise AssertionError("Setup did not respond within its deadline")


@pytest.fixture
def manager(tmp_path, monkeypatch):
    root = tmp_path / "App with spaces"
    (root / "python").mkdir(parents=True)
    (root / "python/python.exe").write_bytes(b"private runtime fixture")
    (root / "desktop/wheels").mkdir(parents=True)
    (root / "desktop/requirements.txt").write_text("audio-tools\n")
    (root / "desktop/wheels/bandit_infer-0.1.0.whl").write_bytes(b"wheel fixture")
    monkeypatch.setattr(bootstrap.shutil, "disk_usage", lambda _: SimpleNamespace(free=30 * 1024**3))
    return bootstrap.Manager(tmp_path / "Profile with spaces", root, system="win32")


@pytest.fixture
def server(manager):
    httpd = bootstrap.LocalServer(("127.0.0.1", 0), bootstrap.handler_for(manager))
    thread = threading.Thread(target=httpd.serve_forever)
    thread.start()
    def call(route, payload=None):
        return bootstrap.local_request(f"http://127.0.0.1:{httpd.server_port}" + route,
                                       token=manager.token, payload=payload, timeout=2)
    yield call
    manager.cleanup()
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def slow_installer(manager, monkeypatch):
    original = manager.run
    slow = [True]
    def run(_args, **kwargs):
        code = "import time; print('Downloading torch-1.0.whl', flush=True); print('Progress 4096 of 8192', flush=True); "
        code += "time.sleep(30)" if slow[0] else "print('Progress 8192 of 8192', flush=True)"
        return original([sys.executable, "-u", "-c", code], **kwargs)
    monkeypatch.setattr(manager, "run", run)
    monkeypatch.setattr(manager, "launch", lambda _: manager.update("ready", "Ready", 100))
    return slow


def test_progress_state_and_diagnostics_remain_responsive_during_cancel_and_repair(manager, server, monkeypatch):
    slow = slow_installer(manager, monkeypatch)
    data = manager.home / "data/session/original.wav"
    data.parent.mkdir(parents=True)
    data.write_bytes(b"user audio must remain unchanged")
    server("/api/start", {"device": "cpu"})
    wait_for(lambda: manager.state()["download"])
    command = manager.command
    for _ in range(5):
        before = time.monotonic()
        state = server("/api/state")
        assert state["can_cancel"] and state["download"]["received"] == 4096
        assert "Progress" in server("/api/diagnostics")["text"]
        assert time.monotonic() - before < 1
    runtime = manager.runtime_path("cpu")
    partial = runtime / "incomplete-package.txt"
    partial.write_text("interrupted package")
    before = time.monotonic()
    server("/api/cancel-setup", {})
    assert time.monotonic() - before < 1
    wait_for(lambda: manager.finished.is_set())
    assert command.poll() is not None and manager.command is None
    assert manager.state()["status"] == "idle"
    assert manager.interrupted.exists() and (runtime / ".setup-incomplete").exists()
    slow[0] = False
    server("/api/start", {"device": "cpu"})
    wait_for(lambda: manager.state()["status"] == "ready" and manager.finished.is_set())
    assert not partial.exists() and not (runtime / ".setup-incomplete").exists()
    assert (runtime / "ready.json").exists() and not manager.interrupted.exists()
    assert data.read_bytes() == b"user audio must remain unchanged"


def test_cancel_and_quit_waits_for_owned_installer_to_exit(manager, server, monkeypatch):
    slow_installer(manager, monkeypatch)
    server("/api/start", {"device": "cpu"})
    wait_for(lambda: manager.state()["download"])
    command = manager.command
    assert server("/api/stop", {"cancel_setup": True})["ok"]
    assert manager.finished.is_set() and command.poll() is not None
    assert manager.state()["status"] == "closing"


def test_shutdown_acknowledges_client_before_server_can_exit(manager):
    shutdown_entered = threading.Event()
    base = bootstrap.handler_for(manager)
    class SlowResponse(base):
        def send(self, status, content, content_type="application/json"):
            if self.path == "/api/stop" and status == 200:
                time.sleep(.05)  # Give a prematurely started shutdown time to race.
                assert not shutdown_entered.is_set()
            super().send(status, content, content_type)
    httpd = bootstrap.LocalServer(("127.0.0.1", 0), SlowResponse)
    shutdown = httpd.shutdown
    def observed_shutdown():
        shutdown_entered.set()
        shutdown()
    httpd.shutdown = observed_shutdown
    thread = threading.Thread(target=httpd.serve_forever)
    thread.start()
    try:
        result = bootstrap.local_request(f"http://127.0.0.1:{httpd.server_port}/api/stop",
                                         token=manager.token, payload={}, timeout=2)
        assert result == {"ok": True}
        assert shutdown_entered.wait(2)
    finally:
        shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("active", [False, True])
def test_silent_or_chatty_stalled_command_is_killed_with_a_clear_error(manager, active):
    code = "import time\nwhile True:\n print('still working', flush=True)\n time.sleep(.04)" if active else "import time; time.sleep(30)"
    before = time.monotonic()
    with pytest.raises(RuntimeError, match="took too long" if active else "stopped reporting activity"):
        manager.run([sys.executable, "-u", "-c", code], timeout=.6 if active else 10, idle_timeout=3 if active else .4)
    assert time.monotonic() - before < 5
    assert manager.command is None


def test_failed_base_copy_is_rebuilt_even_if_python_executable_was_copied(manager, monkeypatch):
    (manager.root / "python/second-file.dll").write_bytes(b"runtime contents")
    copy = manager.copy_runtime_file
    def interrupted(source, target):
        copy(source, target)
        raise bootstrap.SetupCancelled()
    monkeypatch.setattr(manager, "copy_runtime_file", interrupted)
    with pytest.raises(bootstrap.SetupCancelled):
        manager.prepare_runtime("cpu")
    runtime = manager.runtime_path("cpu")
    assert (runtime / ".copy-incomplete").exists()
    monkeypatch.setattr(manager, "copy_runtime_file", copy)
    manager.prepare_runtime("cpu")
    assert (runtime / "python.exe").exists() and (runtime / "second-file.dll").exists()
    assert not (runtime / ".copy-incomplete").exists()


def test_runtime_repair_cannot_delete_a_session_folder(manager):
    folder = manager.home / "data"
    folder.mkdir()
    (folder / ".setup-incomplete").touch()
    (folder / "original.wav").write_bytes(b"keep")
    with pytest.raises(RuntimeError, match="redirected"):
        manager.repair_interrupted_runtime(folder)
    assert (folder / "original.wav").read_bytes() == b"keep"


def test_low_space_is_checked_before_copying_runtime(manager, monkeypatch):
    monkeypatch.setattr(bootstrap.shutil, "disk_usage", lambda _: SimpleNamespace(free=1024**3))
    manager.setup()
    assert manager.status == "error" and "4 GiB" in manager.message
    assert not manager.runtime_path("cpu").exists()


def test_state_polling_does_not_probe_a_slow_disk(manager, monkeypatch):
    def blocked(_):
        raise AssertionError("A state request must not touch the disk")
    monkeypatch.setattr(bootstrap.shutil, "disk_usage", blocked)
    assert manager.state()["free_gib"] == 30


def test_startup_readiness_uses_a_wall_clock_deadline_and_reaps_its_child(manager):
    (manager.root / "desktop/serve.py").write_text("import sys; sys.stdin.buffer.read()")
    before = time.monotonic()
    with pytest.raises(RuntimeError, match="too long to start"):
        manager.launch(sys.executable, timeout=.3)
    assert time.monotonic() - before < 4
    assert manager.process.poll() is not None


def test_interrupted_setup_does_not_restart_automatically_on_reopen(tmp_path):
    bootstrap.write_json(tmp_path / "settings.json", {"device": "cpu"})
    bootstrap.write_json(tmp_path / "setup-interrupted.json", {"device": "cpu"})
    python = getattr(sys, "_base_executable", sys.executable)
    process = subprocess.Popen([python, str(Path(bootstrap.__file__).resolve()), "--home", str(tmp_path), "--no-browser"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=bootstrap.FLAGS)
    try:
        instance = wait_for(lambda: bootstrap.existing_instance(tmp_path))
        assert instance["state"]["status"] == "idle"
        assert "Previous setup" in instance["state"]["message"]
        bootstrap.local_request(instance["base"] + "/api/stop", token=instance["token"], payload={})
        process.wait(timeout=5)
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
