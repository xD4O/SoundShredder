import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from desktop import bootstrap


def wait_for(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError):
            pass
        time.sleep(.05)
    raise AssertionError("Lifecycle operation timed out")


def test_real_process_close_reopen_duplicate_and_crash_recovery(tmp_path):
    home = (tmp_path / "Profile with spaces").resolve()
    home.mkdir()
    # Leftovers from an old/crashed process must not block or redirect startup.
    (home / "desktop.json").write_text('{"pid":123,"url":"https://example.invalid/#old"}')
    (home / "desktop.lock").write_bytes(b"0")
    script = Path(bootstrap.__file__).resolve()
    python = getattr(sys, "_base_executable", sys.executable) if os.name == "nt" else sys.executable
    trace = "import faulthandler,runpy,sys; faulthandler.dump_traceback_later(10); sys.argv[0]=" + repr(str(script)) + "; runpy.run_path(sys.argv[0],run_name='__main__')"
    command = [python, "-c", trace, "--home", str(home), "--no-browser"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    ids = []
    for cycle in range(3):
        log = (tmp_path / f"child-{cycle}.log").open("w+")
        process = subprocess.Popen(command, creationflags=flags, stdout=log, stderr=subprocess.STDOUT)
        try:
            try:
                instance = wait_for(lambda: bootstrap.existing_instance(home))
            except AssertionError:
                log.seek(0)
                raise AssertionError(f"Child exit: {process.poll()}; output: {log.read()}; metadata: {bootstrap.read_json(home / 'desktop.json')}") from None
            ids.append(instance["saved"]["pid"])
            assert instance["saved"]["pid"] == process.pid
            again = subprocess.run(command, capture_output=True, timeout=15, creationflags=flags)
            assert again.returncode == 0, again.stderr
            assert bootstrap.existing_instance(home)["saved"]["pid"] == process.pid
            if cycle == 1:
                process.kill()  # OS releases the lock even if metadata remains.
            else:
                bootstrap.local_request(instance["base"] + "/api/stop", token=instance["token"], payload={})
            process.wait(timeout=15)
            if cycle != 1:
                assert not (home / "desktop.json").exists()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            log.close()
    assert len(set(ids)) == 3


@pytest.mark.parametrize("url", ["https://example.com/#secret", "http://localhost:1234/#secret", "http://127.0.0.1:1234@evil.test/#secret", "file:///tmp/a#secret"])
def test_stale_metadata_cannot_open_or_send_credentials_elsewhere(tmp_path, url):
    (tmp_path / "desktop.json").write_text(json.dumps({"pid": 123, "url": url}))
    assert bootstrap.existing_instance(tmp_path) is None


def test_claim_retries_when_old_instance_is_closing(tmp_path, monkeypatch):
    acquired = object()
    results = iter([None, None, acquired])
    monkeypatch.setattr(bootstrap, "acquire_lock", lambda _: next(results))
    monkeypatch.setattr(bootstrap, "existing_instance", lambda _: None)
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _: None)
    lock, existing = bootstrap.claim_instance(tmp_path)
    assert lock is acquired and existing is None


def test_unresponsive_owner_produces_actionable_error_without_killing_any_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "acquire_lock", lambda _: None)
    monkeypatch.setattr(bootstrap, "existing_instance", lambda _: None)
    with pytest.raises(RuntimeError, match="not responding"):
        bootstrap.claim_instance(tmp_path, timeout=0)


def test_reopen_restarts_a_dead_workspace_but_not_a_failed_install(tmp_path, monkeypatch):
    from types import SimpleNamespace
    manager = bootstrap.Manager(tmp_path)
    started = []
    monkeypatch.setattr(manager, "start", lambda device: started.append(device))
    manager.status = "error"
    manager.reopen()
    assert not started
    manager.process = SimpleNamespace(poll=lambda: 1)
    manager.reopen()
    assert started == ["cpu"]


def test_closing_cannot_start_new_work(tmp_path):
    manager = bootstrap.Manager(tmp_path)
    manager.stop()
    assert manager.state()["status"] == "closing"
    with pytest.raises(ValueError, match="closing"):
        manager.start("cpu")


def test_custom_mac_certificate_settings_survive_relaunch(tmp_path, monkeypatch):
    manager = bootstrap.Manager(tmp_path, system="darwin")
    python = tmp_path / "runtime/bin/python3.11"
    cert = python.parent.parent / "lib/python3.11/site-packages/pip/_vendor/certifi/cacert.pem"
    cert.parent.mkdir(parents=True)
    cert.write_text("bundle")
    monkeypatch.setenv("SSL_CERT_FILE", "/trusted/company.pem")
    assert manager.environment(python)["SSL_CERT_FILE"] == "/trusted/company.pem"


def test_atomic_metadata_retries_windows_sharing_failure(tmp_path, monkeypatch):
    path = tmp_path / "desktop.json"
    replace = os.replace
    calls = []
    def transient(source, target):
        calls.append(source)
        if len(calls) < 3:
            raise PermissionError("Sharing violation")
        replace(source, target)
    monkeypatch.setattr(bootstrap.os, "replace", transient)
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _: None)
    bootstrap.write_json(path, {"pid": 123})
    assert bootstrap.read_json(path)["pid"] == 123
    assert list(tmp_path.iterdir()) == [path]


def test_local_lifecycle_requests_reject_redirects(tmp_path):
    from http.server import BaseHTTPRequestHandler
    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "https://example.invalid")
            self.end_headers()
        def log_message(self, *args):
            pass
    server = bootstrap.LocalServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with pytest.raises(bootstrap.urllib.error.HTTPError) as exc:
            bootstrap.local_request(f"http://127.0.0.1:{server.server_port}/", token="private")
        assert exc.value.code == 302
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_local_server_startup_never_uses_network_name_resolution(tmp_path, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Local startup must not do a reverse DNS lookup")
    monkeypatch.setattr(bootstrap.socket, "getfqdn", forbidden)
    manager = bootstrap.Manager(tmp_path)
    with bootstrap.LocalServer(("127.0.0.1", 0), bootstrap.handler_for(manager)) as server:
        assert server.server_name == "127.0.0.1" and server.server_port > 0


def test_hosted_manager_exits_when_desktop_pipe_closes_and_can_relaunch(tmp_path):
    script = Path(bootstrap.__file__).resolve()
    python = getattr(sys, "_base_executable", sys.executable) if os.name == "nt" else sys.executable
    command = [python, str(script), "--no-browser", "--hosted", "--exclusive", "--home", str(tmp_path)]
    for _ in range(2):
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            current = wait_for(lambda: bootstrap.existing_instance(tmp_path))
            assert current["saved"]["pid"] == process.pid
            duplicate = subprocess.run(command, capture_output=True, timeout=20)
            assert duplicate.returncode != 0 and b"Another SoundShredder standalone" in duplicate.stderr
            assert bootstrap.existing_instance(tmp_path)["saved"]["pid"] == process.pid
            process.stdin.close()
            process.wait(timeout=20)
            assert process.returncode == 0, process.stderr.read().decode()
            assert not (tmp_path / "desktop.json").exists()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
