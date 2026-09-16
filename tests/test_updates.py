import io
import json
import urllib.error
from concurrent.futures import ThreadPoolExecutor

import pytest

from soundshredder import updates


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    monkeypatch.setattr(updates, "_cached", None)
    monkeypatch.setattr(updates, "_expires", 0)
    monkeypatch.setattr(updates, "__version__", "1.0.1")


def response(monkeypatch, data):
    calls = []

    def fetch(request, timeout):
        calls.append(request)
        assert request.full_url == updates.LATEST_API and request.data is None
        assert request.get_method() == "GET" and timeout == 6
        assert request.get_header("Authorization") is None
        return io.BytesIO(json.dumps(data).encode())

    monkeypatch.setattr(updates.urllib.request, "urlopen", fetch)
    return calls


@pytest.mark.parametrize("installed,tag,status", [
    ("1.0.1", "v1.0.1", "current"), ("1.0.1", "v1.0.2", "available"),
    ("1.0.1", "v1.0.0", "ahead"), ("1.0.9", "v1.0.10", "available"),
    ("1.10.0", "1.9.0", "ahead"), ("1.0.1", "v2.0.0", "available"),
])
def test_release_comparison_and_fixed_project_links(monkeypatch, installed, tag, status):
    monkeypatch.setattr(updates, "__version__", installed)
    calls = response(monkeypatch, {"tag_name": tag, "draft": False, "prerelease": False,
                                  "html_url": "https://unrelated.invalid/download"})
    result = updates.check_latest()
    assert result["status"] == status and result["current_version"] == installed
    assert result["latest_version"] == tag.removeprefix("v")
    assert result["release_url"] == updates.RELEASES_URL + "/tag/" + tag
    assert len(calls) == 1 and not result["cached"]


@pytest.mark.parametrize("data", [
    {"tag_name": "v2.0.0", "draft": True, "prerelease": False},
    {"tag_name": "v2.0.0", "draft": False, "prerelease": True},
    {"tag_name": "v2.0.0-beta.1", "draft": False, "prerelease": False},
    {"tag_name": "../../other", "draft": False, "prerelease": False},
    {"tag_name": "v2.0.0"}, [], None,
])
def test_unexpected_release_never_claims_up_to_date(monkeypatch, data):
    response(monkeypatch, data)
    result = updates.check_latest()
    assert result["status"] == "unavailable" and result["latest_version"] is None
    assert result["release_url"] == updates.RELEASES_URL


@pytest.mark.parametrize("error,fragment", [
    (TimeoutError(), "connection"),
    (urllib.error.URLError("offline"), "connection"),
    (urllib.error.HTTPError(updates.LATEST_API, 403, "limit", {}, None), "limiting"),
    (urllib.error.HTTPError(updates.LATEST_API, 429, "limit", {}, None), "limiting"),
    (urllib.error.HTTPError(updates.LATEST_API, 404, "missing", {}, None), "No published"),
    (urllib.error.HTTPError(updates.LATEST_API, 500, "failure", {}, None), "unavailable"),
])
def test_network_failures_are_recoverable(monkeypatch, error, fragment):
    def fail(*_, **__):
        raise error

    monkeypatch.setattr(updates.urllib.request, "urlopen", fail)
    result = updates.check_latest()
    assert result["status"] == "unavailable" and fragment in result["message"]
    # A failed result expires sooner; a later click can succeed.
    monkeypatch.setattr(updates, "_expires", 0)
    response(monkeypatch, {"tag_name": "v1.0.2", "draft": False, "prerelease": False})
    assert updates.check_latest()["status"] == "available"


@pytest.mark.parametrize("body", [b"not json", b"x" * 262145], ids=["invalid-json", "oversized"])
def test_invalid_or_oversized_response(monkeypatch, body):
    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda *_, **__: io.BytesIO(body))
    assert updates.check_latest()["status"] == "unavailable"


def test_concurrent_checks_share_cache_then_expire(monkeypatch):
    calls = response(monkeypatch, {"tag_name": "v1.0.1", "draft": False, "prerelease": False})
    clock = [100.0]
    monkeypatch.setattr(updates.time, "monotonic", lambda: clock[0])
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: updates.check_latest(), range(6)))
    assert len(calls) == 1 and sum(not item["cached"] for item in results) == 1
    assert len({item["checked_at"] for item in results}) == 1
    results[0]["status"] = "altered"
    assert updates.check_latest()["status"] == "current"
    clock[0] = 401
    assert not updates.check_latest()["cached"] and len(calls) == 2
