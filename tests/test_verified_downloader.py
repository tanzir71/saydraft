import hashlib
import io
import json
import threading

import pytest

from saydraft.models.downloader import (
    DownloadPaused, _PinnedRedirects, download_model, installation_ready,
)
from saydraft.models.manifest import load_manifest
from saydraft.privacy.netguard import NetworkGuard


@pytest.fixture(autouse=True)
def restore_guard():
    yield
    NetworkGuard.uninstall()


def model_for(content):
    return {"download_hosts": ["models.example"], "files": [{
        "path": "model.bin", "url": "https://models.example/pinned/model.bin",
        "size": len(content), "sha256": hashlib.sha256(content).hexdigest(),
    }]}


def test_download_verifies_before_publishing_and_skips_verified_file(tmp_path):
    model = model_for(b"verified weights")
    calls = []

    def open_url(request, **kwargs):
        calls.append(request.full_url)
        return io.BytesIO(b"verified weights")

    download_model(model, tmp_path, opener=open_url)
    download_model(model, tmp_path, opener=open_url)
    assert (tmp_path / "model.bin").read_bytes() == b"verified weights"
    assert len(calls) == 1


def test_corrupt_download_never_becomes_loadable_and_preserves_existing_files(tmp_path):
    model = model_for(b"expected")
    (tmp_path / "model.bin").write_bytes(b"older weights")
    with pytest.raises(ValueError, match="SHA-256"):
        download_model(model, tmp_path, opener=lambda *a, **kw: io.BytesIO(b"corrupt!"))
    assert not (tmp_path / "model.bin").exists()
    contents = [file.read_bytes() for file in (tmp_path / "_archive").iterdir()]
    assert b"older weights" in contents
    assert b"corrupt!" in contents


@pytest.mark.parametrize("url", ["http://models.example/file", "https://other.example/file"])
def test_unlisted_or_insecure_redirect_is_rejected(url):
    with pytest.raises(ValueError, match="pinned HTTPS"):
        _PinnedRedirects(["models.example"]).redirect_request(None, None, 302, "", {}, url)


def test_bundled_manifest_is_pinned_and_rejects_path_traversal(tmp_path):
    data = load_manifest()
    assert {model["id"] for model in data["models"]} >= {"whisper-base", "whisper-small", "whisper-medium"}
    data["models"][0]["files"][0]["path"] = "../model.bin"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="safe names"):
        load_manifest(path)


class Response(io.BytesIO):
    def __init__(self, content, *, status=200, headers=None):
        super().__init__(content)
        self.status = status
        self.headers = headers or {}


def seed_partial(tmp_path, model, content):
    (tmp_path / "model.bin.part").write_bytes(content)
    (tmp_path / "model.bin.part.json").write_text(json.dumps(model["files"][0]), encoding="utf-8")


def test_pause_preserves_partial_and_resume_requests_exact_range(tmp_path):
    model = model_for(b"abcdef")
    pause = threading.Event()

    class SlowResponse(Response):
        def read(self, count):
            return super().read(2)

    with pytest.raises(DownloadPaused):
        download_model(model, tmp_path, opener=lambda *a, **kw: SlowResponse(b"abcdef"),
                       progress_callback=lambda value: pause.set(), pause_event=pause)
    assert not installation_ready(model, tmp_path)
    assert (tmp_path / "model.bin.part").read_bytes() == b"ab"

    def resume(request, **kwargs):
        assert request.get_header("Range") == "bytes=2-"
        return Response(b"cdef", status=206, headers={"Content-Range": "bytes 2-5/6"})

    download_model(model, tmp_path, opener=resume)
    assert installation_ready(model, tmp_path, check_hashes=True)
    assert not (tmp_path / "model.bin.part.json").exists()


def test_server_ignoring_range_restarts_and_preserves_old_partial(tmp_path):
    model = model_for(b"abcdef")
    seed_partial(tmp_path, model, b"ab")
    download_model(model, tmp_path, opener=lambda *a, **kw: Response(b"abcdef"))
    assert (tmp_path / "model.bin").read_bytes() == b"abcdef"
    assert b"ab" in [path.read_bytes() for path in (tmp_path / "_archive").iterdir()]


def test_wrong_resume_range_cannot_publish_or_damage_partial(tmp_path):
    model = model_for(b"abcdef")
    seed_partial(tmp_path, model, b"ab")
    with pytest.raises(ValueError, match="resume response"):
        download_model(model, tmp_path, opener=lambda *a, **kw: Response(
            b"cdef", status=206, headers={"Content-Range": "bytes 1-4/6"}))
    assert (tmp_path / "model.bin.part").read_bytes() == b"ab"
    assert not installation_ready(model, tmp_path)


def test_unidentified_partial_is_archived_and_truncated_transfer_can_resume(tmp_path):
    model = model_for(b"abcdef")
    (tmp_path / "model.bin.part").write_bytes(b"unrelated download")
    with pytest.raises(OSError, match="interrupted"):
        download_model(model, tmp_path, opener=lambda *a, **kw: Response(b"abc"))
    assert (tmp_path / "model.bin.part").read_bytes() == b"abc"
    assert not installation_ready(model, tmp_path)
    download_model(model, tmp_path, opener=lambda *a, **kw: Response(
        b"def", status=206, headers={"Content-Range": "bytes 3-5/6"}))
    assert installation_ready(model, tmp_path, check_hashes=True)


def test_corrupt_marker_and_same_size_weight_corruption_are_rejected_and_repaired(tmp_path):
    model = model_for(b"abcdef")
    download_model(model, tmp_path, opener=lambda *a, **kw: Response(b"abcdef"))
    (tmp_path / "model.bin").write_bytes(b"abcXYZ")
    assert not installation_ready(model, tmp_path, check_hashes=True)
    (tmp_path / ".verified.json").write_text("{", encoding="utf-8")
    assert not installation_ready(model, tmp_path)
    download_model(model, tmp_path, opener=lambda *a, **kw: Response(b"abcdef"))
    assert installation_ready(model, tmp_path, check_hashes=True)


def test_insufficient_disk_space_stops_before_network_and_retains_partial(tmp_path, monkeypatch):
    from types import SimpleNamespace

    model = model_for(b"abcdef")
    seed_partial(tmp_path, model, b"abc")
    monkeypatch.setattr("saydraft.models.downloader.shutil.disk_usage", lambda path: SimpleNamespace(free=0))
    calls = []
    with pytest.raises(OSError, match="Not enough disk space"):
        download_model(model, tmp_path, opener=lambda *a, **kw: calls.append(True))
    assert not calls
    assert (tmp_path / "model.bin.part").read_bytes() == b"abc"


def test_ignored_range_checks_space_for_full_restart_before_archiving(tmp_path, monkeypatch):
    from types import SimpleNamespace

    model = model_for(b"abcdef")
    seed_partial(tmp_path, model, b"abc")
    monkeypatch.setattr("saydraft.models.downloader.shutil.disk_usage", lambda path: SimpleNamespace(
        free=64 * 1024 * 1024 + 4))  # Enough for the tail, insufficient for a full restart.
    with pytest.raises(OSError, match="Not enough disk space"):
        download_model(model, tmp_path, opener=lambda *a, **kw: Response(b"abcdef"))
    assert (tmp_path / "model.bin.part").read_bytes() == b"abc"


@pytest.mark.parametrize("requires", [["not-a-model"], ["whisper-base"], "whisper-small"])
def test_catalog_rejects_unknown_cyclic_or_invalid_dependencies(tmp_path, requires):
    data = load_manifest()
    model = next(item for item in data["models"] if item["id"] == "whisper-base")
    model["requires"] = requires
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="dependencies"):
        load_manifest(path)


def test_bundle_checks_combined_remaining_bytes_on_same_volume(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from saydraft.models.downloader import check_bundle_space

    model = model_for(b"abcdef")
    monkeypatch.setattr("saydraft.models.downloader.shutil.disk_usage", lambda path: SimpleNamespace(
        free=64 * 1024 * 1024 + 9))  # Either model fits individually; their package does not.
    with pytest.raises(OSError, match="Not enough disk space"):
        check_bundle_space([(model, tmp_path / "primary"), (model, tmp_path / "helper")])
    assert not list(tmp_path.iterdir())
    (tmp_path / "primary").mkdir()
    seed_partial(tmp_path / "primary", model, b"abc")
    check_bundle_space([(model, tmp_path / "primary"), (model, tmp_path / "helper")])
