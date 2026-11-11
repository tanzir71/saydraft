

def test_default_models_dir_uses_exe_sibling_when_frozen(monkeypatch, tmp_path):
    import sys

    from voicetray.model_download import default_models_dir

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "VoiceTray.exe"))

    assert default_models_dir() == tmp_path / "models"


def test_download_whisper_model_uses_verified_downloader_and_reports_progress(tmp_path, monkeypatch):
    from voicetray.model_download import download_whisper_model

    calls = []
    progress = []

    def fake_download(model, target, *, progress_callback):
        calls.append((model["id"], target))
        progress_callback(50)

    monkeypatch.setattr("voicetray.model_download.download_model", fake_download)

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
