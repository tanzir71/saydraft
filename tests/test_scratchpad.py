"""Owned offscreen Scratchpad/Notes flow; no desktop, microphone or OS clipboard."""

from types import SimpleNamespace
import time
import threading
import uuid

import pytest

from saydraft.data.notes import NoteStore
from tests.test_settings_window import qt_modules
from tests.test_history_window import FakeClipboard


def settle(qt, predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        qt.QtWidgets.QApplication.processEvents()
        qt.QtTest.QTest.qWait(5)
    qt.QtWidgets.QApplication.processEvents()
    assert predicate()


@pytest.fixture
def pad(tmp_path):
    from saydraft.ui.scratchpad import ScratchpadWindow
    qt = qt_modules()
    from PySide6 import QtTest
    qt.QtTest = QtTest
    store, clipboard = NoteStore(tmp_path / 'history.db'), FakeClipboard()
    window = ScratchpadWindow(store, clipboard=clipboard)
    window.present(new=True)
    settle(qt, lambda: window.editor.isEnabled())
    try:
        yield SimpleNamespace(qt=qt, window=window, store=store, clipboard=clipboard)
    finally:
        window.shutdown()
        window.draft.executor.shutdown(wait=True)
        window.hide()
        window.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def saved(pad):
    settle(pad.qt, lambda: not pad.window.draft.snapshot().dirty and not pad.window.draft.snapshot().saving)


def test_multilingual_autosave_close_reopen_and_copy_use_exact_plain_text(pad):
    text = 'বাংলা العربية\n<script>not markup</script>\n  keep spacing  '
    pad.window.editor.setPlainText(text)
    saved(pad)
    assert pad.store.active().body == text
    pad.window.close()
    pad.window.present()
    assert pad.window.editor.toPlainText() == text
    assert pad.window.copy_text() and pad.clipboard.texts[-1] == text
    assert pad.store.list()[0].kind == 'scratchpad'


def test_new_waits_for_old_buffer_then_starts_blank_without_clobber(pad):
    pad.window.editor.setPlainText('Keep first note')
    pad.window.present(new=True)
    settle(pad.qt, lambda: pad.window.editor.toPlainText() == '')
    assert pad.store.list()[0].preview == 'Keep first note'
    pad.window.editor.insertPlainText('Second note')
    saved(pad)
    assert {note.preview for note in pad.store.list()} == {'Keep first note', 'Second note'}


def test_queued_save_ack_cannot_replace_text_typed_before_gui_receives_it(pad):
    committed = threading.Event()
    emit = pad.window.draft.emit
    def observed(state):
        emit(state)
        if state.revision and not state.dirty and not state.saving:
            committed.set()
    pad.window.draft.emit = observed
    pad.window.editor.setPlainText('First edit')
    pad.window.timer.stop()
    assert pad.window.draft.save() and committed.wait(3)
    # The queued Qt save acknowledgement has not been delivered yet.
    pad.window.editor.moveCursor(pad.qt.QtGui.QTextCursor.End)
    pad.window.editor.insertPlainText(' latest')
    pad.qt.QtWidgets.QApplication.processEvents()
    assert pad.window.editor.toPlainText() == 'First edit latest'
    assert pad.window.draft.snapshot().dirty
    saved(pad)
    assert pad.store.active().body == 'First edit latest'


def test_quit_flushes_debounced_text_before_invoking_callback(pad):
    calls = []
    pad.window.editor.setPlainText('Latest at quit')
    assert pad.window.flush_then(lambda: calls.append(pad.store.active().body))
    assert not calls
    settle(pad.qt, lambda: bool(calls))
    assert calls == ['Latest at quit']


def test_failed_close_keeps_draft_and_retry_or_copy_remain_available(pad, monkeypatch):
    original = pad.store.save
    def blocked(*args, **options):
        raise OSError('secret path')
    monkeypatch.setattr(pad.store, 'save', blocked)
    pad.window.editor.setPlainText('Retain unsaved words')
    pad.window.close()
    settle(pad.qt, lambda: pad.window.draft.snapshot().error == 'storage')
    assert pad.window.isVisible() and pad.window.editor.toPlainText() == 'Retain unsaved words'
    assert 'secret' not in pad.window.status.text()
    assert pad.window.copy_text()
    assert not pad.window.flush_then(lambda: pytest.fail('Quit must not lose the draft'))
    monkeypatch.setattr(pad.store, 'save', original)
    pad.window.retry_button.click()
    saved(pad)
    assert pad.store.active().body == 'Retain unsaved words'


def test_conflict_cannot_overwrite_a_newer_note_and_save_copy_retains_both(pad):
    pad.window.editor.setPlainText('Original')
    saved(pad)
    note = pad.store.active()
    pad.store.save(note.id, 'Newer elsewhere', expected_revision=note.revision)
    pad.window.editor.setPlainText('My draft')
    pad.window.close()
    settle(pad.qt, lambda: pad.window.draft.snapshot().error == 'conflict'
        and pad.window.save_copy_button.isVisible() and pad.window.save_copy_button.isEnabled())
    pad.window.retry_button.click()
    assert pad.store.get(note.id).body == 'Newer elsewhere'
    pad.window.save_copy_button.click()
    saved(pad)
    assert {n.preview for n in pad.store.list()} == {'Newer elsewhere', 'My draft'}


def test_notes_search_detail_and_reopen_show_saved_scratchpad(pad):
    from saydraft.ui.notes_page import NotesPage
    pad.window.editor.setPlainText('বাংলা العربية\nPrivate fixture')
    saved(pad)
    pad.store.save(uuid.uuid4().hex, 'Other note')
    page = NotesPage(pad.store)
    page.open_requested.connect(pad.window.present)
    try:
        page.search.setText('العربية')
        settle(pad.qt, lambda: len(page.rows) == 1)
        page.list_widget.setCurrentRow(0)
        settle(pad.qt, lambda: page.current_note is not None)
        assert page.editor.toPlainText() == 'বাংলা العربية\nPrivate fixture'
        page.open_button.click()
        settle(pad.qt, lambda: pad.window.editor.isEnabled())
        assert pad.window.editor.toPlainText() == page.editor.toPlainText()
        page.search.setText('missing')
        settle(pad.qt, lambda: page.status.text() == 'No matching notes.')
        assert not page.open_button.isEnabled() and not page.editor.toPlainText()
    finally:
        page.jobs.close()
        page.jobs.executor.shutdown(wait=True)
        page.deleteLater()


def test_owned_window_destruction_flushes_debounced_text_without_gui_acknowledgement(tmp_path):
    from saydraft.ui.scratchpad import ScratchpadWindow
    qt = qt_modules()
    store = NoteStore(tmp_path / 'history.db')
    window = ScratchpadWindow(store, clipboard=FakeClipboard())
    window.present(new=True)
    window.editor.setPlainText('Last edit before destruction')
    draft = window.draft
    window.deleteLater()
    qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)
    draft.executor.shutdown(wait=True)
    assert store.active().body == 'Last edit before destruction'
