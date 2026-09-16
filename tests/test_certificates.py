import os
import shutil
import ssl
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from soundshredder import certificates


@pytest.fixture(autouse=True)
def clean_certificate_environment(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)


def test_existing_mac_roots_are_preserved(monkeypatch):
    monkeypatch.setattr(certificates.ssl, "create_default_context", lambda: SimpleNamespace(cert_store_stats=lambda: {"x509_ca": 10}))
    monkeypatch.setattr(certificates.importlib, "import_module", lambda _: pytest.fail("Do not replace existing roots"))
    assert certificates.mac_certificate_bundle("darwin") is None


@pytest.mark.parametrize("variable", ["SSL_CERT_FILE", "SSL_CERT_DIR"])
def test_explicit_ca_settings_are_not_overwritten(monkeypatch, variable):
    monkeypatch.setenv(variable, "/custom/company/certificates")
    monkeypatch.setattr(certificates.ssl, "create_default_context", lambda: pytest.fail("Keep explicit settings"))
    assert certificates.mac_certificate_bundle("darwin") is None
    assert certificates.os.environ[variable] == "/custom/company/certificates"


@pytest.mark.parametrize("vendor_fallback", [False, True])
def test_missing_roots_use_verified_bundle_without_changing_tls_checks(monkeypatch, vendor_fallback):
    import certifi

    original_context = ssl.create_default_context
    verified = []
    def context(*, cafile=None):
        if cafile is None:
            return SimpleNamespace(cert_store_stats=lambda: {"x509_ca": 0})
        result = original_context(cafile=cafile)
        verified.append(result)
        return result
    def load(name):
        if vendor_fallback and name == "certifi":
            raise ImportError("not separately installed")
        return certifi
    monkeypatch.setattr(certificates.ssl, "create_default_context", context)
    monkeypatch.setattr(certificates.importlib, "import_module", load)
    monkeypatch.setattr(certificates.sys, "platform", "darwin")
    bundle = certificates.configure_macos_certificates()
    assert bundle and certificates.os.environ["SSL_CERT_FILE"] == bundle
    assert verified[0].verify_mode == ssl.CERT_REQUIRED
    assert verified[0].check_hostname is True
    assert verified[0].cert_store_stats()["x509_ca"] > 0


def test_missing_all_bundles_gives_mac_repair_steps(monkeypatch):
    monkeypatch.setattr(certificates.ssl, "create_default_context", lambda: SimpleNamespace(cert_store_stats=lambda: {"x509_ca": 0}))
    def missing(_):
        raise ImportError("missing")
    monkeypatch.setattr(certificates.importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="Install Certificates.command"):
        certificates.mac_certificate_bundle("darwin")


def test_non_mac_does_not_change_certificate_settings(monkeypatch):
    monkeypatch.setattr(certificates.ssl, "create_default_context", lambda: pytest.fail("Mac-only fix"))
    assert certificates.mac_certificate_bundle("win32") is None
    assert certificates.mac_certificate_bundle("linux") is None


@pytest.mark.parametrize("mode", ["fallback", "custom", "failure"])
def test_repair_launcher_inherits_ca_into_existing_app(tmp_path, mode):
    from scripts.package_mac_certificate_fix import launcher

    bash = Path("C:/Program Files/Git/bin/bash.exe") if os.name == "nt" else Path(shutil.which("bash") or "")
    if not bash.is_file():
        pytest.skip("Bash is required for the launcher fixture")
    app = tmp_path / "Source folder with spaces"
    (app / ".venv/bin").mkdir(parents=True)
    (app / "fakebin").mkdir()
    (app / "app.py").write_text("fixture")
    (app / "repair.command").write_text(launcher(), encoding="utf-8", newline="\n")
    (app / "fakebin/uname").write_text("#!/bin/bash\nprintf 'Darwin\\n'\n", newline="\n")
    fallback = "printf '/trusted bundle/cacert.pem\\n'" if mode == "fallback" else "true"
    if mode == "failure":
        fallback = "exit 1"
    (app / ".venv/bin/python").write_text(
        '#!/bin/bash\nif [ "$1" = "-" ]; then\n cat >/dev/null\n ' + fallback +
        '\nelse printf "%s" "${SSL_CERT_FILE:-}" > launched-with-ca.txt; fi\n', newline="\n")
    for executable in (app / "fakebin/uname", app / ".venv/bin/python"):
        executable.chmod(0o755)
    env = os.environ.copy()
    if mode == "custom":
        env["SSL_CERT_FILE"] = "/company/custom.pem"
    result = subprocess.run([str(bash), "-c", 'export PATH="$PWD/fakebin:/usr/bin:/bin"; bash repair.command'],
                            cwd=app, env=env, capture_output=True, text=True, timeout=15)
    if mode == "failure":
        assert result.returncode == 1 and not (app / "launched-with-ca.txt").exists()
    else:
        assert result.returncode == 0, result.stderr
        assert (app / "launched-with-ca.txt").read_text() == (
            "/trusted bundle/cacert.pem" if mode == "fallback" else "/company/custom.pem")
