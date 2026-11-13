

import threading

from saydraft.models.manifest import get_model


def test_new_downloads_use_user_profile_even_when_frozen(monkeypatch, tmp_path):
    import sys

    from saydraft.model_download import default_models_dir

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Saydraft.exe"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))

    assert default_models_dir() == tmp_path / "profile" / "Saydraft" / "models"


def test_download_whisper_model_uses_verified_downloader_and_reports_progress(tmp_path, monkeypatch):
    from saydraft.model_download import download_whisper_model

    calls = []
    progress = []

    def fake_download(model, target, *, progress_callback):
        calls.append((model["id"], target))
        progress_callback(50)

    monkeypatch.setattr("saydraft.model_download.install_files", fake_download)

    result = download_whisper_model(
        "base",
        progress_callback=progress.append,
        models_dir=tmp_path / "models",
        config={
            "stt": {
                "device": "cpu",
                "compute_type": "int8",
            }
        },
    )

    assert result == tmp_path / "models" / "whisper-base" / get_model("whisper-base")["version"]
    assert progress == [5, 50, 100]
    assert calls == [("whisper-base", result)]


def test_existing_portable_installation_is_read_without_moving_files(tmp_path, monkeypatch):
    import hashlib
    import json
    import sys

    from saydraft.model_download import find_installed_model

    directory = tmp_path / "models" / "asr" / "fixture"
    directory.mkdir(parents=True)
    content = b"retained model"
    model = {"id": "fixture", "engine": "parakeet", "revision": "fixture", "files": [
        {"path": "weights", "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}]}
    (directory / "weights").write_bytes(content)
    (directory / ".verified.json").write_text(json.dumps(
        {"revision": model["revision"], "files": model["files"]}), encoding="utf-8")
    monkeypatch.setattr("saydraft.model_download.get_model", lambda model_id: model)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Saydraft.exe"))
    assert find_installed_model("fixture", check_hashes=True) == directory
    assert (directory / "weights").read_bytes() == content
    assert not (tmp_path / "profile").exists()


def test_one_explicit_download_covers_displayed_dependencies_with_aggregate_progress(tmp_path, monkeypatch):
    from saydraft.model_download import download_asr_model
    from saydraft.models.manifest import model_bundle

    model_id = "parakeet-tdt-0-6b-v3-int8"
    package = model_bundle(model_id)
    calls, progress, preflight = [], [], []
    monkeypatch.setattr("saydraft.model_download.check_bundle_space", lambda targets: preflight.extend(targets))

    def download(model, target, *, progress_callback, pause_event):
        calls.append((model["id"], target, pause_event))
        progress_callback(50)
        progress_callback(100)

    monkeypatch.setattr("saydraft.model_download.install_files", download)
    pause = threading.Event()
    result = download_asr_model(model_id, progress.append, models_dir=tmp_path, pause_event=pause)
    assert result == tmp_path / model_id / get_model(model_id)["version"]
    assert [call[0] for call in calls] == [model["id"] for model in package]
    assert calls[1][1] == tmp_path / "whisper-tiny-lid-int8" / get_model("whisper-tiny-lid-int8")["version"]
    assert all(call[2] is pause for call in calls)
    assert len(preflight) == 2 and progress == sorted(progress) and progress[-1] == 100


def test_preview_archive_download_is_a_separate_explicit_action(tmp_path, monkeypatch):
    from saydraft.asr.model_ids import PREVIEW_MODEL
    from saydraft.model_download import download_preview_model

    calls = []
    monkeypatch.setattr("saydraft.models.packages.install_archive", lambda model, target, **kwargs:
                        calls.append((model, target, kwargs)) or target)
    pause = threading.Event()
    target = download_preview_model(models_dir=tmp_path, pause_event=pause)
    assert target == tmp_path / PREVIEW_MODEL / get_model(PREVIEW_MODEL)["version"]
    assert calls[0][0]["role"] == "preview" and calls[0][2]["pause_event"] is pause
