import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts.package_release import FILES, GUIDE_FILES, WINDOWS_FILES, build_release
from setup_runtime import runtime_plan

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("device", ["auto", "cpu"])
def test_apple_silicon_uses_native_torch_without_cuda(device):
    plan = runtime_plan("darwin", "arm64", (3, 12), device, nvidia=True, mac_version="12.7.6")
    assert plan.torch_version == "2.8.0"
    assert plan.index == "https://pypi.org/simple"
    assert plan.requirements == "requirements.txt"


def test_intel_mac_keeps_numpy_compatible_with_its_torch_wheel():
    plan = runtime_plan("darwin", "x86_64", (3, 11), "auto")
    assert plan.torch_version == "2.2.2"
    assert plan.index == "https://pypi.org/simple"
    dependencies = (ROOT / plan.requirements).read_text()
    assert "torch==2.2.2" in dependencies and "numpy==1.26.4" in dependencies
    assert "-r requirements.txt" in dependencies


@pytest.mark.parametrize(
    "machine,version,device,extra,message",
    [
        ("arm64", (3, 12), "cuda", {}, "NVIDIA"),
        ("x86_64", (3, 12), "cpu", {}, "Intel Macs require Python"),
        ("x86_64", (3, 12), "cpu", {"translated": True}, "Rosetta"),
        ("arm64", (3, 12), "cpu", {"mac_version": "11.7.10"}, "macOS 12"),
        ("arm64", (3, 14), "cpu", {}, "Install Python"),
    ],
)
def test_unsupported_mac_configuration_explains_how_to_fix_it(machine, version, device, extra, message):
    with pytest.raises(ValueError, match=message):
        runtime_plan("darwin", machine, version, device, **extra)


@pytest.mark.parametrize("system", ["win32", "linux"])
@pytest.mark.parametrize("gpu", [True, False])
def test_windows_linux_auto_keep_existing_device_selection(system, gpu):
    plan = runtime_plan(system, "x86_64", (3, 12), "auto", nvidia=gpu)
    flavor = "cu128" if gpu else "cpu"
    assert plan.torch_version == f"2.8.0+{flavor}"
    assert plan.index.endswith("/" + flavor)


@pytest.mark.parametrize("mac_only", [True, False])
def test_release_has_executable_mac_launcher_and_no_local_audio(tmp_path, mac_only):
    source = tmp_path / "source"
    source.mkdir()
    for filename in FILES + WINDOWS_FILES:
        (source / filename).parent.mkdir(parents=True, exist_ok=True)
        (source / filename).write_bytes(b"#!/bin/bash\r\n" if filename.endswith(".command") else b"example\n")
    for filename in ["soundshredder/engine.py", "data/private.wav", ".venv/private", "tests/__pycache__/cache.pyc"]:
        target = source / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"example")
    destination = tmp_path / "release.zip"
    build_release(source, destination, mac_only=mac_only)
    with zipfile.ZipFile(destination) as archive:
        launcher = archive.getinfo("SoundShredder/Start SoundShredder.command")
        assert launcher.create_system == 3
        assert (launcher.external_attr >> 16) & 0o777 == 0o755
        assert b"\r" not in archive.read(launcher)
        assert not any("private" in name or "__pycache__" in name for name in archive.namelist())
        assert ("SoundShredder/Start SoundShredder.bat" in archive.namelist()) is (not mac_only)
        for guide in GUIDE_FILES:
            assert archive.read("SoundShredder/" + guide) == (source / guide).read_bytes()


@pytest.mark.parametrize("existing,healthy", [(False, True), (True, True), (True, False)])
def test_mac_launcher_bootstraps_and_reuses_an_isolated_environment(tmp_path, existing, healthy):
    """Exercise Bash with fake Python/macOS; never install packages or launch a server."""
    bash = Path("C:/Program Files/Git/bin/bash.exe") if os.name == "nt" else Path(shutil.which("bash") or "")
    if not bash.is_file():
        pytest.skip("Bash is needed for launcher integration checks")
    tmp_path = tmp_path / "Mac folder with spaces"
    tmp_path.mkdir()
    shutil.copyfile(ROOT / "Start SoundShredder.command", tmp_path / "Start SoundShredder.command")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    (fakebin / "uname").write_text("#!/bin/bash\nprintf 'Darwin\\n'\n", newline="\n")
    stub = fakebin / "python3.12"
    stub.write_text(
        "#!/bin/bash\n"
        "if [ \"$1\" = '-c' ]; then exit 0; fi\n"
        "if [ \"${4:-}\" = '--check' ]; then exit " + ("0" if healthy else "1") + "; fi\n"
        "if [ \"$1\" = 'setup_runtime.py' ]; then\n"
        "  printf 'setup\\n' >> actions.log\n"
        "  mkdir -p .venv/bin\n"
        "  if [ \"$0\" != \"$PWD/.venv/bin/python\" ]; then cp \"$0\" .venv/bin/python; fi\n"
        "  chmod +x .venv/bin/python\n"
        "else printf 'launch\\n' >> actions.log; fi\n",
        newline="\n",
    )
    for executable in [stub, fakebin / "uname"]:
        executable.chmod(0o755)
    if existing:
        (tmp_path / ".venv/bin").mkdir(parents=True)
        shutil.copyfile(stub, tmp_path / ".venv/bin/python")
        (tmp_path / ".venv/bin/python").chmod(0o755)
    # Restrict PATH to avoid selecting a real Python. A Mac may also have Python
    # in the launcher's fixed paths, so this fixture runs only on non-macOS hosts.
    import sys

    if sys.platform == "darwin":
        pytest.skip("This mocked OS fixture is for non-Mac hosts")
    result = subprocess.run(
        [str(bash), "-c", 'export PATH="$PWD/fakebin:/usr/bin:/bin"; bash "Start SoundShredder.command"'],
        cwd=tmp_path, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "actions.log").read_text().splitlines() == (
        ["launch"] if existing and healthy else ["setup", "launch"]
    )
