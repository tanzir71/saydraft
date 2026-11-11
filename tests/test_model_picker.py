import threading

from PySide6 import QtTest, QtWidgets

from saydraft.config import default_config
from saydraft.models.downloader import DownloadPaused
from saydraft.ui.model_picker import ModelPicker


def wait_finished(picker):
    for _ in range(100):
        QtWidgets.QApplication.processEvents()
        if picker.task is None:
            return
        QtTest.QTest.qWait(10)
    raise AssertionError("download task did not finish")


def test_optional_multilingual_model_download_requires_explicit_action():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    picker = ModelPicker(default_config(), callback=lambda model, progress: calls.append(model))
    app.processEvents()
    assert picker.model_id == "parakeet-tdt-0-6b-v3-int8"
    assert not calls
    picker.combo.setCurrentIndex(picker.combo.findData("whisper-large-v3-turbo"))
    app.processEvents()
    assert not calls
    picker.start_download()
    wait_finished(picker)
    assert calls == ["large-v3-turbo"]


def test_model_download_can_pause_and_resume_while_qt_remains_responsive():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    started = threading.Event()
    attempts = []

    def download(model, progress, *, pause_event):
        attempts.append(model)
        if len(attempts) == 1:
            started.set()
            assert pause_event.wait(2)
            raise DownloadPaused("Paused. Choose Download to resume.")
        progress(100)

    picker = ModelPicker(default_config(), callback=download)
    picker.start_download()
    assert started.wait(1)
    assert not picker.combo.isEnabled()
    assert picker.pause_button.isEnabled()
    # A queued UI callback runs while the worker waits for a pause request.
    timer_fired = []
    from PySide6 import QtCore

    QtCore.QTimer.singleShot(0, lambda: timer_fired.append(True))
    app.processEvents()
    assert timer_fired
    picker.pause()
    wait_finished(picker)
    assert "Paused" in picker.status.text()
    assert picker.combo.isEnabled()
    picker.start_download()
    wait_finished(picker)
    assert len(attempts) == 2
    assert picker.progress.value() == 100
    assert "ready" in picker.status.text()
