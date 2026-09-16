import errno
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from soundshredder import audio


def windows_lock_error(code):
    error = PermissionError(errno.EACCES, "File is temporarily locked")
    error.winerror = code
    return error


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_atomic_json_retries_windows_locks_without_truncating(tmp_path, monkeypatch, winerror):
    path = tmp_path / "progress.json"
    audio.write_json(path, {"status": "old"})
    original_replace = Path.replace
    attempts, delays = [], []

    def replace(source, destination):
        attempts.append(source)
        if len(attempts) <= 2:
            assert audio.read_json(destination) == {"status": "old"}
            raise windows_lock_error(winerror)
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(audio.time, "sleep", delays.append)
    audio.write_json(path, {"status": "complete", "message": "音声 ready"})
    assert audio.read_json(path) == {"status": "complete", "message": "音声 ready"}
    assert len(attempts) == 3 and delays == list(audio._JSON_RETRY_DELAYS[:2])
    assert not list(tmp_path.glob("*.tmp"))


def test_permanent_lock_is_bounded_and_preserves_previous_json(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    audio.write_json(path, {"status": "old"})
    attempts, delays = [], []
    failure = windows_lock_error(5)

    def locked(source, destination):
        attempts.append(source)
        raise failure

    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr(audio.time, "sleep", delays.append)
    with pytest.raises(PermissionError) as raised:
        audio.write_json(path, {"status": "new"})
    assert raised.value is failure
    assert len(attempts) == len(audio._JSON_RETRY_DELAYS) + 1
    assert delays == list(audio._JSON_RETRY_DELAYS)
    assert audio.read_json(path) == {"status": "old"}
    assert not list(tmp_path.glob("*.tmp"))


def test_other_io_errors_fail_immediately_without_losing_previous_json(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    audio.write_json(path, {"status": "old"})
    failure = OSError(errno.ENOSPC, "Disk full")

    def full(source, destination):
        raise failure

    monkeypatch.setattr(Path, "replace", full)
    monkeypatch.setattr(audio.time, "sleep", lambda _: pytest.fail("Unrelated errors must not be retried"))
    with pytest.raises(OSError) as raised:
        audio.write_json(path, {"status": "new"})
    assert raised.value is failure
    assert audio.read_json(path) == {"status": "old"}
    assert not list(tmp_path.glob("*.tmp"))


def test_concurrent_writers_use_independent_temporary_files(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    audio.write_json(path, {"status": "old"})
    original_replace = Path.replace
    rendezvous = threading.Barrier(2)
    state = threading.local()
    temporary_paths = set()

    def replace(source, destination):
        if not getattr(state, "staged", False):
            state.staged = True
            temporary_paths.add(source)
            rendezvous.wait(timeout=5)
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", replace)
    values = [{"writer": i, "content": str(i) * 10000} for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(audio.write_json, path, value) for value in values]
        for future in futures:
            future.result(timeout=10)
    assert len(temporary_paths) == 2
    assert audio.read_json(path) in values
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows delete-sharing semantics")
def test_real_windows_reader_lock_retries_until_handle_closes(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    audio.write_json(path, {"status": "old"})
    original_replace = Path.replace
    denied = threading.Event()
    errors = []

    def replace(source, destination):
        try:
            return original_replace(source, destination)
        except OSError as exc:
            errors.append(getattr(exc, "winerror", None))
            denied.set()
            raise

    monkeypatch.setattr(Path, "replace", replace)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with path.open("rb") as reader:
            pending = pool.submit(audio.write_json, path, {"status": "complete"})
            assert denied.wait(timeout=5), "Reader should deny replacement on Windows"
            assert b'"old"' in reader.read()
            assert not pending.done()
        pending.result(timeout=5)
    assert errors and all(code in {5, 32, 33} for code in errors)
    assert audio.read_json(path) == {"status": "complete"}
    assert not list(tmp_path.glob("*.tmp"))
