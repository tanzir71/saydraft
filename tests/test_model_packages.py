import copy
import hashlib
import io
import tarfile
import threading
import zipfile

import pytest

from saydraft.models.downloader import DownloadPaused, installation_ready
from saydraft.models.manifest import validate_archive_model
from saydraft.models.packages import install_archive
from saydraft.privacy.netguard import NetworkGuard


@pytest.fixture(autouse=True)
def restore_network_policy():
    yield
    NetworkGuard.uninstall()


def descriptor(content, **extra):
    return {"size": len(content), "sha256": hashlib.sha256(content).hexdigest(), **extra}


def make_package(tmp_path, *, kind="tar.bz2", payload=b"verified weights", actual=None, linked=False,
                 missing=False, duplicate=False, asset=1):
    buffer = io.BytesIO()
    member = "export/model.onnx"
    actual = payload if actual is None else actual
    if kind == "tar.bz2":
        with tarfile.open(fileobj=buffer, mode="w:bz2") as archive:
            for _ in range(2 if duplicate else 1):
                item = tarfile.TarInfo("ignored" if missing else member)
                if linked:
                    item.type, item.linkname = tarfile.SYMTYPE, "../owner.txt"
                    archive.addfile(item)
                else:
                    item.size = len(actual)
                    archive.addfile(item, io.BytesIO(actual))
            escape = tarfile.TarInfo("../owner.txt")
            escape.size = 7
            archive.addfile(escape, io.BytesIO(b"replace"))
    else:
        with zipfile.ZipFile(buffer, "w") as archive:
            info = zipfile.ZipInfo(member)
            if linked:
                info.external_attr = 0o120777 << 16
            archive.writestr(info, actual)
            archive.writestr("../owner.txt", b"replace")
    content = buffer.getvalue()
    notice = tmp_path / "assets/licenses/notice.txt"
    notice.parent.mkdir(parents=True, exist_ok=True)
    notice.write_bytes(b"Fixture license notice")
    model = {"id": "fixture-package", "revision": f"github-release-asset-{asset}", "license": "MIT",
             "download_hosts": ["api.github.com", "release-assets.githubusercontent.com"],
             "archive": descriptor(content, path="weights." + kind, format=kind, asset_id=asset,
                 url=f"https://api.github.com/repos/example/models/releases/assets/{asset}"),
             "files": [descriptor(payload, path="model.onnx", member=member),
                       descriptor(notice.read_bytes(), path="NOTICE.txt", bundled_source="assets/licenses/notice.txt")]}
    return model, content


def install(model, content, tmp_path, **kwargs):
    return install_archive(model, tmp_path / model["id"], bundled_root=tmp_path,
                           opener=lambda *args, **kw: io.BytesIO(content), **kwargs)


@pytest.mark.parametrize("kind", ["tar.bz2", "zip"])
def test_archive_publishes_only_verified_payload_and_bundled_notice(tmp_path, kind):
    model, content = make_package(tmp_path, kind=kind)
    (tmp_path / "owner.txt").write_bytes(b"original")
    progress, calls = [], []

    def opener(request, **kwargs):
        assert request.get_header("Accept") == "application/octet-stream"
        calls.append(request.full_url)
        return io.BytesIO(content)

    target = install_archive(model, tmp_path / model["id"], bundled_root=tmp_path,
                             opener=opener, progress_callback=progress.append)
    assert installation_ready(model, target, check_hashes=True)
    assert (target / "model.onnx").read_bytes() == b"verified weights"
    assert (target / "NOTICE.txt").read_bytes() == b"Fixture license notice"
    assert (tmp_path / "owner.txt").read_bytes() == b"original"
    assert progress == sorted(progress) and progress[-1] == 100
    install_archive(model, target, bundled_root=tmp_path, opener=opener)
    assert len(calls) == 1


@pytest.mark.parametrize("mutation", ["linked", "missing", "duplicate", "bad_hash"])
def test_invalid_payload_never_replaces_existing_model(tmp_path, mutation):
    old, content = make_package(tmp_path)
    target = install(old, content, tmp_path)
    kwargs = {mutation: True} if mutation != "bad_hash" else {"actual": b"modified weights"}
    model, content = make_package(tmp_path, asset=2, **kwargs)
    with pytest.raises(ValueError):
        install(model, content, tmp_path)
    assert installation_ready(old, target, check_hashes=True)
    assert list(tmp_path.glob(".*.installing"))  # Failed staging remains available.


def test_linked_zip_payload_is_rejected(tmp_path):
    model, content = make_package(tmp_path, kind="zip", linked=True)
    with pytest.raises(ValueError, match="linked"):
        install(model, content, tmp_path)
    assert not (tmp_path / model["id"]).exists()


def test_publication_failure_restores_the_previous_installed_directory(tmp_path, monkeypatch):
    from pathlib import Path

    old, content = make_package(tmp_path)
    target = install(old, content, tmp_path)
    model, content = make_package(tmp_path, asset=2, payload=b"updated weights")
    original = Path.rename

    def locked_stage(path, destination):
        if path.name.endswith(".installing"):
            raise PermissionError("Windows publication failed")
        return original(path, destination)

    monkeypatch.setattr(Path, "rename", locked_stage)
    with pytest.raises(PermissionError):
        install(model, content, tmp_path)
    assert installation_ready(old, target, check_hashes=True)
    assert list(tmp_path.glob(".*.installing"))


def test_pause_during_extraction_keeps_old_model_and_cached_archive(tmp_path):
    old, content = make_package(tmp_path)
    target = install(old, content, tmp_path)
    model, content = make_package(tmp_path, asset=2, payload=b"updated weights")
    pause = threading.Event()

    def progress(value):
        if value > 70:
            pause.set()

    with pytest.raises(DownloadPaused):
        install(model, content, tmp_path, progress_callback=progress, pause_event=pause)
    assert installation_ready(old, target, check_hashes=True)
    assert list(tmp_path.glob(".*.installing"))
    calls = []
    install_archive(model, target, bundled_root=tmp_path, opener=lambda *a, **kw: calls.append(True))
    assert not calls and installation_ready(model, target, check_hashes=True)
    previous = list((tmp_path / "_archive").iterdir())
    assert len(previous) == 1 and installation_ready(old, previous[0], check_hashes=True)


def test_missing_notice_or_insufficient_disk_space_fails_before_network(tmp_path, monkeypatch):
    from types import SimpleNamespace

    model, content = make_package(tmp_path)
    calls = []
    (tmp_path / "assets/licenses/notice.txt").write_bytes(b"modified notice")
    with pytest.raises(ValueError, match="notice"):
        install_archive(model, tmp_path / model["id"], bundled_root=tmp_path,
                        opener=lambda *a, **kw: calls.append(True))
    model, content = make_package(tmp_path)
    monkeypatch.setattr("saydraft.models.downloader.shutil.disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(OSError, match="disk space"):
        install_archive(model, tmp_path / model["id"], bundled_root=tmp_path,
                        opener=lambda *a, **kw: calls.append(True))
    assert not calls


@pytest.mark.parametrize("path", ["../outside", "C:/outside", "model:stream", "CON.txt", "trailing.", ".verified.json"])
def test_catalog_refuses_unsafe_windows_payload_names(tmp_path, path):
    model, _content = make_package(tmp_path)
    model["files"][0]["path"] = path
    with pytest.raises(ValueError, match="safe names"):
        validate_archive_model(model)


def test_catalog_pins_asset_identity_and_prevents_bundled_notice_escape(tmp_path):
    model, _content = make_package(tmp_path)
    invalid = copy.deepcopy(model)
    invalid["archive"]["url"] = "https://api.github.com/repos/example/models/releases/assets/2"
    with pytest.raises(ValueError, match="immutable"):
        validate_archive_model(invalid)
    model["files"][1]["bundled_source"] = "assets/licenses/../../owner.txt"
    with pytest.raises(ValueError, match="inside assets/licenses"):
        validate_archive_model(model)


@pytest.mark.parametrize("field,value", [("member", None), ("sha256", None), ("size", True)])
def test_catalog_rejects_malformed_payload_metadata_before_filesystem_work(tmp_path, field, value):
    model, _content = make_package(tmp_path)
    model["files"][0][field] = value
    with pytest.raises(ValueError):
        validate_archive_model(model)


def test_registered_preview_notices_match_bundled_bytes():
    from pathlib import Path
    from saydraft.asr.model_ids import PREVIEW_MODEL
    from saydraft.models.downloader import verify_file
    from saydraft.models.manifest import get_model

    model = get_model(PREVIEW_MODEL)
    assert model["role"] == "preview" and model["languages"] == ["en"]
    root = Path(__file__).resolve().parents[1]
    notices = [file for file in model["files"] if "bundled_source" in file]
    assert len(notices) == 2 and all(verify_file(root / file["bundled_source"], file) for file in notices)
