import hashlib
import json
import os
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from saydraft.models import storage
from saydraft.models.storage_lock import storage_lock


@pytest.fixture
def subject(tmp_path):
    return make_subject(tmp_path)


def make_subject(tmp_path):
    root = storage.StorageRoot(tmp_path / "models", "App storage", True)
    content = b"tiny fixture weights"
    model = {"id": "fixture", "label": "Fixture", "engine": "llama.cpp", "role": "llm", "revision": "one",
             "files": [{"path": "weights.gguf", "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}]}
    target = root.path / "llm" / "fixture" / "one"
    target.mkdir(parents=True)
    (target / "weights.gguf").write_bytes(content)
    (target / ".verified.json").write_text(json.dumps({"revision": "one", "files": model["files"]}), encoding="utf-8")
    return root, model, target, content


def snapshot(subject):
    root, model, *_ = subject
    return storage.inventory([root], [model])


def remove(subject, entry=None, **kwargs):
    return storage.remove_model(entry or snapshot(subject).models[0], roots=[subject[0]], **kwargs)


def test_inventory_counts_all_regular_bytes_and_is_read_only(subject, monkeypatch):
    root, model, target, content = subject
    unknown = target / "owner-notes.txt"
    unknown.write_text("keep this", encoding="utf-8")
    cache = root.path / "_packages"
    cache.mkdir()
    (cache / "download.zip").write_bytes(b"cache")
    monkeypatch.setattr(storage, "verify_file", lambda *args: pytest.fail("Inventory must not hash large weights"))
    before = {path: path.read_bytes() for path in root.path.rglob("*") if path.is_file()}
    result = snapshot(subject)
    entry = result.models[0]
    assert entry.status == "Installed (receipt and sizes)"
    assert result.roots[0].total == sum(map(len, before.values()))
    assert result.roots[0].other == len(b"keep thiscache")
    assert entry.size + result.roots[0].other == result.roots[0].total
    assert before == {path: path.read_bytes() for path in before}


def test_manual_removal_preserves_unknown_files_and_other_versions(subject):
    root, model, target, content = subject
    unknown = target / "owner-notes.txt"
    unknown.write_text("keep", encoding="utf-8")
    old = target.parent / "older"
    old.mkdir()
    (old / "weights.gguf").write_bytes(content)
    (old / ".verified.json").write_text(json.dumps({"revision": "older", "files": model["files"]}), encoding="utf-8")
    entries = snapshot(subject).models
    current = next(entry for entry in entries if entry.path == target)
    assert len(entries) == 2 and any(entry.status.startswith("Retained version") for entry in entries)
    result = remove(subject, current)
    assert result.removed == 2 and not result.errors
    assert unknown.read_text() == "keep"
    assert (old / "weights.gguf").read_bytes() == content
    assert not (target / "weights.gguf").exists() and not (target / ".verified.json").exists()


def test_empty_model_folder_is_removed_without_touching_parent(subject):
    _, _, target, _ = subject
    assert not remove(subject).errors
    assert not target.exists() and target.parent.is_dir()


def test_matching_resume_files_are_explicitly_removable(subject):
    root, model, target, _ = subject
    (target / "weights.gguf").unlink()
    (target / ".verified.json").unlink()
    (target / "weights.gguf.part").write_bytes(b"tiny")
    (target / "weights.gguf.part.json").write_text(json.dumps(model["files"][0]), encoding="utf-8")
    entry = snapshot(subject).models[0]
    assert entry.status == "Partial or unverified" and len(entry.files) == 2
    assert remove(subject, entry).removed == 2
    assert not target.exists()


def test_unrecognized_resume_metadata_is_retained(subject):
    _, _, target, _ = subject
    (target / "weights.gguf.part").write_bytes(b"unknown")
    (target / "weights.gguf.part.json").write_text("{}", encoding="utf-8")
    remove(subject)
    assert (target / "weights.gguf.part").read_bytes() == b"unknown"
    assert (target / "weights.gguf.part.json").read_text() == "{}"


def test_changed_confirmation_snapshot_is_refused(subject):
    _, _, target, _ = subject
    entry = snapshot(subject).models[0]
    (target / "weights.gguf").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        remove(subject, entry)
    assert (target / ".verified.json").exists()


def test_refreshed_but_corrupt_payload_is_preserved(subject):
    _, _, target, content = subject
    (target / "weights.gguf").write_bytes(b"x" * len(content))
    with pytest.raises(ValueError, match="checksum"):
        remove(subject)
    assert (target / ".verified.json").exists() and (target / "weights.gguf").exists()


@pytest.mark.parametrize("protection", ["folder", "payload", "parent"])
def test_currently_configured_or_loaded_paths_are_refused(subject, protection):
    _, _, target, _ = subject
    path = {"folder": target, "payload": target / "weights.gguf", "parent": target.parent}[protection]
    with pytest.raises(ValueError, match="Configured or loaded"):
        remove(subject, protected=[path])
    assert (target / "weights.gguf").exists()


def test_portable_and_unapproved_roots_are_read_only(subject):
    entry = snapshot(subject).models[0]
    portable = replace(entry, root=replace(entry.root, managed=False))
    with pytest.raises(ValueError, match="Portable"):
        remove(subject, portable)
    with pytest.raises(ValueError, match="managed model storage"):
        storage.remove_model(entry, roots=[])


def test_download_write_lease_refuses_removal_without_changing_files(subject):
    entered, release = threading.Event(), threading.Event()
    def download():
        with storage_lock:
            entered.set()
            assert release.wait(5)
    thread = threading.Thread(target=download)
    thread.start()
    try:
        assert entered.wait(2)
        with pytest.raises(ValueError, match="setup is active"):
            remove(subject)
        assert (subject[2] / "weights.gguf").exists()
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive()


def test_file_lock_failure_is_reported_and_completion_marker_is_invalidated(subject, monkeypatch):
    _, _, target, _ = subject
    original = Path.unlink
    def unlink(path, *args, **kwargs):
        if path == target / "weights.gguf":
            raise PermissionError("Fixture is locked")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", unlink)
    result = remove(subject)
    assert result.removed == 1 and "Fixture is locked" in result.errors[0]
    assert not (target / ".verified.json").exists() and (target / "weights.gguf").exists()


def test_hard_linked_payload_is_excluded_from_removal(subject):
    _, _, target, content = subject
    outside = target.parent / "owner-file"
    os.link(target / "weights.gguf", outside)
    entry = snapshot(subject).models[0]
    assert all(file.name != "weights.gguf" for file in entry.files)
    remove(subject, entry)
    assert outside.read_bytes() == content and (target / "weights.gguf").read_bytes() == content


def test_linked_model_folder_is_not_followed(subject, tmp_path):
    root, model, target, _ = subject
    link = root.path / "llm" / "fixture" / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        import subprocess
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        assert result.returncode == 0
    try:
        result = snapshot(subject)
        assert len(result.models) == 1 and result.roots[0].skipped == 1
    finally:
        if link.is_junction():
            link.rmdir()
        else:
            link.unlink()


@pytest.mark.parametrize("receipt", [{"revision": "one", "files": [{"path": "../escape"}]},
                                      {"revision": "one", "files": []}, {"files": []}],
                         ids=["escape", "empty", "missing-version"])
def test_invalid_receipts_are_retained_as_unknown_files(subject, receipt):
    _, _, target, _ = subject
    (target / ".verified.json").write_text(json.dumps(receipt), encoding="utf-8")
    entry = snapshot(subject).models[0]
    assert entry.status == "Partial or unverified"
    assert all(file.name != ".verified.json" for file in entry.files)
    remove(subject, entry)
    assert json.loads((target / ".verified.json").read_text()) == receipt


def test_removal_cannot_escape_managed_root(subject):
    entry = snapshot(subject).models[0]
    with pytest.raises(ValueError, match="changed"):
        remove(subject, replace(entry, path=entry.root.path.parent))


def test_worker_reserves_idle_app_and_preserves_first_removal_reservation(monkeypatch):
    from tests.test_session_worker import make_worker
    worker, *_ = make_worker()
    def remove_model(entry, *, protected):
        assert worker.busy and not worker.start_recording()
        with pytest.raises(ValueError, match="busy"):
            worker.remove_stored_model(entry)
        assert worker.busy
        return "removed"
    monkeypatch.setattr(storage, "remove_model", remove_model)
    try:
        assert worker.remove_stored_model(object()) == "removed"
        assert not worker.busy and worker.services.recorder.started == 0
    finally:
        worker.shutdown()


def test_worker_refuses_busy_app_and_releases_reservation_after_failure(monkeypatch):
    from tests.test_session_worker import make_worker
    worker, *_ = make_worker()
    try:
        worker._inflight = 1
        with pytest.raises(ValueError, match="busy"):
            worker.remove_stored_model(object())
        worker._inflight = 0
        monkeypatch.setattr(storage, "remove_model", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("fixture failure")))
        with pytest.raises(ValueError, match="fixture failure"):
            worker.remove_stored_model(object())
        assert not worker.busy
    finally:
        worker.shutdown()


def test_configured_and_cached_models_are_protected_at_removal_time(monkeypatch, subject):
    from saydraft.asr.model_ids import DEFAULT_MODEL
    from saydraft.config import default_config
    from saydraft.model_download import model_relative_dir
    from saydraft.models.manifest import get_model
    from tests.test_session_worker import make_worker

    root = subject[0]
    monkeypatch.setattr(storage, "storage_roots", lambda: [root])
    worker, *_ = make_worker()
    worker.services.asr._engines = {"whisper-small": object()}
    worker.services.config["llm"]["model_path"] = str(subject[2] / "weights.gguf")
    observed = []
    monkeypatch.setattr(storage, "remove_model", lambda entry, *, protected: observed.extend(protected))
    try:
        worker.remove_stored_model(object())
        for identifier in (DEFAULT_MODEL, "whisper-small", "silero-vad-v5", "whisper-tiny-lid-int8"):
            assert root.path / model_relative_dir(get_model(identifier)) in observed
        assert subject[2] / "weights.gguf" in observed
        config = default_config()
        config["stt"].update(engine="whisper", routing_enabled=False, model_size=str(subject[2]))
        assert subject[2] in storage.protected_paths(config)
    finally:
        worker.shutdown()


def test_settings_wait_for_model_removal_to_finish(monkeypatch):
    from saydraft.config import default_config
    from tests.test_session_worker import make_worker
    worker, *_ = make_worker()
    original = worker.services
    new_config = default_config()
    new_config["app"]["tier"] = "lite"
    worker.services_factory = lambda *args, **kwargs: replace(original, config=new_config)
    def remove_model(entry, *, protected):
        worker.configure(new_config)
        assert worker.services is original and worker._pending_config == new_config
        return "done"
    monkeypatch.setattr(storage, "remove_model", remove_model)
    try:
        assert worker.remove_stored_model(object()) == "done"
        assert worker.services.config == new_config and worker._pending_config is None
        assert not worker.busy
    finally:
        worker.shutdown()


def test_same_revision_with_different_receipt_is_not_claimed_installed(subject):
    _, model, target, _ = subject
    receipt = {"revision": model["revision"], "files": [dict(model["files"][0], extra="changed")]}
    (target / ".verified.json").write_text(json.dumps(receipt), encoding="utf-8")
    assert snapshot(subject).models[0].status == "Retained receipt (sizes match)"
