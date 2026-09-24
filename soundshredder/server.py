"""Loopback-only UI and job API. Audio stays on this computer."""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .audio import EXTENSIONS, MAX_BYTES, export_mix, read_json, validate_gains, write_json
from .bubble import MAX_PASSES, export_cleanup, validate_settings
from .listening import manifest as listening_manifest
from .targeted import PREVIEW_SECONDS
from .targeted import validate_settings as validate_targeted
from .updates import RELEASES_URL, REPOSITORY_URL, check_latest

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("SOUNDSHREDDER_DATA", str(ROOT / "data"))).resolve()
JOB_ID = re.compile(r"^[a-f0-9]{32}$")
PROCESSES: dict[str, subprocess.Popen] = {}
LISTENING_PROCESSES: dict[str, subprocess.Popen] = {}
LAB_PROCESSES: dict[str, subprocess.Popen] = {}
GUARD = threading.RLock()
MIX_LOCK = threading.Lock()
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska", ".webm": "video/webm"}


def job_path(job_id: str) -> Path:
    if not JOB_ID.fullmatch(job_id) or not (DATA / job_id / "request.json").is_file():
        raise HTTPException(404, "That session was not found.")
    return DATA / job_id


def active_jobs() -> list[str]:
    return list(dict.fromkeys(job for group in (PROCESSES, LISTENING_PROCESSES, LAB_PROCESSES)
                             for job, process in group.items() if process.poll() is None))


def snapshot(job_id: str) -> dict:
    directory = job_path(job_id)
    progress = read_json(directory / "progress.json")
    process = PROCESSES.get(job_id)
    if progress["status"] == "running" and (process is None or process.poll() is not None):
        progress = {
            "status": "failed",
            "progress": 0,
            "message": "Processing stopped before completion. Start a new separation to retry.",
        }
    settings = read_json(directory / "request.json")
    result = {
        "id": job_id,
        **progress,
        "worker_active": process is not None and process.poll() is None,
        "filename": settings["filename"],
        "video_preview": Path(settings.get("video_source", settings["source"])).suffix.lower() in VIDEO_TYPES,
        "settings": {key: settings[key] for key in ("device", "gains", "cpu_fallback", "mode", "cleanup", "preview",
                                                    "source_basis", "parent_id", "root_id", "created_at") if key in settings},
    }
    for key, filename in (("source", "source.json"), ("report", "separation.json"), ("mix", "mix.json")):
        if (directory / filename).is_file():
            result[key] = read_json(directory / filename)
    return result


@asynccontextmanager
async def lifespan(_app):
    DATA.mkdir(parents=True, exist_ok=True)
    yield
    with GUARD:
        lab_manager.close()
        for processes, filename in ((PROCESSES, "progress.json"), (LISTENING_PROCESSES, "listening.json")):
            for job_id, process in processes.items():
                if process.poll() is not None:
                    continue
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                write_json(DATA / job_id / filename,
                           {"status": "cancelled", "progress": 0, "message": "Stopped when SoundShredder closed."})


app = FastAPI(title="SoundShredder", version=__version__, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.middleware("http")
async def local_only(request: Request, call_next):
    # No public sharing, wildcard CORS, or cross-origin mutations of local files.
    if request.method in {"POST", "DELETE", "PUT", "PATCH"}:
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Open SoundShredder on this computer to make changes."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/system")
def system():
    import torch

    available = torch.cuda.is_available()
    return {
        "name": "SoundShredder",
        "version": __version__,
        "repository_url": REPOSITORY_URL,
        "releases_url": RELEASES_URL,
        "gpu_available": available,
        "gpu_name": torch.cuda.get_device_name(0) if available else None,
        "torch": torch.__version__,
        "max_mb": MAX_BYTES // (1024 * 1024),
        "active_jobs": active_jobs(),
        "features": {"bubble_cleanup": True, "listening_tracks": True,
                     "bubble_multipass": True, "rerun_source": True, "update_check": True,
                     "targeted_cleanup": True, "cleanup_versions": True, "mixing_lab": True},
        "max_bubble_passes": MAX_PASSES,
        "max_preview_seconds": PREVIEW_SECONDS,
    }


@app.post("/api/updates/check")
def check_updates():
    return check_latest()


@app.get("/api/jobs")
def history():
    directories = sorted(
        (p for p in DATA.iterdir() if p.is_dir() and JOB_ID.fullmatch(p.name)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:20]
    jobs = []
    for directory in directories:
        with contextlib.suppress(OSError, ValueError, HTTPException):
            jobs.append(snapshot(directory.name))
    return jobs


@app.post("/api/jobs", status_code=202)
async def create_job(
    file: Annotated[UploadFile, File()],
    device: Annotated[str, Form()] = "auto",
    speech: Annotated[float, Form()] = 1,
    music: Annotated[float, Form()] = 0,
    effects: Annotated[float, Form()] = 1,
    cpu_fallback: Annotated[bool, Form()] = True,
    mode: Annotated[str, Form()] = "stems",
    bubble_type: Annotated[str, Form()] = "water",
    bubble_strength: Annotated[float, Form()] = 0.85,
    range_start: Annotated[float, Form()] = 0,
    range_end: Annotated[float | None, Form()] = None,
    bubble_passes: Annotated[int, Form()] = 1,
    prompt: Annotated[str, Form()] = "",
    preview: Annotated[bool, Form()] = False,
):
    if device not in {"auto", "cpu", "cuda"}:
        raise HTTPException(400, "Choose Auto, CPU, or NVIDIA GPU.")
    try:
        gains = validate_gains({"speech": speech, "music": music, "effects": effects})
        if mode not in {"stems", "bubble", "targeted", "inspect"}:
            raise ValueError("Choose layer separation, Bubble FX or targeted cleanup.")
        cleanup = (validate_targeted(prompt, bubble_strength, range_start, range_end, bubble_passes)
                   if mode == "targeted" else validate_settings(bubble_type, bubble_strength, range_start, range_end, bubble_passes))
        if preview and mode != "targeted":
            raise ValueError("Short previews are available in Target a Sound.")
        if mode in {"bubble", "targeted"}:
            gains = dict(speech=1, music=1, effects=1)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    filename = (file.filename or "audio").replace("\\", "/").split("/")[-1][:200]
    extension = Path(filename).suffix.lower()
    if extension not in EXTENSIONS:
        raise HTTPException(400, "Upload WAV, MP3, FLAC, M4A, AAC, OGG, AIFF, or a video with audio.")
    with GUARD:
        if active_jobs():
            raise HTTPException(409, "A separation is already running. Wait for it to finish or cancel it first.")
    job_id = uuid.uuid4().hex
    directory = DATA / job_id
    directory.mkdir(parents=True)
    source_name = f"source{extension}"
    size = 0
    try:
        with (directory / source_name).open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "The file is too large. The limit is 500 MB.")
                destination.write(chunk)
        if not size:
            raise HTTPException(400, "The uploaded file is empty.")
        write_json(
            directory / "request.json",
            {
                "filename": filename,
                "source": source_name,
                "device": device,
                "gains": gains,
                "cpu_fallback": cpu_fallback,
                "mode": mode,
                "cleanup": cleanup,
                "preview": preview,
                "root_id": job_id,
                "created_at": time.time(),
            },
        )
        with GUARD:
            if active_jobs():
                raise HTTPException(409, "Another separation just started. Please try again when it finishes.")
            write_json(
                directory / "progress.json",
                {"status": "running", "progress": 0.01, "message": "Starting the separation engine…"},
            )
            with (directory / "worker.log").open("wb") as log:
                PROCESSES[job_id] = subprocess.Popen(
                    [sys.executable, "-m", "soundshredder.worker", str(directory)],
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
        return {"id": job_id}
    except BaseException:
        # This path is always a freshly generated UUID under DATA, never a user path.
        if job_id not in PROCESSES:
            shutil.rmtree(directory, ignore_errors=True)
        raise
    finally:
        await file.close()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return snapshot(job_id)


class RerunSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device: str = "auto"
    cpu_fallback: bool = True
    mode: str = "bubble"
    speech: float = 1
    music: float = 1
    effects: float = 1
    bubble_type: str = "water"
    bubble_strength: float = 0.85
    range_start: float = 0
    range_end: float | None = None
    bubble_passes: int = Field(default=1, strict=True, ge=1, le=MAX_PASSES)
    prompt: str = ""
    preview: bool = False
    source_basis: str = "original"


@app.post("/api/jobs/{job_id}/rerun", status_code=202)
async def rerun(job_id: str, settings: RerunSettings):
    directory = job_path(job_id)
    if snapshot(job_id)["status"] == "running":
        raise HTTPException(409, "Finish or cancel this session before running its source again.")
    with GUARD:
        if active_jobs():
            raise HTTPException(409, "The audio engine is still busy. Wait for it to finish or cancel the active job.")
    saved = read_json(directory / "request.json")
    original = (directory / saved.get("original_source", saved["source"])).resolve()
    if original.parent != directory.resolve() or not original.is_file():
        raise HTTPException(404, "The saved source is missing. Upload the original file again.")
    if settings.source_basis not in {"original", "cleaned"}:
        raise HTTPException(400, "Choose the original upload or the current cleaned version.")
    if settings.device not in {"auto", "cpu", "cuda"} or settings.mode not in {"stems", "bubble", "targeted", "inspect"}:
        raise HTTPException(400, "Choose a supported cleanup mode and device.")
    try:
        gains = validate_gains(dict(speech=settings.speech, music=settings.music, effects=settings.effects))
        cleanup = (validate_targeted(settings.prompt, settings.bubble_strength, settings.range_start,
                                     settings.range_end, settings.bubble_passes) if settings.mode == "targeted"
                   else validate_settings(settings.bubble_type, settings.bubble_strength, settings.range_start,
                                          settings.range_end, settings.bubble_passes))
        if settings.preview and settings.mode != "targeted":
            raise ValueError("Short previews are available in Target a Sound.")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if settings.mode in {"targeted", "bubble"}:
        gains = dict(speech=1, music=1, effects=1)
    source = original
    if settings.source_basis == "cleaned":
        mix = read_json(directory / "mix.json") if (directory / "mix.json").is_file() else {}
        if not re.fullmatch(r"cleaned-[a-f0-9]{12}\.wav", mix.get("mix", "")) or mix.get("preview"):
            raise HTTPException(400, "Apply a full cleanup before using it as the input to another step.")
        source = directory / "output" / mix["mix"]
        if not source.is_file():
            raise HTTPException(404, "The selected cleaned audio is missing.")
    new_id = uuid.uuid4().hex
    target = DATA / new_id
    target.mkdir()
    try:
        # Each version owns its source copies, so deleting an earlier session does
        # not break a later one. Disk copies run off the async request loop.
        import asyncio

        original_name = "source" + original.suffix.lower()
        await asyncio.to_thread(shutil.copyfile, original, target / original_name)
        source_name = original_name
        if settings.source_basis == "cleaned":
            source_name = "base.wav"
            await asyncio.to_thread(shutil.copyfile, source, target / source_name)
        write_json(target / "request.json", {
            "filename": saved["filename"], "source": source_name, "original_source": original_name,
            "video_source": original_name, "device": settings.device, "cpu_fallback": settings.cpu_fallback,
            "mode": settings.mode, "gains": gains, "cleanup": cleanup, "preview": settings.preview,
            "parent_id": job_id, "root_id": saved.get("root_id", job_id),
            "source_basis": settings.source_basis, "created_at": time.time(),
        })
        with GUARD:
            if active_jobs():
                raise HTTPException(409, "Another cleanup is running. Finish or cancel it first.")
            write_json(target / "progress.json", {"status": "running", "progress": 0.01, "message": "Preparing a new version…"})
            with (target / "worker.log").open("wb") as log:
                PROCESSES[new_id] = subprocess.Popen([sys.executable, "-m", "soundshredder.worker", str(target)],
                                                     cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"id": new_id}
    except BaseException:
        if new_id not in PROCESSES and target.resolve().parent == DATA.resolve():
            shutil.rmtree(target, ignore_errors=True)
        raise


@app.get("/api/jobs/{job_id}/versions")
def versions(job_id: str):
    directory = job_path(job_id)
    root = read_json(directory / "request.json").get("root_id", job_id)
    result = []
    for folder in DATA.iterdir():
        if not folder.is_dir() or not JOB_ID.fullmatch(folder.name):
            continue
        with contextlib.suppress(OSError, ValueError, KeyError, HTTPException):
            saved = read_json(folder / "request.json")
            if saved.get("root_id", folder.name) != root:
                continue
            state = snapshot(folder.name)
            result.append({"id": folder.name, "status": state["status"], "mode": saved.get("mode", "stems"),
                           "cleanup": saved.get("cleanup"), "preview": saved.get("preview", False),
                           "applied_cleanup": state.get("report", {}).get("applied_cleanup"),
                           "parent_id": saved.get("parent_id"), "source_basis": saved.get("source_basis", "original"),
                           "created_at": saved.get("created_at", folder.stat().st_mtime)})
    return sorted(result, key=lambda value: value["created_at"], reverse=True)


@app.get("/api/jobs/{job_id}/listening")
def get_listening(job_id: str):
    directory = job_path(job_id)
    if snapshot(job_id)["status"] != "complete" or not (directory / "mix.json").is_file():
        raise HTTPException(409, "Finish separation before preparing listening tracks.")
    result = listening_manifest(directory)
    process = LISTENING_PROCESSES.get(job_id)
    if result["status"] == "running" and (process is None or process.poll() is not None):
        result.update(status="failed", message="Track preparation stopped. Click Prepare isolated tracks to retry.")
    return result


@app.post("/api/jobs/{job_id}/listening", status_code=202)
def prepare_listening(job_id: str):
    directory = job_path(job_id)
    with GUARD, MIX_LOCK:
        result = get_listening(job_id)
        if result["status"] == "running" or not result["missing"]:
            return result
        if active_jobs():
            raise HTTPException(409, "Another separation is running. Wait for it to finish first.")
        write_json(directory / "listening.json", {
            "status": "running", "progress": 0, "message": "Preparing isolated listening tracks…",
            "generate_stems": any(name in result["missing"] for name in ("speech", "music", "effects")),
        })
        try:
            with (directory / "listening.log").open("wb") as log:
                LISTENING_PROCESSES[job_id] = subprocess.Popen(
                    [sys.executable, "-m", "soundshredder.listening", str(directory)], cwd=ROOT,
                    stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
        except OSError as exc:
            write_json(directory / "listening.json", {"status": "failed", "message": "Could not start track preparation."})
            raise HTTPException(500, "Could not start track preparation. Try again.") from exc
        return get_listening(job_id)


@app.post("/api/jobs/{job_id}/listening/cancel")
def cancel_listening(job_id: str):
    directory = job_path(job_id)
    with GUARD:
        process = LISTENING_PROCESSES.get(job_id)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            write_json(directory / "listening.json", {"status": "cancelled", "progress": 0,
                                                     "message": "Track preparation cancelled. Your cleaned mix is unchanged."})
    return get_listening(job_id)


@app.post("/api/jobs/{job_id}/cancel")
def cancel(job_id: str):
    directory = job_path(job_id)
    with GUARD:
        process = PROCESSES.get(job_id)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            write_json(
                directory / "progress.json",
                {
                    "status": "cancelled",
                    "progress": 0,
                    "message": "Separation cancelled. Your original file is unchanged.",
                },
            )
    return snapshot(job_id)


class MixLevels(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speech: float = Field(ge=0, le=1, allow_inf_nan=False)
    music: float = Field(ge=0, le=1, allow_inf_nan=False)
    effects: float = Field(ge=0, le=1, allow_inf_nan=False)
    bubble_strength: float = Field(default=0.85, ge=0, le=1, allow_inf_nan=False)
    range_start: float = Field(default=0, ge=0, allow_inf_nan=False)
    range_end: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    bubble_passes: int | None = Field(default=None, strict=True, ge=1, le=MAX_PASSES)


@app.post("/api/jobs/{job_id}/mix")
def remix(job_id: str, levels: MixLevels):
    directory = job_path(job_id)
    if snapshot(job_id)["status"] != "complete" or not (directory / "separation.json").is_file():
        raise HTTPException(409, "Wait until separation is complete to adjust the mix.")
    with GUARD, MIX_LOCK:
        listening_process = LISTENING_PROCESSES.get(job_id)
        if listening_process and listening_process.poll() is None:
            raise HTTPException(409, "Finish or cancel track preparation before updating the mix.")
        try:
            if read_json(directory / "separation.json").get("mode") == "targeted":
                raise ValueError("Save a new targeted cleanup version to apply these settings.")
            if read_json(directory / "separation.json").get("mode") == "bubble":
                return export_cleanup(directory, levels.bubble_strength, levels.range_start, levels.range_end, levels.bubble_passes)
            return export_mix(directory, levels.model_dump(include={"speech", "music", "effects"}))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc


@app.get("/api/jobs/{job_id}/video")
def video_preview(job_id: str):
    directory = job_path(job_id)
    saved = read_json(directory / "request.json")
    source = (directory / saved.get("video_source", saved["source"])).resolve()
    if source.parent != directory.resolve() or source.suffix.lower() not in VIDEO_TYPES or not source.is_file():
        raise HTTPException(404, "This session has no available video preview.")
    return FileResponse(source, media_type=VIDEO_TYPES[source.suffix.lower()], content_disposition_type="inline")


@app.get("/api/jobs/{job_id}/files/{filename}")
def download(job_id: str, filename: str, preview: bool = False):
    directory = job_path(job_id)
    allowed = re.fullmatch(
        r"(?:speech|music|effects|original)\.wav|(?:cleaned|removed)-[a-f0-9]{12}\.wav|soundshredder-[a-f0-9]{12}\.zip|report-[a-f0-9]{12}\.json",
        filename,
    )
    if not allowed or not (directory / "output" / filename).is_file():
        raise HTTPException(404, "That output file is not available.")
    return FileResponse(directory / "output" / filename, filename=filename,
                        content_disposition_type="inline" if preview and filename.endswith(".wav") else "attachment")


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    directory = job_path(job_id)
    with GUARD, MIX_LOCK:
        if job_id in active_jobs():
            raise HTTPException(409, "Cancel the separation before deleting this session.")
        # Resolve and verify the target before any recursive removal.
        if directory.resolve().parent != DATA or not JOB_ID.fullmatch(directory.name):
            raise HTTPException(400, "Invalid session directory.")
        shutil.rmtree(directory)
        PROCESSES.pop(job_id, None)
        LISTENING_PROCESSES.pop(job_id, None)
        LAB_PROCESSES.pop(job_id, None)
    return {"deleted": True}


from .lab_api import register as register_lab  # noqa: E402

lab_manager = register_lab(app, sys.modules[__name__])
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
