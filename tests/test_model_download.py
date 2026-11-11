

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

    monkeypatch.setattr("saydraft.model_download.download_model", fake_download)

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

    assert result == tmp_path / "models" / "whisper" / "base"
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
