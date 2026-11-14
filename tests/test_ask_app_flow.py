"""Actual worker -> review -> model port -> History -> independent Qt answer."""

from types import SimpleNamespace as NS
import uuid

import pytest

from saydraft.app import SaydraftApp, WorkerController
from saydraft.data.notes import NoteStore
from tests.test_ask_controller import rig
from tests.test_history_window import FakeClipboard, qt_modules
from tests.test_qt_app_shell import FakeSignalChannel
from tests.test_scratchpad import settle


@pytest.fixture
def subject(tmp_path):
    from PySide6 import QtTest
    f = rig(tmp_path)
    qt = qt_modules()
    qt.QtTest = QtTest
    app = SaydraftApp(argv=[])
    app.qt_app = NS(aboutToQuit=FakeSignalChannel(), quit=lambda: None)
    app.controller = WorkerController.__new__(WorkerController)
    app.controller.core = f.worker
    clipboard = FakeClipboard()
    app.history_window = NS(clipboard=clipboard)
    store = NoteStore(f.worker.services.history.db_path)
    primary = store.save(uuid.uuid4().hex, 'Primary note must stay active')
    app.hub_window = NS(notes_page=NS(store=store, refresh=lambda: None))
    app._ensure_hub = lambda: pytest.fail('Ask must not construct Settings or discover microphone devices')
    request = f.review()
    app._ask_review_requested(request)
    assert app.ask_window is not None
    try:
        yield NS(f=f, app=app, qt=qt, request=request, clipboard=clipboard, store=store, primary=primary)
    finally:
        if app.ask_window is not None:
            app.ask_window.retire()
        if app.ask_answers is not None:
            for window in app.ask_answers.windows:
                window.shutdown()
                window.draft.executor.shutdown(wait=True)
                window.hide()
                window.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def deliver(subject):
    s = subject
    s.app.ask_window.question.setPlainText('When does it open?')
    s.app.ask_window.ask_button.click()
    s.f.executor.drain()
    for signal in s.f.signals:
        if signal[0] == 'ask_status_changed':
            s.app._ask_status_changed(signal[1])
        elif signal[0] == 'ask_answer_requested':
            s.app._ask_answer_requested(signal[1])


def test_reviewed_read_only_text_reaches_model_then_history_and_separate_scratchpad(subject):
    s = subject
    deliver(s)
    assert s.f.calls[0][:2] == ('The library opens on Saturday.', 'When does it open?')
    answer = s.app.ask_answers.windows[0]
    settle(s.qt, lambda: not answer.draft.snapshot().dirty and not answer.draft.snapshot().saving)
    row = s.f.worker.services.history.list_recent()[0]
    assert row.mode == 'ask' and row.raw_text == 'When does it open?' and row.cleaned_text == answer.editor.toPlainText()
    assert s.store.active() == s.primary and len(s.store.list()) == 2
    assert not s.clipboard.texts and s.f.worker.services.history.last_transcript() is None
    answer.copy_button.click()
    assert s.clipboard.texts == [row.cleaned_text]


def test_new_capture_drops_queued_answer_popup_while_preserving_saved_history(subject):
    s = subject
    s.app.ask_window.question.setPlainText('Question')
    s.app.ask_window.ask_button.click()
    s.f.executor.drain()
    s.f.worker.ask.invalidate_answer()
    for signal in s.f.signals:
        if signal[0] == 'ask_answer_requested':
            s.app._ask_answer_requested(signal[1])
        elif signal[0] == 'ask_status_changed':
            s.app._ask_status_changed(signal[1])
    assert s.app.ask_answers is None and len(s.f.worker.services.history.list_recent()) == 1
    assert 'saved in History' in s.app.ask_window.status.text()
    assert s.store.active() == s.primary and len(s.store.list()) == 1 and not s.clipboard.texts


def test_answer_store_can_open_without_building_hub_or_settings(subject):
    s = subject
    s.app.hub_window = None
    paths = []
    def create(path):
        paths.append(path)
        return NoteStore(path)
    s.app.ask_notes_store_factory = create
    deliver(s)
    answer = s.app.ask_answers.windows[0]
    settle(s.qt, lambda: not answer.draft.snapshot().dirty and not answer.draft.snapshot().saving)
    assert paths == [s.f.worker.services.history.db_path]
    assert s.store.active() == s.primary and not s.clipboard.texts


def test_late_review_signal_cannot_open_after_another_capture_has_started(subject):
    s = subject
    s.app.ask_window.retire()
    s.app.ask_window = s.app.ask_request = None
    request = s.f.review()
    s.f.worker.ask.invalidate_answer()
    s.app.ask_window_factory = lambda *args, **kwargs: pytest.fail('Retired review must not construct a window')
    s.app._ask_review_requested(request)
    assert s.app.ask_window is None and not s.f.worker.ask.review_is_current(request)
