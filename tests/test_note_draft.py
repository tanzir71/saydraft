"""Draft lifecycle, delayed writes, stale loads, and recoverable save failures."""

from concurrent.futures import Future
import threading

from saydraft.core.note_draft import NoteDraft
from saydraft.data.notes import NoteStore


class Queue:
    def __init__(self):
        self.pending = []

    def submit(self, action):
        future = Future()
        self.pending.append((future, action))
        return future

    def run(self, index=0):
        future, action = self.pending.pop(index)
        future.set_running_or_notify_cancel()
        try:
            future.set_result(action())
        except BaseException as error:
            future.set_exception(error)
            raise

    def shutdown(self, **options):
        pass


def draft_at(tmp_path):
    store, queue, updates = NoteStore(tmp_path / 'history.db'), Queue(), []
    draft = NoteDraft(store, emit=updates.append, executor=queue)
    assert draft.load()
    queue.run()
    assert draft.snapshot().loaded
    return draft, store, queue, updates


def test_blank_draft_is_not_a_note_but_clearing_an_existing_note_persists(tmp_path):
    draft, store, queue, _ = draft_at(tmp_path)
    assert draft.save() and not queue.pending and not store.list()
    draft.edit('First text')
    draft.save()
    queue.run()
    identifier = draft.snapshot().identifier
    draft.edit('')
    draft.save()
    queue.run()
    assert store.get(identifier).body == ''
    assert draft.snapshot().revision == 2 and not draft.snapshot().dirty
    assert draft.close()


def test_stale_load_cannot_replace_new_note_or_a_newer_load(tmp_path):
    draft, store, queue, _ = draft_at(tmp_path)
    assert draft.load()
    assert draft.new()
    draft.edit('Keep typing')
    queue.run()
    assert draft.snapshot().body == 'Keep typing' and draft.snapshot().dirty
    assert not draft.load() and not draft.new() and not draft.close()
    draft.save()
    queue.run()
    assert len(store.list()) == 1
    draft.close()


def test_deleted_open_does_not_become_an_empty_successful_load(tmp_path):
    draft, _, queue, _ = draft_at(tmp_path)
    draft.load('a' * 32)
    queue.run()
    assert draft.snapshot().error == 'missing' and not draft.snapshot().loaded
    assert draft.new() and draft.snapshot().loaded
    draft.close()


def test_conflict_retains_draft_and_save_as_new_preserves_both_versions(tmp_path):
    draft, store, queue, _ = draft_at(tmp_path)
    draft.edit('Original')
    draft.save()
    queue.run()
    identifier = draft.snapshot().identifier
    store.save(identifier, 'Edited elsewhere', expected_revision=1)
    draft.edit('My unsaved words')
    draft.save()
    queue.run()
    state = draft.snapshot()
    assert state.error == 'conflict' and state.dirty and state.body == 'My unsaved words'
    assert not draft.save() and not draft.close()
    assert draft.save_copy()
    queue.run()
    assert store.get(identifier).body == 'Edited elsewhere'
    assert store.get(draft.snapshot().identifier).body == 'My unsaved words'
    assert draft.snapshot().identifier != identifier
    draft.close()


def test_storage_failure_keeps_latest_text_and_retry_saves_it(tmp_path, monkeypatch):
    draft, store, queue, _ = draft_at(tmp_path)
    original = store.save
    def unavailable(*args, **options):
        raise OSError('private database details must not escape')
    monkeypatch.setattr(store, 'save', unavailable)
    draft.edit('Keep this draft')
    draft.save()
    queue.run()
    assert draft.snapshot().error == 'storage' and draft.snapshot().dirty
    monkeypatch.setattr(store, 'save', original)
    draft.edit('Keep the latest draft')
    draft.save(retry=True)
    queue.run()
    assert store.active().body == 'Keep the latest draft'
    assert not draft.snapshot().dirty and draft.snapshot().error is None
    draft.close()


def test_latest_edits_drain_after_force_close_without_any_gui_callback(tmp_path):
    store = NoteStore(tmp_path / 'history.db')
    entered, release = threading.Event(), threading.Event()
    original = store.save
    def delayed(*args, **options):
        entered.set()
        assert release.wait(4)
        return original(*args, **options)
    store.save = delayed
    updates = []
    draft = NoteDraft(store, emit=updates.append)
    assert draft.new()
    draft.edit('First edit')
    try:
        assert draft.save() and entered.wait(3)
        draft.edit('বাংলা العربية — latest edit')
        count = len(updates)
        assert draft.close(force=True)
    finally:
        release.set()
        draft.executor.shutdown(wait=True)
    assert store.active().body == 'বাংলা العربية — latest edit'
    assert len(updates) == count


def test_discard_invalidates_a_pending_read_and_does_not_delete_stored_note(tmp_path):
    draft, store, queue, _ = draft_at(tmp_path)
    draft.edit('Stored')
    draft.save()
    queue.run()
    identifier = draft.snapshot().identifier
    draft.edit('Unsaved')
    assert draft.discard() and not draft.snapshot().loaded
    assert not draft.edit('Cannot edit unloaded text')
    draft.load(identifier)
    queue.run()
    assert draft.snapshot().body == 'Stored' and store.get(identifier).body == 'Stored'
    draft.close()


def test_executor_rejection_preserves_draft_and_allows_explicit_retry(tmp_path):
    draft, store, queue, _ = draft_at(tmp_path)
    submit = queue.submit
    def rejected(action):
        raise RuntimeError('Cannot submit')
    queue.submit = rejected
    draft.edit('Keep when queue is unavailable')
    assert not draft.save()
    assert draft.snapshot().error == 'queue' and draft.snapshot().dirty and not draft.snapshot().saving
    queue.submit = submit
    assert draft.save(retry=True)
    queue.run()
    assert store.active().body == 'Keep when queue is unavailable'
    assert draft.close()


def test_presentation_exception_cannot_prevent_a_committed_save(tmp_path):
    draft, store, queue, _ = draft_at(tmp_path)
    def destroyed(state):
        raise TypeError('Qt signal receiver is gone')
    draft.emit = destroyed
    draft.edit('Persist without a presenter')
    assert draft.save()
    queue.run()
    assert store.active().body == 'Persist without a presenter'
    assert draft.close()
