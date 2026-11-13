import io
import hashlib

import pytest

from saydraft.models.downloader import DownloadPaused, installation_ready
from saydraft.models.installation import install_files, staging_directory
from saydraft.models.progress import FileProgress
from saydraft.privacy.netguard import NetworkGuard
from tests.test_versioned_models import CONTENT, tiny_model


@pytest.fixture(autouse=True)
def restore_network():
    yield
    NetworkGuard.uninstall()


def test_file_progress_reports_verification_before_complete_directory_publication(tmp_path):
    model = tiny_model()
    target = tmp_path / model["id"] / model["version"]
    events = []

    def observe(event):
        assert not target.exists()
        assert event.model_id == model["id"] and event.filename == "model.bin"
        if event.phase == "verifying":
            assert not (staging_directory(target) / ".verified.json").exists()
        events.append(event)

    install_files(model, target, opener=lambda *_a, **_k: io.BytesIO(CONTENT), file_progress_callback=observe)
    assert [e.phase for e in events] == ["checking", "downloading", "verifying", "verified"]
    assert events[-1].completed_bytes == events[-1].total_bytes == len(CONTENT)
    assert installation_ready(model, target, check_hashes=True)
    cached = []
    install_files(model, target, opener=lambda *_a, **_k: pytest.fail("verified cache fetched"),
        file_progress_callback=cached.append)
    assert [e.phase for e in cached] == ["verified"]


def test_corrupt_file_never_reports_verified_or_publishes_live_installation(tmp_path):
    model = tiny_model()
    target = tmp_path / model["id"] / model["version"]
    events = []
    with pytest.raises(ValueError, match="SHA-256"):
        install_files(model, target, opener=lambda *_a, **_k: io.BytesIO(b"ghijkl"), file_progress_callback=events.append)
    assert events[-1].phase == "verifying"
    assert not any(e.phase == "verified" for e in events)
    assert not target.exists()


def test_pause_during_file_progress_keeps_resumable_bytes_and_no_ready_marker(tmp_path):
    import threading

    model = tiny_model()
    target = tmp_path / model["id"] / model["version"]
    pause, events = threading.Event(), []

    def observe(event):
        events.append(event)
        if event.phase == "downloading":
            pause.set()

    with pytest.raises(DownloadPaused):
        install_files(model, target, opener=lambda *_a, **_k: io.BytesIO(CONTENT),
            pause_event=pause, file_progress_callback=observe)
    assert not target.exists() and not any(e.phase == "verified" for e in events)
    assert (staging_directory(target) / "model.bin.part").read_bytes() == CONTENT
    pause.clear()
    install_files(model, target, opener=lambda *_a, **_k: pytest.fail("complete partial fetched"),
        pause_event=pause, file_progress_callback=events.append)
    assert events[-1].phase == "verified" and installation_ready(model, target, check_hashes=True)


@pytest.mark.parametrize("changes", [{"filename": "../private"}, {"completed_bytes": -1},
    {"total_bytes": 0}, {"completed_bytes": 7}, {"phase": "ready"}, {"completed_bytes": True}])
def test_file_progress_refuses_paths_invalid_bounds_and_unknown_phases(changes):
    args = {"model_id": "public-model", "filename": "model.bin", "completed_bytes": 0,
        "total_bytes": 6, "phase": "checking"}
    args.update(changes)
    with pytest.raises(ValueError):
        FileProgress(**args)


def test_file_progress_is_bounded_even_when_http_returns_tiny_chunks(tmp_path):
    model = tiny_model()
    data = b"abcd" * 1024 * 1024
    model["files"][0].update(size=len(data), sha256=hashlib.sha256(data).hexdigest())

    class Response(io.BytesIO):
        def read(self, size):
            return super().read(min(size, 4096))

    events = []
    install_files(model, tmp_path / model["id"] / model["version"],
        opener=lambda *_a, **_k: Response(data), file_progress_callback=events.append)
    assert len([event for event in events if event.phase == "downloading"]) <= 101
    assert events[-1].completed_bytes == len(data)


def test_bundled_notice_reports_verification_without_a_network_transfer(tmp_path, monkeypatch):
    data = b"public license fixture"
    source = tmp_path / "notice.txt"
    source.write_bytes(data)
    monkeypatch.setattr("saydraft.models.manifest.bundled_license_path", lambda _path: source)
    model = tiny_model()
    model["files"] = [{"path": "LICENSE.txt", "bundled_source": "assets/licenses/fixture.txt",
        "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}]
    events = []
    install_files(model, tmp_path / model["id"] / model["version"],
        opener=lambda *_a, **_k: pytest.fail("bundled notice fetched"), file_progress_callback=events.append)
    assert [event.phase for event in events] == ["checking", "verifying", "verified"]


def test_explicit_default_bundle_forwards_file_progress_for_primary_and_language_detector(tmp_path, monkeypatch):
    from saydraft.asr.model_ids import DEFAULT_MODEL
    from saydraft.model_download import download_asr_model

    def install(model, target, *, progress_callback, pause_event, file_progress_callback):
        file = model["files"][0]
        file_progress_callback(FileProgress(model["id"], file["path"], file["size"], file["size"], "verified"))
        progress_callback(100)
        return target

    monkeypatch.setattr("saydraft.model_download.install_files", install)
    events, progress = [], []
    download_asr_model(DEFAULT_MODEL, models_dir=tmp_path, progress_callback=progress.append,
        file_progress_callback=events.append)
    assert [event.model_id for event in events] == [DEFAULT_MODEL, "whisper-tiny-lid-int8"]
    assert progress[-1] == 100


def test_per_file_details_cross_the_real_queued_download_task_and_ignore_foreign_artifacts():
    import threading
    from PySide6 import QtCore, QtTest, QtWidgets
    from saydraft.config import default_config
    from saydraft.models.manifest import get_model
    from saydraft.asr.model_ids import DEFAULT_MODEL
    from saydraft.ui.model_picker import ModelPicker
    from tests.test_model_picker import wait_finished

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    file = get_model(DEFAULT_MODEL)["files"][0]
    started, release = threading.Event(), threading.Event()

    def download(_model, progress, *, pause_event, file_progress_callback):
        progress(40)
        file_progress_callback(FileProgress(DEFAULT_MODEL, file["path"], file["size"], file["size"], "verifying"))
        file_progress_callback(FileProgress("foreign-fixture", "model.bin", 6, 6, "verified"))
        started.set()
        assert release.wait(3)

    picker = ModelPicker(default_config(), callback=download)
    try:
        picker.start_download()
        assert started.wait(1)
        for _ in range(5):
            app.processEvents()
            QtTest.QTest.qWait(1)
        assert file["path"] in picker.file_status.text()
        assert "Verifying SHA-256" in picker.file_status.text()
        assert "foreign" not in picker.file_status.text()
        assert picker.progress.value() == 40 and picker.task is not None
        assert picker.license_label.textInteractionFlags() & QtCore.Qt.LinksAccessibleByKeyboard
        details = picker.file_status.text()
        for foreground, background in (("#f5f2e9", "#111111"), ("#141414", "#f5f2e9")):
            picker.setStyleSheet(f"QWidget {{ color: {foreground}; background-color: {background}; }}")
            for _ in range(5):
                app.processEvents()
            assert f"color:{foreground}" in picker.license_label.text()
            assert picker.file_status.text() == details and picker.progress.value() == 40
            assert picker.task is not None and picker.model_id == DEFAULT_MODEL
        release.set()
        wait_finished(picker)
    finally:
        release.set()
        picker.close()


def test_changing_model_clears_the_previous_download_completion_and_file_details():
    from PySide6 import QtWidgets
    from saydraft.config import default_config
    from saydraft.ui.model_picker import ModelPicker
    from tests.test_model_picker import wait_finished

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    picker = ModelPicker(default_config(), callback=lambda *_a: None)
    try:
        picker.start_download()
        wait_finished(picker)
        assert picker.progress.value() == 100 and "ready" in picker.status.text()
        picker.combo.setCurrentIndex(picker.combo.findData("whisper-small"))
        app.processEvents()
        assert picker.progress.isHidden() and picker.progress.value() < 0
        assert not picker.status.text() and not picker.file_status.text()
    finally:
        picker.close()
