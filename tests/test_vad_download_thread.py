import threading

import pytest
from PySide6 import QtTest, QtWidgets

from tests.test_settings_window import make_window


@pytest.mark.parametrize("fail", [False, True])
def test_vad_download_status_updates_stay_on_the_gui_thread(tmp_path, fail):
    window, *_ = make_window(tmp_path)
    main_thread, updates = threading.get_ident(), []
    original = window.status_label.setText
    def record(text):
        updates.append(threading.get_ident())
        if threading.get_ident() == main_thread:
            original(text)
    window.status_label.setText = record
    def download(progress):
        progress(100)
        if fail:
            raise OSError("fixture failure")
        return "fixture vad model"
    window.vad_download_callback = download
    window.download_vad_model()
    task = window._vad_download_task
    task._thread.join(2)
    assert not task._thread.is_alive()
    for _ in range(100):
        QtWidgets.QApplication.processEvents()
        if window._vad_download_task is None:
            break
        QtTest.QTest.qWait(10)
    assert updates and set(updates) == {main_thread}
    assert window._vad_download_task is None
    assert ("Could not" if fail else "ready") in window.status_label.text()
    window.close()


def test_destroying_the_owner_pauses_download_without_emitting_from_a_deleted_object(tmp_path, monkeypatch):
    import shiboken6

    started, release = threading.Event(), threading.Event()
    errors = []
    monkeypatch.setattr(threading, "excepthook", lambda args: errors.append(args.exc_value))
    window, *_ = make_window(tmp_path)
    def download(progress, *, pause_event):
        started.set()
        assert release.wait(2)
        progress(100)
        return "fixture finished"
    window.vad_download_callback = download
    window.download_vad_model()
    task = window._vad_download_task
    assert started.wait(1)
    try:
        shiboken6.delete(window)
    finally:
        release.set()
        task._thread.join(2)
    QtWidgets.QApplication.processEvents()
    assert not task._thread.is_alive() and not errors
    assert task.pause_event.is_set()


def test_finished_is_delivered_on_gui_only_after_the_python_thread_exits(tmp_path, monkeypatch):
    from saydraft.ui import download_task

    window, *_ = make_window(tmp_path)
    returned, release = threading.Event(), threading.Event()
    original = threading.Thread
    class DelayedExit(original):
        def run(self):
            super().run()
            returned.set()
            assert release.wait(2)
    monkeypatch.setattr(download_task.threading, "Thread", DelayedExit)
    task = download_task.DownloadTask(window)
    finished = []
    gui_thread = threading.get_ident()
    task.finished.connect(lambda: finished.append((threading.get_ident(), task._thread.is_alive())))
    task.start(lambda progress: "fixture")
    try:
        assert returned.wait(1)
        QtWidgets.QApplication.processEvents()
        assert not finished and task in download_task.DownloadTask._active
    finally:
        release.set()
        task._thread.join(2)
    for _ in range(100):
        QtWidgets.QApplication.processEvents()
        if finished:
            break
        QtTest.QTest.qWait(10)
    assert finished == [(gui_thread, False)] and task not in download_task.DownloadTask._active
    window.close()
