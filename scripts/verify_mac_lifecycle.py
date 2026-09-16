"""Run the built app through Launch Services on a native macOS CI runner."""
import argparse
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


def wait_for(check, timeout=60):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError, KeyError) as exc:
            last = exc
        time.sleep(.5)
    raise AssertionError(f"Timed out: {check} ({last})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    folder = Path.cwd() / "artifacts/mac-lifecycle"
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ditto", "-x", "-k", str(args.archive.resolve()), str(folder)], check=True)
    app = folder / "SoundShredder.app"
    home = folder / "Test profile with spaces"
    metadata = home / "desktop.json"
    log = home / "native-launcher.log"
    evidence = {"machine": os.uname().machine, "cycles": []}

    def instance():
        data = json.loads(metadata.read_text())
        parts = urllib.parse.urlsplit(data["url"])
        return data, f"http://{parts.netloc}", parts.fragment

    def api(path, payload=None):
        data, base, token = instance()
        request = urllib.request.Request(base + path, headers={"X-Setup-Token": token},
                                         data=json.dumps(payload).encode() if payload is not None else None)
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def ready():
        state = api("/api/state")
        if state["status"] == "error":
            raise RuntimeError(state["message"])
        return state if state["status"] == "ready" else None

    for cycle in range(3):
        subprocess.run(["open", "-a", str(app), "--args", "--no-browser", "--home", str(home)], check=True)
        wait_for(lambda: metadata.exists())
        state = wait_for(lambda: api("/api/state"))
        first = instance()[0]["pid"]
        if cycle == 0:
            api("/api/start", {"device": "cpu"})
        state = wait_for(ready, timeout=900)
        with urllib.request.urlopen(state["url"] + "/api/system", timeout=10) as response:
            system = json.load(response)
        assert system["name"] == "SoundShredder" and system["version"] == "1.1.1"
        previous = log.read_text().count("reopen-workspace")
        subprocess.run(["open", "-a", str(app)], check=True)
        wait_for(lambda previous=previous: log.read_text().count("reopen-workspace") > previous)
        assert api("/api/state")["status"] == "ready" and instance()[0]["pid"] == first
        # The normal setup Close control must terminate the native host as well.
        api("/api/stop", {})
        wait_for(lambda: not metadata.exists())
        wait_for(lambda cycle=cycle: log.read_text().count("native-app-closed") >= cycle + 1)
        evidence["cycles"].append({"cycle": cycle + 1, "version": system["version"], "manager_pid": first, "duplicate_reopen": True, "closed": True})
        print(json.dumps(evidence["cycles"][-1]), flush=True)
    (folder / "verification.json").write_text(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
