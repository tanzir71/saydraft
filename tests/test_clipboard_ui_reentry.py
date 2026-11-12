"""A clipboard renderer needing GUI work must not block GUI cancellation/settings."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from saydraft.config import default_config
from saydraft.core.interfaces import TargetContext
from saydraft.core.session import SessionState
from saydraft.insert.clipboard_handles import ClipboardUnavailable
from saydraft.insert.clipboard_win import WindowsClipboard
from saydraft.insert.inserter import Inserter
from tests.test_clipboard_transactions import Api
from tests.test_inserter import FakeKeyboard
from tests.test_processing import make_processor
from tests.test_session_worker import make_worker


@pytest.mark.parametrize("action", ["copy", "recover"])
def test_gui_clipboard_actions_return_busy_without_waiting_for_a_worker_transaction(action):
    clipboard = WindowsClipboard(api_factory=Api)
    held, release = threading.Event(), threading.Event()
    def worker():
        with clipboard._lock:
            held.set()
            assert release.wait(5)
    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert held.wait(2)
        with ThreadPoolExecutor(max_workers=1) as gui:
            def invoke():
                if action == "recover":
                    return clipboard.recover()
                with pytest.raises(ClipboardUnavailable, match="active"):
                    clipboard.setText("public fixture")
                return False
            future = gui.submit(invoke)
            try:
                assert future.result(timeout=1) is False
            finally:
                release.set()
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive()


@pytest.mark.parametrize("action", ["cancel", "settings", "shutdown"])
def test_gui_session_actions_can_run_while_native_snapshot_waits_for_gui_rendering(action):
    api, keyboard = Api(), FakeKeyboard()
    clipboard = WindowsClipboard(api_factory=lambda: api)
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
                        delivery_guard=lambda target: "", sleep=lambda delay: None)
    processor, events, notices = make_processor(inserter=inserter)
    worker, clock, executor, _, _, _ = make_worker(queued=True, processor=(processor, events, notices))
    worker.services.inserter = inserter
    worker.services.context.capture = lambda: TargetContext(123, "Fixture")
    original = api.data()
    renderer_needed, rendered = threading.Event(), threading.Event()
    get = api.get
    def render(format):
        renderer_needed.set()
        assert rendered.wait(5)
        return get(format)
    api.get = render
    worker.start_recording()
    executor.drain()
    clock.now = 1
    worker.stop_recording()
    failures = []
    def processing():
        try:
            executor.drain()
        except Exception as error:
            failures.append(error)
    thread = threading.Thread(target=processing)
    thread.start()
    try:
        assert renderer_needed.wait(2)
        with ThreadPoolExecutor(max_workers=1) as gui:
            def invoke():
                if action == "settings":
                    config = default_config()
                    config["dictation"]["profile"] = "chat"
                    replacement = replace(worker.services, config=config)
                    worker.services_factory = lambda *args, **kwargs: replacement
                    worker.configure(config)
                    assert worker._pending_config == config
                elif action == "cancel":
                    worker.cancel()
                else:
                    worker.shutdown()
                return True
            future = gui.submit(invoke)
            try:
                assert future.result(timeout=1)
            finally:
                rendered.set()
    finally:
        rendered.set()
        thread.join(2)
    assert not thread.is_alive() and not failures
    assert [event[0] for event in events] == ["history"] and worker.last_result.history_id == 1
    if action == "settings":
        assert worker.last_result.insertion.status == "inserted"
        assert worker.services.config["dictation"]["profile"] == "chat" and worker._pending_config is None
        assert keyboard.ops == [("send", "ctrl+v")]
    else:
        assert worker.last_result.insertion.reason == "cancelled" and not keyboard.ops
    assert api.data() == original
    api.assert_retired()
    worker.shutdown()


def test_unexpected_delivery_exception_retires_inserting_state_and_allows_next_recording():
    def failed(*args, **kwargs):
        raise RuntimeError("fixture delivery failure")
    processor, events, notices = make_processor()
    processor.inserter.insert_text = failed
    worker, clock, *_ = make_worker(processor=(processor, events, notices))
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert worker.last_result.history_id == 1 and worker.last_result.insertion.reason == "insertion_error"
    assert worker.session.state == SessionState.NOT_INSERTED and not worker.busy
    assert worker.start_recording()
    worker.cancel()
    worker.shutdown()


@pytest.mark.parametrize("through_copy_slot", [False, True])
def test_history_selection_mime_and_builtin_copy_keep_all_privacy_formats(through_copy_slot):
    from PySide6 import QtWidgets
    from saydraft.insert._clipboard_win32 import PRIVACY_FORMATS
    from saydraft.ui.private_text import PrivatePlainTextEdit
    from tests.test_history_window import qt_modules
    qt_modules()
    app = QtWidgets.QApplication.instance()
    if app.platformName() != "offscreen":
        pytest.skip("Selection-copy unit test requires the process-local offscreen clipboard")
    editor = PrivatePlainTextEdit()
    editor.setReadOnly(True)
    editor.setPlainText("Public selection\nবাংলা العربية")
    editor.selectAll()
    try:
        if through_copy_slot:
            editor.copy()  # C++ copy slot must dispatch the virtual MIME override too.
            data = app.clipboard().mimeData()
        else:
            data = editor.createMimeDataFromSelection()  # The same hook serves selection drags.
        assert data.text() == editor.toPlainText()
        for name in PRIVACY_FORMATS:
            assert bytes(data.data(f'application/x-qt-windows-mime;value="{name}"')) == bytes(4)
    finally:
        if through_copy_slot:
            app.clipboard().clear()
        editor.close()
