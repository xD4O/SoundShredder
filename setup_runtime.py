"""Install an isolated CPU or NVIDIA CUDA runtime. No global packages are changed."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BINARY_PACKAGES = ("torch", "numpy", "scipy", "soundfile", "imageio-ffmpeg", "pydantic-core", "cffi")


@dataclass(frozen=True)
class RuntimePlan:
    label: str
    torch_version: str
    index: str
    requirements: str = "requirements.txt"


def runtime_plan(system, machine, python_version, device, *, nvidia=False, translated=False, mac_version=""):
    """Choose wheels before creating an environment or downloading packages."""
    if device not in {"auto", "cpu", "cuda"}:
        raise ValueError("Choose auto, cpu, or cuda.")
    if not (3, 10) <= python_version <= (3, 13):
        recommended = "3.11" if system == "darwin" else "3.12"
        raise ValueError(f"Install Python {recommended}, then run setup again. Supported versions are in README.md.")
    if system == "darwin":
        if device == "cuda":
            raise ValueError("CUDA requires an NVIDIA GPU on Windows/Linux. Use --device cpu on macOS.")
        if translated:
            raise ValueError(
                "Python is running through Rosetta. Install Python 3.11's macOS universal2 installer, "
                "open Terminal without 'Open using Rosetta', and use a fresh extracted SoundShredder folder."
            )
        if mac_version and int(mac_version.split(".")[0]) < 12:
            raise ValueError("This Mac package requires macOS 12 Monterey or newer.")
        if machine == "arm64":
            return RuntimePlan("Apple Silicon CPU", "2.8.0", "https://pypi.org/simple")
        if machine == "x86_64":
            if python_version > (3, 11):
                raise ValueError("Intel Macs require Python 3.10–3.11 for Bandit v2. Install Python 3.11 and retry.")
            return RuntimePlan("Intel Mac CPU", "2.2.2", "https://pypi.org/simple", "requirements-mac-intel.txt")
        raise ValueError(f"Unsupported Mac processor: {machine}. Use native Apple Silicon or Intel Python.")
    if device == "auto":
        device = "cuda" if nvidia else "cpu"
    flavor = "cu128" if device == "cuda" else "cpu"
    return RuntimePlan(
        "NVIDIA GPU (CUDA 12.8)" if device == "cuda" else "CPU",
        "2.8.0+" + flavor,
        "https://download.pytorch.org/whl/" + flavor,
    )


def is_translated():
    if sys.platform != "darwin":
        return False
    result = subprocess.run(
        ["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"], capture_output=True, text=True, check=False
    )
    return result.returncode == 0 and result.stdout.strip() == "1"


def check_runtime(executable):
    subprocess.run(
        [
            str(executable),
            "-c",
            "import torch, numpy as np, bandit_infer, fastapi, uvicorn, soundfile, scipy, imageio_ffmpeg, multipart; "
            "torch.from_numpy(np.zeros(1, dtype=np.float32)).numpy(); "
            "print('Ready. PyTorch:', torch.__version__, '| NVIDIA GPU available:', torch.cuda.is_available())",
        ],
        check=True,
        cwd=ROOT,
    )


def main():
    parser = argparse.ArgumentParser(description="Install SoundShredder's local Python runtime")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--check", action="store_true", help="Check this Python runtime without installing anything")
    args = parser.parse_args()
    try:
        plan = runtime_plan(
            sys.platform, platform.machine(), sys.version_info[:2], args.device,
            nvidia=bool(shutil.which("nvidia-smi")), translated=is_translated(), mac_version=platform.mac_ver()[0],
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.check:
        check_runtime(sys.executable)
        return
    environment = ROOT / ".venv"
    executable = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not executable.is_file():
        print("Creating your isolated Python environment…", flush=True)
        venv.create(environment, with_pip=True)
    uv = shutil.which("uv")
    command = [uv, "pip", "install", "--python", str(executable)] if uv else [str(executable), "-m", "pip", "install"]
    print(f"Installing {plan.label} support in this folder. First setup can take several minutes.", flush=True)
    if "cu128" in plan.torch_version:
        print("The GPU runtime download is about 3.2 GB.", flush=True)
    subprocess.run([*command, f"torch=={plan.torch_version}", "--index-url", plan.index], check=True, cwd=ROOT)
    subprocess.run(
        [*command, "-r", str(ROOT / plan.requirements), f"torch=={plan.torch_version}",
         *(argument for package in BINARY_PACKAGES for argument in ("--only-binary", package))],
        check=True, cwd=ROOT,
    )
    check_runtime(executable)
    if sys.platform == "darwin":
        next_step = "Open Start SoundShredder.command."
    elif sys.platform == "win32":
        next_step = "Open Start SoundShredder.bat."
    else:
        next_step = "Run .venv/bin/python app.py."
    print(f"\nSetup complete. {next_step}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"Setup stopped (exit {exc.returncode}). Check the error above and your internet connection, then retry. "
            "For CPU installation run: python3 setup_runtime.py --device cpu (on Windows use Setup CPU.bat)."
        ) from exc
