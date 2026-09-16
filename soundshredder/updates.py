"""On-demand public release checks. Never sends local audio or session data."""

import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import __version__

REPOSITORY_URL = "https://github.com/xD4O/SoundShredder"
RELEASES_URL = REPOSITORY_URL + "/releases"
LATEST_API = "https://api.github.com/repos/xD4O/SoundShredder/releases/latest"
_lock = threading.Lock()
_cached = None
_expires = 0.0


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise ValueError("Expected a stable release version.")
    return tuple(int(part) for part in value.removeprefix("v").split("."))


def check_latest():
    global _cached, _expires
    # Serialize concurrent clicks and share their result; audio jobs use other locks.
    with _lock:
        if _cached is not None and time.monotonic() < _expires:
            return {**_cached, "cached": True}
        result = {"current_version": __version__, "latest_version": None,
                  "repository_url": REPOSITORY_URL, "release_url": RELEASES_URL,
                  "status": "unavailable", "checked_at": datetime.now(timezone.utc).isoformat(), "cached": False}
        request = urllib.request.Request(LATEST_API, headers={
            "Accept": "application/vnd.github+json", "User-Agent": f"SoundShredder/{__version__}",
            "X-GitHub-Api-Version": "2026-03-10",
        })
        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                payload = response.read(262145)
            if len(payload) > 262144:
                raise ValueError("Unexpected release response size.")
            release = json.loads(payload)
            if not isinstance(release, dict) or release.get("draft") is not False or release.get("prerelease") is not False:
                raise ValueError("Expected a published stable release.")
            tag = release.get("tag_name")
            latest, current = version_tuple(tag), version_tuple(__version__)
            latest_text = tag.removeprefix("v")
            status = "available" if latest > current else "current" if latest == current else "ahead"
            result.update(status=status, latest_version=latest_text,
                          release_url=RELEASES_URL + "/tag/" + tag)
            result["message"] = {
                "available": f"SoundShredder {latest_text} is available. You have {__version__}.",
                "current": f"You're up to date — SoundShredder {__version__}.",
                "ahead": f"You have {__version__}, newer than the latest published release ({latest_text}).",
            }[status]
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                result["message"] = "GitHub is limiting update checks. Try again later or open Releases."
            elif exc.code == 404:
                result["message"] = "No published release was found. You can check the GitHub project."
            else:
                result["message"] = "GitHub is unavailable right now. Try again later or open Releases."
        except (OSError, ValueError, http.client.HTTPException):
            result["message"] = "Couldn't check for updates. Check your connection or open Releases."
        _cached = result
        _expires = time.monotonic() + (30 if result["status"] == "unavailable" else 300)
        return dict(result)
