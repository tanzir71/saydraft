"""Versioned publication and compatibility use only tiny, disposable payloads."""

import copy
import hashlib
import io
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from saydraft.models.downloader import DownloadPaused, check_bundle_space, installation_ready
from saydraft.models.installation import installation_target, install_files, staging_directory
from saydraft.models.layout import archive_cache_directory, legacy_model_relative_dir, model_relative_dir
from saydraft.models.manifest import load_manifest, model_version
from saydraft.models.storage import StorageRoot, inventory, protected_paths, removal_reason
from saydraft.privacy.netguard import NetworkGuard


CONTENT = b"abcdef"
PIN = "a" * 40


@pytest.fixture(autouse=True)
def restore_network():
    yield
    NetworkGuard.uninstall()


def tiny_model():
    return {"id": "fixture", "engine": "parakeet", "revision": PIN, "version": PIN,
            "download_hosts": ["models.example"], "files": [{"path": "model.bin",
            "url": f"https://models.example/{PIN}/model.bin", "size": len(CONTENT),
            "sha256": hashlib.sha256(CONTENT).hexdigest()}]}


def write_model(model, target, content=CONTENT):
    target.mkdir(parents=True, exist_ok=True)
    for file in model["files"]:
        (target / file["path"]).write_bytes(content)
    (target / ".verified.json").write_text(json.dumps({"revision": model["revision"], "files": model["files"]}), encoding="utf-8")
    return target


def state(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


CATALOG = load_manifest()["models"]


@pytest.mark.parametrize("catalog", CATALOG, ids=[model["id"] for model in CATALOG])
def test_every_role_uses_explicit_pinned_versions_and_reads_legacy_in_place(tmp_path, monkeypatch, catalog):
    import saydraft.model_download as facade
    model = dict(catalog, files=tiny_model()["files"])
    model.pop("archive", None)
    assert model_version(catalog) == catalog["revision"] == catalog["version"]
    assert model_relative_dir(catalog) == Path(catalog["id"]) / catalog["version"]
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    monkeypatch.setattr(facade, "__file__", str(tmp_path / "source" / "saydraft" / "model_download.py"))
    monkeypatch.setattr(facade, "get_model", lambda identifier: model)
    root = facade.default_models_dir()
    legacy = write_model(model, root / legacy_model_relative_dir(model))
    before = state(root)
    legacy_before = state(legacy)
    assert facade.find_installed_model(model["id"], check_hashes=True) == legacy
    assert installation_target(root, model) == legacy
    assert install_files(model, legacy, opener=lambda *args, **kwargs: pytest.fail("Unexpected network")) == legacy
    assert state(root) == before and not (root / model_relative_dir(model)).exists()
    current = write_model(model, root / model_relative_dir(model))
    assert facade.find_installed_model(model["id"], check_hashes=True) == current
    (current / model["files"][0]["path"]).write_bytes(b"xxxxxx")
    assert facade.find_installed_model(model["id"], check_hashes=True) == legacy
    assert state(legacy) == legacy_before


@pytest.mark.parametrize("version", ["../escape", "C:/outside", ".hidden", "_archive", "CON", "", None, [], "different-pin"],
                         ids=["escape", "absolute", "hidden", "reserved", "device", "empty", "null", "list", "alias"])
def test_catalog_rejects_unsafe_or_mutable_version_aliases(tmp_path, version):
    data = copy.deepcopy(load_manifest())
    data["models"][0]["version"] = version
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="versions"):
        load_manifest(path)


def test_old_descriptors_without_version_keep_their_revision_pin():
    model = tiny_model()
    model.pop("version")
    assert model_relative_dir(model) == Path("fixture") / PIN


def test_new_file_installation_publishes_only_after_complete_hash_verification(tmp_path):
    model = tiny_model()
    target = tmp_path / model_relative_dir(model)
    progress, calls = [], []
    def changed(value):
        progress.append(value)
        assert target.exists() == (value == 100)
    def open_url(*args, **kwargs):
        calls.append(True)
        assert not target.exists()
        return io.BytesIO(CONTENT)
    assert install_files(model, target, opener=open_url, progress_callback=changed) == target
    assert installation_ready(model, target, check_hashes=True) and progress[-1] == 100
    assert not staging_directory(target).exists()
    install_files(model, target, opener=open_url)
    assert len(calls) == 1


def test_pause_and_range_resume_do_not_expose_the_live_version(tmp_path):
    from tests.test_verified_downloader import Response
    model = tiny_model()
    target = tmp_path / model_relative_dir(model)
    pause = threading.Event()
    class Slow(Response):
        def read(self, count):
            return super().read(2)
    with pytest.raises(DownloadPaused):
        install_files(model, target, opener=lambda *args, **kwargs: Slow(CONTENT),
                      pause_event=pause, progress_callback=lambda value: pause.set())
    assert not target.exists()
    assert (staging_directory(target) / "model.bin.part").read_bytes() == b"ab"
    pause.clear()
    def resume(request, **kwargs):
        assert request.get_header("Range") == "bytes=2-" and not target.exists()
        return Response(b"cdef", status=206, headers={"Content-Range": "bytes 2-5/6"})
    install_files(model, target, opener=resume, pause_event=pause)
    assert installation_ready(model, target, check_hashes=True)


def test_paused_setup_and_read_only_space_preflight_create_no_folders(tmp_path):
    model = tiny_model()
    target = tmp_path / model_relative_dir(model)
    pause = threading.Event()
    pause.set()
    with pytest.raises(DownloadPaused):
        install_files(model, target, pause_event=pause)
    assert not list(tmp_path.iterdir())
    check_bundle_space([(model, staging_directory(target))])
    assert not list(tmp_path.iterdir())


def test_corrupt_transfer_keeps_current_and_older_versions_then_repair_preserves_unknowns(tmp_path):
    model = tiny_model()
    old = dict(model, revision="b" * 40, version="b" * 40)
    older = write_model(old, tmp_path / model_relative_dir(old))
    target = write_model(model, tmp_path / model_relative_dir(model), b"xxxxxx")
    (target / "owner.txt").write_bytes(b"keep")
    before = state(tmp_path)
    with pytest.raises(ValueError, match="SHA-256"):
        install_files(model, target, opener=lambda *args, **kwargs: io.BytesIO(b"broken"))
    assert all((tmp_path / name).read_bytes() == content for name, content in before.items())
    install_files(model, target, opener=lambda *args, **kwargs: io.BytesIO(CONTENT))
    assert installation_ready(model, target, check_hashes=True)
    assert installation_ready(old, older, check_hashes=True)
    preserved = list((target.parent / "_archive").glob("*/owner.txt"))
    assert len(preserved) == 1 and preserved[0].read_bytes() == b"keep"


def test_atomic_publication_failure_restores_the_previous_directory(tmp_path, monkeypatch):
    model = tiny_model()
    previous = dict(model, revision="older", version="older")
    target = write_model(previous, tmp_path / model_relative_dir(model))
    (target / "owner.txt").write_bytes(b"keep")
    before = state(target)
    original = Path.rename
    def locked(path, destination):
        if path == staging_directory(target):
            raise PermissionError("Fixture publication failure")
        return original(path, destination)
    monkeypatch.setattr(Path, "rename", locked)
    with pytest.raises(PermissionError, match="publication failure"):
        install_files(model, target, opener=lambda *args, **kwargs: io.BytesIO(CONTENT))
    assert state(target) == before and installation_ready(previous, target, check_hashes=True)
    assert installation_ready(model, staging_directory(target), check_hashes=True)


def test_hard_linked_resume_files_cannot_modify_the_original(tmp_path):
    model = tiny_model()
    target = tmp_path / model_relative_dir(model)
    stage = staging_directory(target)
    stage.mkdir(parents=True)
    owner = tmp_path / "owner.bin"
    owner.write_bytes(b"ab")
    os.link(owner, stage / "model.bin.part")
    (stage / "model.bin.part.json").write_text(json.dumps(model["files"][0]), encoding="utf-8")
    with pytest.raises(ValueError, match="hard linked"):
        install_files(model, target, opener=lambda *args, **kwargs: pytest.fail("Unexpected network"))
    assert owner.read_bytes() == b"ab" and not target.exists()


@pytest.mark.parametrize("kind", ["tar.bz2", "zip"])
def test_archive_versions_keep_separate_payloads_and_download_caches(tmp_path, kind):
    from saydraft.models.packages import install_archive
    from tests.test_model_packages import make_package
    old, content = make_package(tmp_path, kind=kind)
    first = tmp_path / "models" / model_relative_dir(old)
    install_archive(old, first, bundled_root=tmp_path, opener=lambda *args, **kwargs: io.BytesIO(content))
    model, newer = make_package(tmp_path, kind=kind, asset=2, payload=b"new verified weights")
    second = tmp_path / "models" / model_relative_dir(model)
    install_archive(model, second, bundled_root=tmp_path, opener=lambda *args, **kwargs: io.BytesIO(newer))
    assert first != second and installation_ready(old, first, check_hashes=True)
    assert installation_ready(model, second, check_hashes=True)
    assert archive_cache_directory(old, first) != archive_cache_directory(model, second)
    assert not (first.parent / "_archive").exists()


def test_archive_space_preflight_counts_unpacked_and_compressed_bytes_without_writing(tmp_path, monkeypatch):
    from tests.test_model_packages import make_package
    model, content = make_package(tmp_path)
    target = tmp_path / "models" / model_relative_dir(model)
    required = sum(file["size"] for file in model["files"]) + len(content) + 64 * 1024**2
    before = state(tmp_path)
    monkeypatch.setattr("saydraft.models.downloader.shutil.disk_usage", lambda path: SimpleNamespace(free=required - 1))
    with pytest.raises(OSError, match="Not enough disk space"):
        check_bundle_space([(model, target)])
    assert state(tmp_path) == before and not target.exists()
    cache = archive_cache_directory(model, target)
    cache.mkdir(parents=True)
    (cache / model["archive"]["path"]).write_bytes(content)
    monkeypatch.setattr("saydraft.models.downloader.shutil.disk_usage", lambda path: SimpleNamespace(
        free=sum(file["size"] for file in model["files"]) + 64 * 1024**2))
    before = state(tmp_path)
    check_bundle_space([(model, target)])
    assert state(tmp_path) == before and not target.exists()


def test_inventory_and_protection_cover_both_layouts_but_not_staging_or_cache(tmp_path, monkeypatch):
    from saydraft.config import default_config
    from saydraft.models import storage
    import saydraft.models.manifest as manifest
    model = tiny_model()
    old = dict(model, revision="b" * 40, version="b" * 40)
    root = StorageRoot(tmp_path, "App storage", True)
    current = write_model(model, tmp_path / model_relative_dir(model))
    older = write_model(old, tmp_path / model_relative_dir(old))
    legacy = write_model(model, tmp_path / legacy_model_relative_dir(model))
    stage = write_model(model, staging_directory(current))
    cache = write_model(model, current.parent / "_packages" / PIN)
    before = state(tmp_path)
    result = inventory([root], [model])
    assert {entry.path for entry in result.models} == {current, older, legacy}
    assert result.roots[0].other == sum(len(content) for folder in (stage, cache) for content in state(folder).values())
    monkeypatch.setattr(storage, "storage_roots", lambda: [root])
    monkeypatch.setattr(manifest, "model_bundle", lambda identifier: [model])
    protection = protected_paths(default_config(), [model["id"]])
    assert current in protection and legacy in protection and older not in protection
    assert removal_reason(next(entry for entry in result.models if entry.path == older), protection) == ""
    assert state(tmp_path) == before


@pytest.mark.parametrize("location", ["version-parent", "stage", "archive-cache"])
def test_linked_install_paths_are_refused_before_network_or_external_changes(tmp_path, location):
    import subprocess
    from saydraft.models.packages import install_archive
    from tests.test_model_packages import make_package
    model, content = make_package(tmp_path)
    target = tmp_path / "models" / model_relative_dir(model)
    link = {"version-parent": target.parent, "stage": staging_directory(target),
            "archive-cache": archive_cache_directory(model, target)}[location]
    outside = tmp_path / "outside-fixture"
    outside.mkdir()
    (outside / "owner.txt").write_bytes(b"untouched")
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        assert result.returncode == 0
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match="linked"):
            if location == "archive-cache":
                install_archive(model, target, bundled_root=tmp_path,
                                opener=lambda *args, **kwargs: pytest.fail("Unexpected network"))
            else:
                files = tiny_model()
                files.update(id=model["id"], revision=model["revision"], version=model["revision"])
                install_files(files, target, opener=lambda *args, **kwargs: pytest.fail("Unexpected network"))
        assert state(outside) == {"owner.txt": b"untouched"}
    finally:
        if link.is_junction():
            link.rmdir()
        else:
            link.unlink()


def test_linked_archive_partial_is_preserved_without_appending(tmp_path):
    from saydraft.models.packages import install_archive
    from tests.test_model_packages import make_package
    model, _ = make_package(tmp_path)
    target = tmp_path / "models" / model_relative_dir(model)
    cache = archive_cache_directory(model, target)
    cache.mkdir(parents=True)
    original = tmp_path / "outside-fixture.bin"
    original.write_bytes(b"partial")
    os.link(original, cache / (model["archive"]["path"] + ".part"))
    with pytest.raises(ValueError, match="hard linked"):
        install_archive(model, target, bundled_root=tmp_path,
                        opener=lambda *args, **kwargs: pytest.fail("Unexpected network"))
    assert original.read_bytes() == b"partial" and not target.exists()


def test_legacy_partials_are_preserved_when_new_versioned_downloads_are_started(tmp_path):
    model = tiny_model()
    legacy = tmp_path / legacy_model_relative_dir(model)
    legacy.mkdir(parents=True)
    (legacy / "model.bin.part").write_bytes(b"ab")
    (legacy / "model.bin.part.json").write_text(json.dumps(model["files"][0]), encoding="utf-8")
    before = state(legacy)
    target = installation_target(tmp_path, model)
    assert target == tmp_path / model_relative_dir(model)
    install_files(model, target, opener=lambda *args, **kwargs: io.BytesIO(CONTENT))
    assert installation_ready(model, target, check_hashes=True) and state(legacy) == before


def test_qt_removal_of_an_old_version_preserves_current_and_legacy_models(tmp_path, monkeypatch):
    from saydraft.models import storage
    import saydraft.models.manifest as manifest
    from saydraft.ui.model_storage import ModelStorage
    from tests.test_model_storage_ui import settle
    from tests.test_settings_window import qt_modules
    from tests.test_session_worker import make_worker
    qt_modules()
    model = tiny_model()
    old = dict(model, revision="b" * 40, version="b" * 40)
    root = StorageRoot(tmp_path, "App storage", True)
    current = write_model(model, tmp_path / model_relative_dir(model))
    legacy = write_model(model, tmp_path / legacy_model_relative_dir(model))
    older = write_model(old, tmp_path / model_relative_dir(old))
    monkeypatch.setattr(storage, "storage_roots", lambda: [root])
    monkeypatch.setattr(manifest, "model_bundle", lambda identifier: [model])
    worker, *_ = make_worker()
    page = ModelStorage(config_provider=lambda: worker.services.config,
                        inventory_provider=lambda: inventory([root], [model]), remove_callback=worker.remove_stored_model)
    try:
        page.refresh()
        settle(page)
        index = next(i for i, entry in enumerate(page.snapshot.models) if entry.path == older)
        page.combo.setCurrentIndex(index)
        assert page.remove_button.isEnabled() and str(older) in page.details.text()
        page.confirm = lambda entry: entry.path == older
        page.request_remove()
        settle(page)
        assert not older.exists() and installation_ready(model, current, check_hashes=True)
        assert installation_ready(model, legacy, check_hashes=True)
        assert not page.remove_button.isEnabled() and not worker.busy
    finally:
        page.close()
        worker.shutdown()


def test_storage_details_wrap_long_paths_without_changing_their_text():
    from saydraft.ui.model_storage import StorageDetailsLabel
    from tests.test_settings_window import qt_modules
    qt_modules()
    label = StorageDetailsLabel()
    font = label.font()
    font.setPixelSize(22)
    label.setFont(font)
    text = "Revision: " + PIN + "\nFolder: C:\\Users\\Example\\AppData\\Local\\Saydraft\\models\\fixture\\" + PIN
    label.setText(text)
    document = label.document_for_width(300)
    document.size()  # Complete native text layout before measuring glyph runs.
    block, widths = document.begin(), []
    while block.isValid():
        layout = block.layout()
        widths.extend(layout.lineAt(i).naturalTextWidth() for i in range(layout.lineCount()))
        block = block.next()
    assert widths and max(widths) <= 301
    assert label.text() == text and document.toPlainText() == text
    label.close()
