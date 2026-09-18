"""Model storage can follow the Electron folder choice without changing source defaults."""
import urllib.request
from pathlib import Path

from soundshredder import bubble


def test_bubble_download_and_temporary_file_use_selected_storage(tmp_path, monkeypatch):
    models = tmp_path / "Selected drive with spaces" / "models"
    monkeypatch.setenv("SOUNDSHREDDER_MODEL_HOME", str(models))
    monkeypatch.setattr(bubble, "sha256", lambda _: bubble.MODEL_SHA)
    class Download:
        headers = {"Content-Length": "4"}
        def __enter__(self):
            self.sent = False
            return self
        def __exit__(self, *args):
            pass
        def read(self, _):
            if self.sent:
                return b""
            self.sent = True
            assert list((models / "audiosep").glob("audiosep-*.part"))
            return b"data"
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: Download())
    result = bubble.checkpoint(lambda *_: None)
    assert result == models / "audiosep/audiosep_base_4M_steps.ckpt"
    assert result.read_bytes() == b"data"
    assert not list(result.parent.glob("*.part"))


def test_source_version_keeps_its_existing_model_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("SOUNDSHREDDER_MODEL_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _: tmp_path))
    cached = tmp_path / ".cache/soundshredder/audiosep/audiosep_base_4M_steps.ckpt"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"cached")
    monkeypatch.setattr(bubble, "sha256", lambda _: bubble.MODEL_SHA)
    def unexpected(*args, **kwargs):
        raise AssertionError("A valid existing cache must not be downloaded again")
    monkeypatch.setattr(urllib.request, "urlopen", unexpected)
    assert bubble.checkpoint(lambda *_: None) == cached
