"""Local Lab API; subprocesses own expensive work, the server owns state commits."""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import uuid
from typing import Annotated

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from . import mixing
from .audio import EXTENSIONS, MAX_BYTES, read_json, write_json
from .targeted import validate_settings


class Edit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    tracks: dict


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(default=0, ge=0, strict=True)
    device: str = "auto"
    track: str = "effects"
    prompt: str = ""
    strength: float = Field(default=.85, ge=0, le=1, allow_inf_nan=False)
    passes: int = Field(default=1, ge=1, le=4, strict=True)
    start: float = Field(default=0, ge=0, allow_inf_nan=False)
    end: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    preview: bool = False
    video: bool = False


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        # Only the live, owned worker PID; include its FFmpeg children.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                       timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


class Lab:
    def __init__(self, service):
        self.s = service

    def folder(self, job_id):
        return self.s.job_path(job_id) / "lab"

    def state(self, folder):
        return read_json(folder / "state.json") if (folder / "state.json").is_file() else None

    def status(self, job_id):
        folder = self.folder(job_id)
        state = self.state(folder)
        task_info = read_json(folder / "task.json") if (folder / "task.json").is_file() else None
        task_status = None
        if task_info:
            task = folder / "tasks" / task_info["id"]
            task_status = read_json(task / "progress.json")
            process = self.s.LAB_PROCESSES.get(job_id)
            alive = process is not None and process.poll() is None
            if not task_info.get("finalized") and not alive:
                if process is not None and process.returncode == 0 and task_status["status"] == "complete":
                    result = read_json(task / "result.json")
                    if (state or {}).get("last_task") == task_info["id"]:
                        # Recover an interrupted finalization after the atomic state write.
                        if "export" in result:
                            write_json(task / "published.json", {"complete": True})
                    elif (state or {}).get("revision", 0) != task_info["revision"]:
                        task_status = dict(status="failed", message="The mix changed. Run this operation again.", progress=0)
                    elif "state" in result:
                        state = result["state"]
                        state["revision"] = task_info["revision"] + 1
                        state["last_task"] = task_info["id"]
                        write_json(folder / "state.json", state)
                    else:
                        state["export"] = {**result["export"], "id": task_info["id"]}
                        state["last_task"] = task_info["id"]
                        write_json(folder / "state.json", state)
                        write_json(task / "published.json", {"complete": True})
                elif task_status["status"] not in {"failed", "cancelled"}:
                    task_status = dict(status="failed", progress=0,
                                       message="Lab work stopped before it was saved. Your previous mix is intact; retry when ready.")
                task_info["finalized"] = True
                write_json(folder / "task.json", task_info)
                write_json(task / "progress.json", task_status)
            if alive:
                task_status = {**task_status, "status": "running"}
                inner = task / "separation" / "progress.json"
                if inner.is_file():
                    task_status.update(read_json(inner))
                    task_status["status"] = "running"
            task_status.update(id=task_info["id"], operation=task_info["operation"], active=alive)
        return dict(state=state, task=task_status,
                    stems_available=all((folder.parent / "output" / f"{name}.wav").is_file()
                                        for name in ("speech", "music", "effects")))

    def ready(self, job_id, revision):
        state = self.status(job_id)["state"]
        if self.s.active_jobs():
            raise HTTPException(409, "Finish or cancel the current processing job first.")
        if self.s.snapshot(job_id)["status"] != "complete":
            raise HTTPException(409, "Finish reading the source before opening the Lab.")
        if (state or {}).get("revision", 0) != revision:
            raise HTTPException(409, "This mix changed in another tab. Reload the Lab before editing.")
        return state

    def launch(self, job_id, operation, revision, extra=None, task=None):
        state = self.ready(job_id, revision)
        folder = self.folder(job_id)
        task = task or folder / "tasks" / uuid.uuid4().hex
        task.mkdir(parents=True, exist_ok=True)
        write_json(task / "request.json", dict(operation=operation, state=state, **(extra or {})))
        write_json(task / "progress.json", dict(status="running", progress=0, message="Starting Lab work…"))
        with (task / "worker.log").open("wb") as log:
            process = subprocess.Popen([sys.executable, "-m", "soundshredder.mixing", str(task)], cwd=self.s.ROOT,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                       start_new_session=os.name != "nt")
        self.s.LAB_PROCESSES[job_id] = process
        write_json(folder / "task.json", dict(id=task.name, operation=operation, revision=revision))
        return self.status(job_id)

    def cancel(self, job_id):
        process = self.s.LAB_PROCESSES.get(job_id)
        if process and process.poll() is None:
            stop_process(process)
            folder = self.folder(job_id)
            info = read_json(folder / "task.json")
            info["finalized"] = True
            write_json(folder / "task.json", info)
            write_json(folder / "tasks" / info["id"] / "progress.json",
                       dict(status="cancelled", progress=0, message="Cancelled. Your previously saved mix is intact."))
        return self.status(job_id)

    def close(self):
        for job_id in list(self.s.LAB_PROCESSES):
            with contextlib.suppress(OSError, ValueError, HTTPException):
                self.cancel(job_id)


def register(app, service):
    manager = Lab(service)

    @app.get("/lab")
    def page():
        return FileResponse(service.ROOT / "static" / "lab.html")

    @app.get("/api/jobs/{job_id}/lab")
    def status(job_id: str):
        with service.GUARD:
            return manager.status(job_id)

    @app.put("/api/jobs/{job_id}/lab")
    def edit(job_id: str, body: Edit):
        with service.GUARD:
            state = manager.ready(job_id, body.revision)
            if state is None:
                raise HTTPException(409, "Open this session in the Lab first.")
            try:
                state["tracks"] = mixing.validate_edit(state, body.tracks)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            state["revision"] += 1
            write_json(manager.folder(job_id) / "state.json", state)
            return manager.status(job_id)

    @app.post("/api/jobs/{job_id}/lab/actions/{operation}", status_code=202)
    def action(job_id: str, operation: str, body: Action):
        if operation not in {"prepare", "extract", "cleanup", "export"} or body.device not in {"auto", "cpu", "cuda"}:
            raise HTTPException(400, "Choose a supported Lab action and device.")
        with service.GUARD:
            state = manager.ready(job_id, body.revision)
            if state is None and operation not in {"prepare", "extract"}:
                raise HTTPException(409, "Open this session in the Lab first.")
            extra = dict(device=body.device, video=body.video)
            if operation == "prepare" and state:
                return manager.status(job_id)
            if operation == "extract" and state and all(state["tracks"][t]["asset"] for t in ("speech", "music", "effects")):
                raise HTTPException(409, "These stems are already available. Mix them without extracting again.")
            if operation == "cleanup":
                if body.track not in mixing.TRACKS or not state["tracks"][body.track]["asset"]:
                    raise HTTPException(400, "Select an available stem to clean up.")
                try:
                    cleanup = validate_settings(body.prompt, body.strength, body.start, body.end, body.passes)
                    if body.start >= state["duration"] or (body.end is not None and body.end > state["duration"]):
                        raise ValueError("Keep the cleanup interval inside this clip.")
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                extra.update(track=body.track, cleanup=cleanup, preview=body.preview)
            if operation == "export":
                selected = [state["assets"][t["asset"]] for t in state["tracks"].values() if t["asset"]]
                if not selected or any(a["role"] == "preview" for a in selected):
                    raise HTTPException(409, "Select full stem versions before exporting. Previews need Apply cleanup.")
            return manager.launch(job_id, operation, body.revision, extra)

    @app.post("/api/jobs/{job_id}/lab/import", status_code=202)
    def import_track(job_id: str, file: Annotated[UploadFile, File()], revision: Annotated[int, Form()],
                     track: Annotated[str, Form()], fit: Annotated[str, Form()] = "exact"):
        filename = (file.filename or "audio").replace("\\", "/").split("/")[-1][:200]
        extension = service.Path(filename).suffix.lower()
        if track not in mixing.TRACKS or fit not in {"exact", "fit"} or extension not in EXTENSIONS:
            raise HTTPException(400, "Choose a channel, an audio file and a duration rule.")
        with service.GUARD:
            if manager.ready(job_id, revision) is None:
                raise HTTPException(409, "Open this session in the Lab first.")
            task = manager.folder(job_id) / "tasks" / uuid.uuid4().hex
            task.mkdir(parents=True)
            upload = task / ("upload" + extension)
            try:
                size = 0
                with upload.open("xb") as stream:
                    while block := file.file.read(1024 * 1024):
                        size += len(block)
                        if size > MAX_BYTES:
                            raise HTTPException(413, "The file exceeds 500 MB.")
                        stream.write(block)
                if not size:
                    raise HTTPException(400, "The file is empty.")
                return manager.launch(job_id, "import", revision,
                                      dict(track=track, fit=fit, upload=upload.name, filename=filename), task)
            finally:
                file.file.close()
                if not (task / "request.json").exists():
                    upload.unlink(missing_ok=True)

    @app.post("/api/jobs/{job_id}/lab/cancel")
    def cancel(job_id: str):
        with service.GUARD:
            return manager.cancel(job_id)

    @app.get("/api/jobs/{job_id}/lab/assets/{asset_id}")
    def asset(job_id: str, asset_id: str, start: float | None = None, seconds: float = 20):
        folder = manager.folder(job_id)
        state = manager.state(folder)
        if not state or asset_id not in state["assets"]:
            raise HTTPException(404, "That stem version is unavailable.")
        if start is None:
            name = state["assets"][asset_id]
            return FileResponse(mixing.asset_path(folder, asset_id), filename=f"{name['track']}-{name['role']}.wav")
        try:
            return Response(mixing.segment(folder, state, asset_id, start, seconds), media_type="audio/wav")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/jobs/{job_id}/lab/exports/{export_id}/{filename}")
    def export(job_id: str, export_id: str, filename: str):
        folder = manager.folder(job_id)
        if not service.JOB_ID.fullmatch(export_id):
            raise HTTPException(404, "That export is unavailable.")
        task = folder / "tasks" / export_id
        result = read_json(task / "result.json") if (task / "result.json").is_file() else {}
        if not (task / "published.json").is_file() or filename not in result.get("export", {}).get("files", []):
            raise HTTPException(404, "That export file is unavailable.")
        return FileResponse(task / "export" / filename, filename=filename)

    return manager
