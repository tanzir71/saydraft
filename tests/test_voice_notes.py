"""Voice notes share recognition/History, but have no foreground delivery ports."""
from types import SimpleNamespace
import uuid

import pytest

from saydraft.core.session import SessionState as State
from saydraft.data.notes import NoteStore
from saydraft.history import DictationHistoryStore
from tests.test_processing import make_processor
from tests.test_session_worker import make_worker


def forbidden(*args, **kwargs):
    raise AssertionError('A voice note must not inspect or modify the foreground')


def setup_note(tmp_path, *, queued=False):
    history = DictationHistoryStore(db_path=tmp_path / 'history.db')
    processor = make_processor(history=history)
    worker, clock, executor, events, signals, _ = make_worker(queued=queued, processor=processor)
    worker.services.notes = NoteStore(history.db_path)
    worker.services.context = SimpleNamespace(capture=forbidden, focus=forbidden, verify=forbidden)
    worker.services.inserter.insert_text = forbidden
    worker.services.processor.snippet_clipboard = forbidden
    return worker, clock, executor, signals


def test_toggle_saves_separate_note_after_history_without_changing_active_draft(tmp_path):
    worker, clock, _, signals = setup_note(tmp_path)
    store = worker.services.notes
    draft = store.save(uuid.uuid4().hex, 'Still editing this draft')
    original = store.save
    def save(*args, **kwargs):
        assert worker.services.history.search_page().total == 1
        return original(*args, **kwargs)
    store.save = save
    assert worker.record_note()
    assert worker.note_recording_status() == 'recording'
    assert not any(t.seconds == 3 for t in worker._timers)
    clock.now = 12
    assert worker.record_note()
    notes = store.list()
    assert len(notes) == 2 and store.active().id == draft.id
    voice = next(n for n in notes if n.id != draft.id)
    assert store.get(voice.id).body == 'clean raw transcript'
    row = worker.services.history.search_page().rows[0]
    assert row.app_name == 'Voice note' and worker.services.history.get_row(row.id).profile == 'notes'
    assert ('notes_updated',) in signals
    assert ('note_status_changed', 'saving') in signals
    assert signals[-1] == ('note_status_changed', 'idle')
    assert worker.note_recording_status() == 'idle'
    worker.stop_recording()
    assert len(store.list()) == 2


@pytest.mark.parametrize('queued', [False, True])
def test_cancel_discards_note_and_never_reads_foreground(tmp_path, queued):
    worker, clock, executor, signals = setup_note(tmp_path, queued=queued)
    assert worker.record_note()
    clock.now = 1
    worker.cancel()
    executor.drain()
    assert worker.session.state == State.CANCELLED
    assert not worker.services.notes.list()
    assert worker.services.history.search_page().total == 0
    assert worker.note_recording_status() == 'idle'


def test_note_cannot_hijack_ordinary_dictation_or_processing(tmp_path):
    worker, clock, executor, signals = setup_note(tmp_path, queued=True)
    worker.services.context.capture = lambda: SimpleNamespace(app_title='Notepad', app_group='general', app_exe='', app_site='')
    assert worker.start_recording()
    generation = worker.session.session_id
    assert not worker.record_note()
    assert worker.session.session_id == generation and worker._insert_text
    worker.cancel()
    executor.drain()
    assert not worker.services.notes.list()


def test_note_write_failure_preserves_history_and_reports_recovery(tmp_path):
    worker, clock, _, signals = setup_note(tmp_path)
    worker.services.notes.save = lambda *a, **kw: (_ for _ in ()).throw(OSError('disk full'))
    worker.record_note()
    clock.now = 1
    worker.record_note()
    assert worker.services.history.search_page().total == 1
    assert not worker.services.notes.list()
    assert ('notes_updated',) not in signals
    assert any('saved in History' in s[1] for s in signals if s[0] == 'notification_requested')


def test_failed_history_never_creates_or_claims_saved_note(tmp_path):
    worker, clock, _, signals = setup_note(tmp_path)
    worker.services.history.append = lambda *a: (_ for _ in ()).throw(OSError('disk full'))
    worker.record_note()
    clock.now = 1
    worker.record_note()
    assert not worker.services.notes.list()
    assert worker.last_result.history_id is None
    assert ('notes_updated',) not in signals


def test_note_respects_time_limit_and_can_start_another_note(tmp_path):
    worker, clock, _, _ = setup_note(tmp_path)
    worker.record_note()
    first_generation = worker.session.session_id
    clock.now = worker.services.config['recording']['max_seconds']
    worker._cap(first_generation)
    assert len(worker.services.notes.list()) == 1
    worker.record_note()
    worker.stop_recording(session_id=first_generation)
    assert worker.note_recording_status() == 'recording'
    clock.now += 2
    worker.record_note()
    assert len(worker.services.notes.list()) == 2


def test_note_stop_during_arming_cancels_and_busy_save_cannot_restart(tmp_path):
    worker, clock, executor, _ = setup_note(tmp_path, queued=True)
    worker.record_note()
    worker.record_note()
    executor.drain()
    assert not worker.services.notes.list()
    worker.record_note()
    executor.drain()
    clock.now = 1
    worker.record_note()
    assert worker.note_recording_status() == 'saving'
    assert not worker.record_note()
    executor.drain()
    assert len(worker.services.notes.list()) == 1


def test_note_disables_foreground_profiles_and_translation(tmp_path):
    worker, clock, _, _ = setup_note(tmp_path)
    worker.services.profiles = [{'app': '*', 'mode': 'aggressive', 'profile': 'email'}]
    worker.services.config['dictation']['profile'] = 'email'
    worker.record_note()
    assert worker._context.profile == 'notes' and not worker._context.translation_target
    clock.now = 1
    worker.record_note()


def test_note_bar_copy_does_not_ask_to_paste():
    from saydraft.ui.bar_motion import insertion_message
    assert insertion_message('note_saved', saved=True, paste_hint='Shift+Alt+Z') == (
        'Note saved', 'Available in Notes and History')
    assert 'recover' in insertion_message('note_save_failed', saved=True, paste_hint='Shift+Alt+Z')[1]


@pytest.mark.parametrize('binding,keys', [('f10', ('f10',)), ('ctrl+alt+n', ('left_ctrl', 'left_alt', 'n'))])
def test_native_note_repeat_does_not_toggle_twice_and_custom_binding_survives(tmp_path, binding, keys):
    from saydraft.core.hotkey_service import HotkeyService
    from tests.test_native_recording import factory
    from tests.test_notes_shortcuts import feed
    worker, clock, _, _ = setup_note(tmp_path)
    worker.services.config['hotkeys']['save'] = binding
    create, owners = factory()
    worker.hotkeys = HotkeyService(worker.services.config, start=worker.start_recording,
        stop=worker.stop_recording, cancel=worker.cancel, save=worker.record_note,
        notify=lambda message: None, native_factory=create)
    worker.hotkeys.start()
    try:
        owner = owners[-1]
        for index, key in enumerate(keys):
            feed(owner, key, True, 1 + index / 100)
        feed(owner, keys[-1], True, 1.1)
        for key in reversed(keys):
            feed(owner, key, False, 1.2)
        assert worker.note_recording_status() == 'recording'
        clock.now = 2
        for key in keys:
            feed(owner, key, True, 2)
        for key in reversed(keys):
            feed(owner, key, False, 2.1)
        assert len(worker.services.notes.list()) == 1
        assert worker.services.config['hotkeys']['save'] == binding
    finally:
        worker.hotkeys.stop()
