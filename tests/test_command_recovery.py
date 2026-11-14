"""Separate owned offscreen recovery windows, with only a memory clipboard."""

from types import SimpleNamespace as NS
import threading
import uuid

import pytest

from saydraft.core.command_edit import CommandEditResult, CommandRecoveryRequest
from saydraft.data.notes import NoteStore
from tests.test_history_window import FakeClipboard
from tests.test_scratchpad import settle
from tests.test_settings_window import qt_modules


@pytest.fixture
def recovery(tmp_path):
    from PySide6 import QtTest
    from saydraft.ui.command_recovery import CommandRecoveryWindows
    qt = qt_modules()
    qt.QtTest = QtTest
    store, clipboard = NoteStore(tmp_path / 'notes.db'), FakeClipboard()
    saves = []
    group = CommandRecoveryWindows(store, clipboard=clipboard, saved=lambda: saves.append(True))
    try:
        yield NS(qt=qt, store=store, clipboard=clipboard, group=group, saves=saves)
    finally:
        for window in group.windows:
            window.shutdown()
            window.draft.executor.shutdown(wait=True)
            window.hide()
            window.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def test_results_autosave_as_independent_plain_text_notes_and_copy_only_on_click(recovery):
    f = recovery
    original = f.store.save(uuid.uuid4().hex, 'Current owner note')
    text = 'বাংলা العربية\n<script>literal text</script>\n  keep spacing  '
    first = f.group.present(CommandEditResult(text, 'focus_changed'))
    second = f.group.present(CommandEditResult('Second independent result', 'history_unavailable'))
    settle(f.qt, lambda: all(not window.draft.snapshot().dirty and not window.draft.snapshot().saving
                            for window in f.group.windows))
    assert f.store.active() == original and len(f.store.list()) == 3
    assert first.editor.toPlainText() == text and second.editor.toPlainText() == 'Second independent result'
    assert first.draft.snapshot().identifier != second.draft.snapshot().identifier
    assert not f.clipboard.texts and not first.new_button.isVisible()
    assert first.windowTitle() == 'Command edit — Saydraft' and 'History' in second.description.text()
    first.copy_button.click()
    assert f.clipboard.texts == [text] and f.saves


def test_failed_instruction_recovery_is_explicitly_labelled_and_retains_full_plain_words(recovery):
    f = recovery
    text = 'Make it shorter. বাংলা العربية <b>literal</b>'
    window = f.group.present(CommandEditResult(text, 'instruction_history_unavailable'))
    settle(f.qt, lambda: not window.draft.snapshot().dirty and not window.draft.snapshot().saving)
    assert window.windowTitle() == 'Command instruction — Saydraft'
    assert 'recognized instruction' in window.description.text() and window.editor.toPlainText() == text
    assert not f.clipboard.texts
    window.copy_button.click()
    assert f.clipboard.texts == [text] and f.store.get(window.draft.snapshot().identifier).body == text


def test_clipboard_fallback_explains_no_paste_and_copies_only_after_explicit_click(recovery):
    f = recovery
    window = f.group.present(CommandEditResult('The file arrived.', 'copy_only'))
    settle(f.qt, lambda: not window.draft.snapshot().dirty and not window.draft.snapshot().saving)
    assert 'no paste was sent' in window.description.text() and not f.clipboard.texts
    window.copy_button.click()
    assert f.clipboard.texts == ['The file arrived.']


def test_translation_and_recognized_speech_recover_separately_without_auto_copy(recovery):
    f = recovery
    raw = 'Recognized speech. ' * 1000
    source = f.group.present(CommandEditResult(raw, 'history_unavailable', task='translation_raw'))
    translated = f.group.present(CommandEditResult('الملف جاهز.', 'history_unavailable', task='translation'))
    settle(f.qt, lambda: all(not w.draft.snapshot().dirty and not w.draft.snapshot().saving for w in f.group.windows))
    assert source.windowTitle().startswith('Recognized speech') and source.editor.toPlainText() == raw
    assert translated.windowTitle().startswith('Translation') and translated.editor.toPlainText() == 'الملف جاهز.'
    assert 'No untranslated text was pasted' in source.description.text() and not f.clipboard.texts
    assert source.draft.snapshot().identifier != translated.draft.snapshot().identifier


@pytest.mark.parametrize('conflicted', [False, True])
def test_a_dirty_or_conflicted_primary_scratchpad_is_never_replaced_or_activated(recovery, conflicted):
    from saydraft.ui.scratchpad import ScratchpadWindow
    f = recovery
    primary = ScratchpadWindow(f.store, clipboard=f.clipboard)
    primary.present(new=True)
    primary.editor.setPlainText('Saved owner text')
    settle(f.qt, lambda: not primary.draft.snapshot().dirty and not primary.draft.snapshot().saving)
    stored = f.store.active()
    if conflicted:
        f.store.save(stored.id, 'Newer stored owner text', expected_revision=stored.revision)
    primary.editor.setPlainText('Unsaved owner draft')
    primary.timer.stop()
    if conflicted:
        primary.draft.save()
        settle(f.qt, lambda: primary.draft.snapshot().error == 'conflict')
    before = primary.draft.snapshot()
    active = f.store.active()
    try:
        result = f.group.present(CommandEditResult('Recovered edit', 'insertion_unconfirmed',
                                                 confirmation_reason='focus_changed'))
        settle(f.qt, lambda: not result.draft.snapshot().dirty and not result.draft.snapshot().saving)
        assert primary.draft.snapshot() == before and primary.editor.toPlainText() == 'Unsaved owner draft'
        assert f.store.active() == active and f.store.get(stored.id).body == active.body
        assert 'Check the original field' in result.description.text()
    finally:
        primary.shutdown()
        primary.draft.executor.shutdown(wait=True)
        primary.hide()
        primary.deleteLater()


def test_storage_failure_keeps_copy_available_and_blocks_quit_until_saved(recovery, monkeypatch):
    f = recovery
    save = f.store.save
    def blocked(*args, **kwargs):
        raise OSError('private storage path must not be displayed')
    monkeypatch.setattr(f.store, 'save', blocked)
    window = f.group.present(CommandEditResult('Keep this edit', 'history_unavailable'))
    settle(f.qt, lambda: window.draft.snapshot().error == 'storage')
    calls = []
    assert not f.group.flush_then(lambda: calls.append(True)) and not calls
    assert window.isVisible() and window.editor.toPlainText() == 'Keep this edit'
    assert 'private storage' not in window.status.text() and window.copy_text()
    assert f.clipboard.texts[-1] == 'Keep this edit'
    monkeypatch.setattr(f.store, 'save', save)
    window.retry_button.click()
    settle(f.qt, lambda: not window.draft.snapshot().dirty and not window.draft.snapshot().saving)
    assert f.group.flush_then(lambda: calls.append(True)) and calls == [True]
    assert f.store.active() is None and f.store.list()[0].preview == 'Keep this edit'


def test_unavailable_notes_still_show_a_recoverable_copy_window(recovery):
    f = recovery
    f.group.store = None
    window = f.group.present(CommandEditResult('Memory-only recovery', 'history_unavailable'))
    settle(f.qt, lambda: window.draft.snapshot().error == 'storage')
    assert window.copy_text() and f.clipboard.texts == ['Memory-only recovery']
    assert not f.group.flush_then(lambda: pytest.fail('Must keep unsaved edit'))


def test_close_waits_for_pending_save_then_retires_owned_window(recovery, monkeypatch):
    f = recovery
    entered, release = threading.Event(), threading.Event()
    save = f.store.save
    def delayed(*args, **kwargs):
        entered.set()
        if not release.wait(3):
            raise OSError('fixture timeout')
        return save(*args, **kwargs)
    monkeypatch.setattr(f.store, 'save', delayed)
    window = f.group.present(CommandEditResult('Persist before closing', 'focus_changed'))
    assert entered.wait(1)
    destroyed = []
    window.destroyed.connect(lambda _object=None: destroyed.append(True))
    try:
        assert not window.close() and window in f.group.windows
        release.set()
        settle(f.qt, lambda: bool(destroyed))
        f.qt.QtWidgets.QApplication.sendPostedEvents(None, f.qt.QtCore.QEvent.DeferredDelete)
        assert not f.group.windows and f.store.list()[0].preview == 'Persist before closing'
    finally:
        release.set()


def test_app_rechecks_queued_request_after_hub_setup_and_keeps_primary_window(recovery):
    from saydraft.app import SaydraftApp
    from tests.test_qt_app_shell import FakeSignalChannel
    f = recovery
    app = SaydraftApp(argv=[], command_recovery_factory=lambda *args, **kwargs: f.group)
    app.qt_app = NS(aboutToQuit=FakeSignalChannel())
    app.hub_window = NS(notes_page=NS(store=f.store, refresh=lambda: None))
    app.history_window = NS(clipboard=f.clipboard)
    app.scratchpad_window = NS(marker='Existing window')
    checks = [True, False]
    app.controller = NS(is_current_command_request=lambda request: checks.pop(0))
    app._ensure_hub = lambda: None
    request = CommandRecoveryRequest(1, object(), CommandEditResult('Queued edit', 'focus_changed'))
    app._command_recovery_requested(request)
    assert not f.group.windows and app.scratchpad_window.marker == 'Existing window'
    app.controller.is_current_command_request = lambda request: True
    app._command_recovery_requested(request)
    assert len(f.group.windows) == 1 and app.scratchpad_window.marker == 'Existing window'


def test_app_quit_flushes_all_recoveries_before_primary_draft(recovery):
    from saydraft.app import SaydraftApp
    f = recovery
    calls = []
    app = SaydraftApp(argv=[])
    app.command_recovery = f.group
    app.qt_app = NS(quit=lambda: calls.append('quit'))
    app.scratchpad_window = NS(flush_then=lambda action: (calls.append('primary'), action(), True)[-1])
    first = f.group.present(CommandEditResult('First recovered edit', 'focus_changed'))
    second = f.group.present(CommandEditResult('Second recovered edit', 'focus_changed'))
    first.editor.setPlainText('Latest first edit')
    second.editor.setPlainText('Latest second edit')
    assert app._request_quit()
    settle(f.qt, lambda: calls == ['primary', 'quit'])
    assert {note.preview for note in f.store.list()} == {'Latest first edit', 'Latest second edit'}


def test_a_primary_draft_save_refusal_is_propagated_after_recovery_flush(recovery):
    from saydraft.app import SaydraftApp
    app = SaydraftApp(argv=[])
    app.command_recovery = recovery.group
    app.qt_app = NS(quit=lambda: pytest.fail('Unsaved primary draft must block quit'))
    app.scratchpad_window = NS(flush_then=lambda action: False)
    assert not app._request_quit()


def test_recovery_request_retirement_on_cancel_and_new_capture_uses_actual_worker():
    from tests.test_session_worker import make_worker
    worker, clock, _executor, _events, signals, _keyboard = make_worker()
    try:
        result = CommandEditResult('Result', 'focus_changed')
        worker._recover_command_result(0, result)
        assert not signals
        assert worker.start_recording()
        worker._recover_command_result(worker.session.session_id, result)
        assert not any(item[0] == 'command_recovery_requested' for item in signals)
        clock.now = 1
        worker.stop_recording()
        worker._recover_command_result(worker.session.session_id, result)
        request = signals[-1][1]
        assert worker.is_current_command_request(request)
        worker.cancel()
        assert not worker.is_current_command_request(request)
        assert worker.start_recording()
        assert not worker.is_current_command_request(request)
    finally:
        worker.shutdown()


@pytest.mark.parametrize('value', [None, '', '   ', '\ud800', 'x' * 16385],
                         ids=['none', 'empty', 'blank', 'invalid-unicode', 'oversize'])
def test_incomplete_or_invalid_results_do_not_create_a_window(recovery, value):
    with pytest.raises(ValueError):
        recovery.group.present(CommandEditResult(value, 'unavailable'))
    assert not recovery.group.windows and not recovery.clipboard.texts


def test_retirement_during_window_construction_does_not_present_or_save(recovery):
    from saydraft.ui.command_recovery import CommandRecoveryWindow
    f = recovery
    active = [True]
    def factory(*args, **kwargs):
        window = CommandRecoveryWindow(*args, **kwargs)
        active[0] = False
        return window
    f.group.window_factory = factory
    assert f.group.present(CommandEditResult('Retired before presentation', 'focus_changed'), valid=lambda: active[0]) is None
    f.qt.QtWidgets.QApplication.sendPostedEvents(None, f.qt.QtCore.QEvent.DeferredDelete)
    assert not f.group.windows and not f.store.list() and not f.clipboard.texts


def test_gui_recovery_admission_never_waits_for_the_session_mutex():
    from concurrent.futures import ThreadPoolExecutor
    from tests.test_session_worker import make_worker
    worker, clock, _executor, _events, signals, _keyboard = make_worker()
    try:
        worker.start_recording()
        clock.now = 1
        worker.stop_recording()
        worker._recover_command_result(worker.session.session_id, CommandEditResult('Result', 'focus_changed'))
        request = signals[-1][1]
        with ThreadPoolExecutor(max_workers=1) as caller:
            with worker._lock:
                assert caller.submit(worker.is_current_command_request, request).result(timeout=.2)
    finally:
        worker.shutdown()
