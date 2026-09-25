"""Immutable Lab assets and time-scoped mixing. No model runs for volume edits."""
from __future__ import annotations

import contextlib
import copy
import io
import math
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

from .audio import decode, read_json, resample, write_json

TRACKS = {"speech": "Dialogue", "music": "Music", "effects": "Effects", "ambience": "Ambience"}
FADE = .005
PEAK_HZ = 10
CHUNK_SECONDS = 20
MAX_LAYER_DEPTH = 8
MAX_ACTIVE_TRACKS = 16
MAX_TRACKS = 64


def track_info(state, name):
    return state.get("track_info", {}).get(name, dict(label=TRACKS.get(name, name), depth=1))


def active_layer(state, name):
    return next((layer for layer in state.get("layers", {}).values()
                 if layer["parent_track"] == name and layer["active"]), None)


def active_tracks(state):
    selected = {}

    def visit(name):
        track = state["tracks"][name]
        if not track["asset"]:
            return
        layer = active_layer(state, name)
        if layer:
            for child in layer["children"]:
                visit(child)
        else:
            selected[name] = track

    for name in TRACKS:
        visit(name)
    return selected


def reachable_tracks(state):
    names = set()

    def visit(name):
        names.add(name)
        layer = active_layer(state, name)
        if layer:
            for child in layer["children"]:
                visit(child)

    for name in TRACKS:
        visit(name)
    return names


def split_source(state, name):
    if name not in active_tracks(state):
        raise ValueError("Choose a playing stem from an active layer to split.")
    asset = state["tracks"][name]["asset"]
    if state["assets"][asset]["role"] == "preview":
        raise ValueError("Apply cleanup or choose a full stem version before splitting.")
    if track_info(state, name)["depth"] >= MAX_LAYER_DEPTH:
        raise ValueError(f"This session supports up to Layer {MAX_LAYER_DEPTH}.")
    if len(active_tracks(state)) + 3 > MAX_ACTIVE_TRACKS or len(state["tracks"]) + 4 > MAX_TRACKS:
        raise ValueError("This session has reached its split-track limit. Use a parent layer or start a new session.")
    return asset


def use_layer(state, layer_id, enabled):
    layer = state.get("layers", {}).get(layer_id)
    if not layer:
        raise ValueError("That layer is unavailable.")
    if layer["parent_track"] not in reachable_tracks(state):
        raise ValueError("Use this branch's parent layer in the mix first.")
    parent = state["tracks"][layer["parent_track"]]
    if enabled and parent != layer["source_track"]:
        raise ValueError("The parent stem or its time edits changed. Split it again to use those changes.")
    result = copy.deepcopy(state)
    if enabled:
        for other in result["layers"].values():
            if other["parent_track"] == layer["parent_track"]:
                other["active"] = False
    result["layers"][layer_id]["active"] = enabled
    if len(active_tracks(result)) > MAX_ACTIVE_TRACKS:
        raise ValueError(f"Keep the mix within {MAX_ACTIVE_TRACKS} active tracks.")
    return result


def validate_regions(regions, duration):
    if not isinstance(regions, list) or len(regions) > 2000:
        raise ValueError("Keep each track below 2,000 time edits.")
    result = []
    previous = 0
    for region in regions:
        if not isinstance(region, dict) or set(region) != {"start", "end", "db"}:
            raise ValueError("An edit needs a start, end and gain.")
        start, end, db = region["start"], region["end"], region["db"]
        numbers = [start, end] + ([] if db is None else [db])
        if any(isinstance(n, bool) or not isinstance(n, (float, int)) or not math.isfinite(n) for n in numbers):
            raise ValueError("Time edits must contain finite numbers.")
        if not 0 <= start < end <= duration + 1e-9 or start < previous:
            raise ValueError("Time edits must be ordered, within the clip and non-overlapping.")
        if db is not None and not -60 <= db <= 6:
            raise ValueError("Choose a gain between -60 and +6 dB, or mute.")
        result.append(dict(start=start, end=min(end, duration), db=db))
        previous = end
    return result


def envelope(regions, times):
    """Linear amplitude fades stay inside each edited interval; outside is unity."""
    gains = np.ones(len(times), dtype=np.float64)
    for region in regions:
        start, end = region["start"], region["end"]
        mask = (times >= start) & (times < end)
        fade = min(FADE, (end - start) / 2)
        weight = np.clip(np.minimum((times[mask] - start) / fade, (end - times[mask]) / fade), 0, 1)
        level = 0 if region["db"] is None else 10 ** (region["db"] / 20)
        gains[mask] = 1 + (level - 1) * weight
    return gains


def protection(state):
    bound = 0
    # Keep the original fixed headroom convention for sessions without layers.
    for name in (active_tracks(state) if state.get("layers") else state["tracks"]):
        assets = [a for a in state["assets"].values() if a["track"] == name and a["role"] != "removed"]
        if assets:
            # Reserve the full +6 dB fader range, independent of time edits. An
            # isolated boost must not silently turn down the rest of the clip.
            peak = max(a["peak"] for a in assets)
            bound += peak * 10 ** (6 / 20)
    return min(1, .98 / max(bound, 1e-12))


def validate_edit(state, tracks):
    if not isinstance(tracks, dict) or set(tracks) != set(state["tracks"]):
        raise ValueError("Save all Lab channels together.")
    result = {}
    for name, track in tracks.items():
        if not isinstance(track, dict) or set(track) != {"asset", "regions"}:
            raise ValueError("Invalid track settings.")
        if active_layer(state, name) and track != state["tracks"][name]:
            raise ValueError("Use the parent layer before changing a stem that has been split.")
        asset = track["asset"]
        if asset is not None:
            if not isinstance(asset, str) or asset not in state["assets"]:
                raise ValueError("That stem version is unavailable.")
            metadata = state["assets"][asset]
            if metadata["track"] != name or metadata["role"] == "removed":
                raise ValueError("Removed sounds are for review, outside the mix.")
        result[name] = {"asset": asset, "regions": validate_regions(track["regions"], state["duration"])}
    return result


def asset_path(lab, asset_id):
    # IDs are looked up in the state catalog by the API before this internal helper.
    if len(asset_id) != 32 or any(c not in "0123456789abcdef" for c in asset_id):
        raise ValueError("Invalid asset ID.")
    return lab / "assets" / f"{asset_id}.wav"


def add_asset(lab, state, path, track, label, role, **extra):
    asset_id = uuid.uuid4().hex
    destination = asset_path(lab, asset_id)
    destination.parent.mkdir(exist_ok=True)
    shutil.copyfile(path, destination)
    peaks = []
    with sf.SoundFile(destination) as stream:
        if (stream.frames, stream.samplerate, stream.channels) != (state["frames"], state["rate"], state["channels"]):
            raise ValueError("Stem timing does not match this session.")
        while len(block := stream.read(max(1, stream.samplerate // PEAK_HZ), dtype="float32", always_2d=True)):
            if not np.isfinite(block).all():
                raise ValueError("The stem contains invalid audio samples.")
            peaks.append(float(np.max(np.abs(block))))
    state["assets"][asset_id] = dict(id=asset_id, track=track, label=label, role=role,
                                      peaks=peaks, peak_hz=PEAK_HZ, peak=max(peaks, default=0), **extra)
    return asset_id


def video_source(directory):
    request = read_json(directory / "request.json")
    path = (directory / request.get("video_source", request["source"])).resolve()
    if path.parent == directory.resolve() and path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}:
        return path
    return None


def initial_state(directory):
    source = read_json(directory / "source.json")
    source_mode = read_json(directory / "request.json").get("mode", "stems")
    fps = None
    video = video_source(directory)
    if video:
        import imageio_ffmpeg

        reader = imageio_ffmpeg.read_frames(str(video))
        try:
            value = next(reader).get("fps", 0)
            if math.isfinite(value) and 1 <= value <= 240:
                fps = value
        except (OSError, RuntimeError):
            pass
        finally:
            reader.close()
    return dict(schema=1, revision=0, filename=source["filename"], frames=source["frames"],
                rate=source["sample_rate"], channels=source["channels"], duration=source["duration"],
                fps=fps, video=bool(video), source_mode=source_mode,
                tracks={name: dict(asset=None, regions=[]) for name in TRACKS}, assets={})


def segment(lab, state, asset_id, start, seconds):
    """Bounded browser audio; contextual resampling avoids discontinuities at chunk edges."""
    if not math.isfinite(start) or not 0 <= start < state["duration"]:
        raise ValueError("Seek inside the clip.")
    if not math.isfinite(seconds) or not 0 < seconds <= CHUNK_SECONDS:
        raise ValueError("Playback segments are limited to 20 seconds.")
    browser_rate = 48000
    first = round(start * browser_rate)
    stop = min(round(state["duration"] * browser_rate), first + round(seconds * browser_rate))
    # Start on a whole second so polyphase resampling has a stable phase in every chunk.
    context_start = max(0, int(start) - 1)
    context_end = min(state["frames"], math.ceil((stop / browser_rate + .1) * state["rate"]))
    with sf.SoundFile(asset_path(lab, asset_id)) as stream:
        stream.seek(context_start * state["rate"])
        audio = stream.read(context_end - stream.tell(), dtype="float32", always_2d=True)
    audio = resample(audio, state["rate"], browser_rate)
    offset = first - context_start * browser_rate
    audio = audio[offset:offset + stop - first]
    if len(audio) < stop - first:
        audio = np.pad(audio, ((0, stop - first - len(audio)), (0, 0)))
    buffer = io.BytesIO()
    sf.write(buffer, audio, browser_rate, format="WAV", subtype="FLOAT")
    return buffer.getvalue()


def render(lab, state, target, progress, video=None):
    selected = active_tracks(state)
    if not selected:
        raise ValueError("Add at least one stem before exporting.")
    if any(state["assets"][t["asset"]]["role"] == "preview" for t in selected.values()):
        raise ValueError("Apply cleanup or select a full stem version before exporting a preview.")
    target.mkdir(exist_ok=True)
    trim = protection(state)
    rate, frames, channels = state["rate"], state["frames"], state["channels"]
    filenames = {name: f"{name}.wav" if name in TRACKS else
                 f"layer-{track_info(state, name)['depth']}-{track_info(state, name)['kind']}-{name[:8]}.wav"
                 for name in selected}
    file_labels = {filename: f"Layer {track_info(state, name)['depth']} · {track_info(state, name)['label']} WAV"
                   for name, filename in filenames.items()}
    files = list(filenames.values()) + ["mix.wav", "mix-report.json"]
    filenames["mix"] = "mix.wav"
    with contextlib.ExitStack() as stack:
        readers = {name: stack.enter_context(sf.SoundFile(asset_path(lab, t["asset"]))) for name, t in selected.items()}
        writers = {name: stack.enter_context(sf.SoundFile(target / filenames[name], "w", rate, channels,
                                                           subtype="PCM_24")) for name in [*selected, "mix"]}
        for offset in range(0, frames, rate):
            size = min(rate, frames - offset)
            times = (np.arange(size, dtype=np.float64) + offset) / rate
            mix = np.zeros((size, channels), dtype=np.float64)
            for name, track in selected.items():
                audio = readers[name].read(size, dtype="float64", always_2d=True)
                audio *= envelope(track["regions"], times)[:, None] * trim
                writers[name].write(audio)
                mix += audio
            if not np.isfinite(mix).all() or np.max(np.abs(mix)) > 1:
                raise RuntimeError("Mix exceeded its verified output headroom.")
            writers["mix"].write(mix)
            progress(.05 + .8 * (offset + size) / frames, "Rendering your time edits and stems…")
    report = {"revision": state["revision"], "frames": frames, "sample_rate": rate, "channels": channels,
              "duration": state["duration"], "output_gain": trim, "edge_fade_seconds": FADE,
              "tracks": selected, "assets": {t["asset"]: {k: v for k, v in state["assets"][t["asset"]].items()
                                                          if k != "peaks"} for t in selected.values()},
              "layers": state.get("layers", {}), "track_info": state.get("track_info", {}),
              "track_files": filenames, "solo_is_audition_only": True, "format": "24-bit PCM WAV", "video": None}
    if video:
        import imageio_ffmpeg

        progress(.89, "Attaching the mix to your footage without re-encoding the picture…")
        try:
            result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-y", "-i", str(video),
                                     "-i", str(target / "mix.wav"), "-map", "0:v:0", "-map", "1:a:0",
                                     "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart",
                                     str(target / "mixed-video.mp4")], capture_output=True, timeout=180,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            video_ok = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            video_ok = False
        if video_ok:
            files.append("mixed-video.mp4")
            report["video"] = "Picture stream copied; new soundtrack encoded as AAC. WAV remains lossless."
        else:
            (target / "mixed-video.mp4").unlink(missing_ok=True)
            report["video_error"] = "The picture could not be copied into MP4 (format or encoder issue). Download the WAV mix for your editor."
    write_json(target / "mix-report.json", report)
    progress(.97, "Packing the mix, individual tracks and edit report…")
    with zipfile.ZipFile(target / "mixing-lab.zip", "w", compression=zipfile.ZIP_STORED) as bundle:
        for filename in files:
            bundle.write(target / filename, filename)
    return dict(files=[*files, "mixing-lab.zip"], revision=state["revision"],
                file_labels=file_labels, output_gain=trim, video_error=report.get("video_error"))


def tidy_scratch(task):
    """Discard only worker-owned temporary copies after immutable assets are written."""
    task = task.resolve()
    if task.parent.name != "tasks" or task.parent.parent.name != "lab" or len(task.name) != 32:
        raise ValueError("Invalid Lab scratch directory.")
    for name in ("work", "output", "separation"):
        path = (task / name).resolve()
        if path.parent == task and path.is_dir():
            shutil.rmtree(path)
    for path in task.iterdir():
        if path.is_file() and (path.stem in {"source", "upload", "fitted", "decoded"}):
            path.unlink()


def work(task):
    """Worker writes a result; only the server commits it after a successful process exit."""
    request = read_json(task / "request.json")
    lab = task.parent.parent
    directory = lab.parent
    state = request.get("state")
    operation = request["operation"]

    def progress(amount, message, **extra):
        write_json(task / "progress.json", dict(status="running", progress=amount, message=message, **extra))

    progress(.01, "Preparing the Mixing Lab…")
    if operation in {"prepare", "extract"}:
        state = state or initial_state(directory)
        source_dir = directory / "output"
        if operation == "extract":
            from .worker import process

            inner = task / "separation"
            inner.mkdir()
            shutil.copyfile(directory / "output" / "original.wav", inner / "source.wav")
            write_json(inner / "request.json", dict(source="source.wav", filename=state["filename"], mode="stems",
                                                     device=request["device"], cpu_fallback=True,
                                                     gains=dict(speech=1, music=1, effects=1)))
            process(inner)
            source_dir = inner / "output"
        for track in ("speech", "music", "effects"):
            path = source_dir / f"{track}.wav"
            if path.is_file() and not state["tracks"][track]["asset"]:
                asset = add_asset(lab, state, path, track, "Separated stem", "original")
                state["tracks"][track]["asset"] = asset
    elif operation == "split":
        from .worker import process

        name = request["track"]
        base = split_source(state, name)
        parent = state["tracks"][name]
        depth = track_info(state, name)["depth"] + 1
        inner = task / "separation"
        inner.mkdir()
        shutil.copyfile(asset_path(lab, base), inner / "source.wav")
        write_json(inner / "request.json", dict(source="source.wav", filename=f"Layer {depth} stem split",
                                                 mode="stems", device=request["device"], cpu_fallback=True,
                                                 gains=dict(speech=1, music=1, effects=1)))
        process(inner)
        source_dir = inner / "output"
        progress(.91, f"Preserving remaining audio and saving Layer {depth}…")
        # Keep the full parent signal available: model estimates may not sum to
        # their input. A separate residual prevents silently dropping that audio.
        with contextlib.ExitStack() as stack:
            source = stack.enter_context(sf.SoundFile(asset_path(lab, base)))
            readers = [stack.enter_context(sf.SoundFile(source_dir / f"{kind}.wav"))
                       for kind in ("speech", "music", "effects")]
            for reader in readers:
                if (reader.frames, reader.samplerate, reader.channels) != (state["frames"], state["rate"], state["channels"]):
                    raise ValueError("The deeper split did not preserve the stem's timing.")
            residual = stack.enter_context(sf.SoundFile(source_dir / "remainder.wav", "w", state["rate"],
                                                        state["channels"], subtype="FLOAT"))
            while len(block := source.read(state["rate"], dtype="float64", always_2d=True)):
                for reader in readers:
                    block -= reader.read(len(block), dtype="float64", always_2d=True)
                residual.write(block)
        layer_id = uuid.uuid4().hex
        children = []
        for kind, label in (("speech", "Dialogue"), ("music", "Music"), ("effects", "Effects"), ("remainder", "Remainder")):
            child = uuid.uuid4().hex
            asset = add_asset(lab, state, source_dir / f"{kind}.wav", child, f"Layer {depth} · {label}", "split",
                              parent=base, layer=layer_id, depth=depth, kind=kind)
            state["tracks"][child] = dict(asset=asset, regions=copy.deepcopy(parent["regions"]))
            state.setdefault("track_info", {})[child] = dict(label=label, kind=kind, depth=depth,
                                                             parent_track=name, layer=layer_id)
            children.append(child)
        state.setdefault("layers", {})[layer_id] = dict(id=layer_id, depth=depth, parent_track=name,
                                                        source_track=copy.deepcopy(parent), children=children,
                                                        active=True, method="Bandit v2")
        # Earlier alternatives stay available without being mixed twice.
        for key, layer in state["layers"].items():
            if key != layer_id and layer["parent_track"] == name:
                layer["active"] = False
        state["last_layer"] = layer_id
    elif operation == "import":
        audio, rate = decode(task / request["upload"], task)
        original_seconds = len(audio) / rate
        if request["fit"] == "exact" and abs(original_seconds - state["duration"]) > 1 / state["rate"]:
            raise ValueError("This track has a different duration. Choose Pad / trim to footage to fit it explicitly.")
        if audio.shape[1] != state["channels"]:
            audio = np.repeat(audio, 2, axis=1) if state["channels"] == 2 else audio.mean(axis=1, keepdims=True)
        audio = resample(audio, rate, state["rate"], state["frames"])
        path = task / "fitted.wav"
        sf.write(path, audio, state["rate"], subtype="FLOAT")
        asset = add_asset(lab, state, path, request["track"], request["filename"], "imported",
                          fit=request["fit"], imported_duration=original_seconds)
        state["tracks"][request["track"]]["asset"] = asset
    elif operation == "cleanup":
        from .targeted import process_targeted

        track = request["track"]
        base = state["tracks"][track]["asset"]
        if state["assets"][base]["role"] == "preview":
            base = state["assets"][base]["parent"]
        shutil.copyfile(asset_path(lab, base), task / "source.wav")
        (task / "output").mkdir()
        (task / "work").mkdir()
        audio, rate = sf.read(task / "source.wav", dtype="float32", always_2d=True)
        from .audio import sha256

        source_info = dict(filename=state["assets"][base]["label"], frames=state["frames"], sample_rate=rate,
                           channels=state["channels"], duration=state["duration"])
        job = dict(source="source.wav", cleanup=request["cleanup"], preview=request["preview"],
                   device=request["device"], cpu_fallback=True, source_basis="selected Lab stem", parent_id=base)
        process_targeted(task, audio, rate, source_info, job, time.monotonic(), progress, sha256(task / "source.wav"))
        mix = read_json(task / "mix.json")
        common = dict(parent=base, cleanup=mix["cleanup"], applied_cleanup=mix["applied_cleanup"])
        removed = add_asset(lab, state, task / "output" / mix["removed"], track, "Removed sounds", "removed", **common)
        role = "preview" if request["preview"] else "cleaned"
        asset = add_asset(lab, state, task / "output" / mix["mix"], track,
                          f"{role.title()}: {request['cleanup']['prompt']}", role, removed=removed, **common)
        state["tracks"][track]["asset"] = asset
    elif operation == "export":
        result = render(lab, state, task / "export", progress,
                        video_source(directory) if request["video"] else None)
        write_json(task / "result.json", {"export": result})
        write_json(task / "progress.json", dict(status="complete", progress=1, message="Your mix is ready to download."))
        return
    else:
        raise ValueError("Unknown Lab operation.")
    write_json(task / "result.json", {"state": state})
    # A scanner can briefly hold a temporary WAV; cleanup failure is not an audio failure.
    with contextlib.suppress(OSError):
        tidy_scratch(task)
    write_json(task / "progress.json", dict(status="complete", progress=1, message="Your Lab is ready."))


if __name__ == "__main__":
    folder = Path(sys.argv[1]).resolve()
    try:
        work(folder)
    except Exception as error:
        import traceback

        traceback.print_exc()
        write_json(folder / "progress.json", dict(status="failed", progress=0, message=str(error)))
        sys.exit(1)
