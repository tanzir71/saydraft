import hashlib
import io
import json

import pytest

from saydraft.models.downloader import _PinnedRedirects, download_model
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
