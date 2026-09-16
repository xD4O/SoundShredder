import io
import plistlib
import tarfile
import zipfile

import pytest

from scripts import build_mac_standalone as package


def runtime_tar(path, members):
    with tarfile.open(path, "w:gz") as tar:
        for name, value, mode, link in members:
            info = tarfile.TarInfo(name)
            info.mode = mode
            if link:
                info.type, info.linkname = tarfile.SYMTYPE, value
                tar.addfile(info)
            else:
                info.size = len(value)
                tar.addfile(info, io.BytesIO(value))


def test_mac_package_contains_native_launcher_permissions_and_shared_interface(tmp_path, monkeypatch):
    runtime = tmp_path / "python.tar.gz"
    runtime_tar(runtime, [("python/bin/python3.11", b"Mach-O fixture", 0o755, False),
                          ("python/bin/python3", "python3.11", 0o777, True)])
    wheel = tmp_path / "bandit_infer-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"fixture")
    monkeypatch.setattr(package, "WORK", tmp_path)
    monkeypatch.setattr(package, "python_archive", lambda _: (runtime, "https://example.invalid/runtime", "digest"))
    native = tmp_path / "native-launcher"
    native.write_bytes(b"Mach-O AppKit fixture")
    result = package.build("arm64", wheel, native)
    with zipfile.ZipFile(tmp_path / result["file"]) as archive:
        plist = plistlib.loads(archive.read(package.APP + "Info.plist"))
        assert plist["CFBundleExecutable"] == "SoundShredder"
        assert plist["LSArchitecturePriority"] == ["arm64"]
        launcher = archive.getinfo(package.APP + "MacOS/SoundShredder")
        assert (launcher.external_attr >> 16) & 0o111 == 0o111
        assert archive.read(launcher) == native.read_bytes()
        assert package.APP + "Resources/desktop/serve.py" in archive.namelist()
        py = archive.getinfo(package.APP + "Resources/python/bin/python3.11")
        assert (py.external_attr >> 16) & 0o111 == 0o111
        link = archive.getinfo(package.APP + "Resources/python/bin/python3")
        assert (link.external_attr >> 16) & 0o170000 == 0o120000
        assert archive.read(package.APP + "Resources/static/index.html") == (package.ROOT / "static/index.html").read_bytes()
        assert not any("/data/" in n or "/.venv/" in n or "__pycache__" in n for n in archive.namelist())
    assert result["signed"] is False and result["mac_hardware_tested"] is False


@pytest.mark.parametrize("name,link", [("../outside", False), ("python/link", True)])
def test_runtime_archive_rejects_escape(tmp_path, name, link):
    source = tmp_path / "unsafe.tar.gz"
    runtime_tar(source, [(name, "../../outside" if link else b"x", 0o755, link)])
    with zipfile.ZipFile(io.BytesIO(), "w") as archive:
        with pytest.raises(ValueError, match="Unsafe"):
            package.add_python(archive, source)


def test_intel_constraints_are_kept_in_standalone_package():
    intel = package.requirements_for("x86_64")
    apple = package.requirements_for("arm64")
    assert "numpy==1.26.4" in intel and "scipy==1.14.1" in intel and "torch==2.2.2" in intel
    assert "torch==2.8.0" in apple and "numpy==1.26.4" not in apple
    assert "bandit-infer @" not in apple + intel


def test_cross_platform_builder_requires_a_native_mac_launcher(tmp_path, monkeypatch):
    monkeypatch.setattr(package.sys, "platform", "win32")
    with pytest.raises(RuntimeError, match="Build the AppKit launcher on macOS"):
        package.native_launcher(tmp_path / "launcher")
