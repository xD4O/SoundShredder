import json
import subprocess
import sys

import pytest

from desktop.bootstrap import Manager
from scripts import verify_mac_distribution as distribution


def test_desktop_imports_and_child_workers_do_not_modify_app(tmp_path):
    app = tmp_path / "App with spaces"
    app.mkdir()
    (app / "fixture_module.py").write_text("VALUE = 7\n")
    manager = Manager(tmp_path / "profile", app, system="darwin", machine="arm64")
    child = f"import sys; sys.path.insert(0, {str(app)!r}); import fixture_module"
    code = child + "; import subprocess; subprocess.run([sys.executable, '-c', " + repr(child) + "], check=True)"
    subprocess.run([*manager.python_command(sys.executable), "-c", code], env=manager.environment(), check=True)
    assert not list(app.rglob("*.pyc"))
    assert not (app / "__pycache__").exists()


@pytest.fixture
def bundle(tmp_path):
    app = tmp_path / "SoundShredder.app"
    binary = app / "Contents/MacOS/SoundShredder"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(bytes.fromhex("cffaedfe") + b"fixture")
    (app / "Contents/Info.plist").write_text("text resource")
    return app


def test_native_scan_includes_python_extension_modules(bundle):
    module = bundle / "Contents/Resources/backend/python/lib/test.so"
    module.parent.mkdir(parents=True)
    module.write_bytes(bytes.fromhex("feedfacf") + b"fixture")
    assert set(distribution.native_files(bundle)) == {module, bundle / "Contents/MacOS/SoundShredder"}


def simulated_run(*args, required=True):
    blocked = args[0] in {"/usr/sbin/spctl", "/usr/bin/xcrun"}
    return {"returncode": int(blocked), "output": "not notarized" if blocked else "valid"}


def test_valid_adhoc_signature_is_not_reported_as_apple_trusted(bundle, monkeypatch):
    monkeypatch.setattr(distribution, "run", simulated_run)
    result = distribution.verify_bundle(bundle)
    assert result["integrity"] == "passed"
    assert result["notarized_distribution_ready"] is False
    with pytest.raises(RuntimeError, match="Distribution blocked"):
        distribution.verify_bundle(bundle, require_notarized=True)


def test_broken_signature_fails_even_in_preview_mode(bundle, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("invalid signature")
    monkeypatch.setattr(distribution, "run", broken)
    with pytest.raises(RuntimeError, match="invalid signature"):
        distribution.verify_bundle(bundle)


def test_notarized_gate_requires_both_gatekeeper_and_stapled_ticket(bundle, monkeypatch):
    def trusted(*args, **kwargs):
        return {"returncode": 0, "output": "accepted"}
    monkeypatch.setattr(distribution, "run", trusted)
    assert distribution.verify_bundle(bundle, require_notarized=True)["notarized_distribution_ready"]
    def missing_ticket(*args, **kwargs):
        return simulated_run(*args, **kwargs) if args[0] == "/usr/bin/xcrun" else trusted(*args, **kwargs)
    monkeypatch.setattr(distribution, "run", missing_ticket)
    with pytest.raises(RuntimeError, match="Distribution blocked"):
        distribution.verify_bundle(bundle, require_notarized=True)


def test_verification_failure_is_saved_for_ci(tmp_path, monkeypatch):
    monkeypatch.setattr(distribution, "WORK", tmp_path)
    monkeypatch.setattr(distribution.sys, "platform", "darwin")
    monkeypatch.setattr(distribution.sys, "argv", ["verify_mac_distribution.py"])
    def broken(*args, **kwargs):
        raise RuntimeError("archive failure")
    monkeypatch.setattr(distribution, "verify_archives", broken)
    with pytest.raises(RuntimeError, match="archive failure"):
        distribution.main()
    report = json.loads((tmp_path / "verification/mac-distribution.json").read_text())
    assert report["status"] == "failed" and report["error"] == "archive failure"
