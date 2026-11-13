"""Coalesced note writes; latest edits retire without depending on GUI callbacks."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import threading
import uuid

from saydraft.data.notes import NoteConflict


@dataclass(frozen=True)
class DraftState:
    generation: int
    identifier: str
    body: str
    kind: str
    revision: int
    version: int
    dirty: bool
    saving: bool
    loaded: bool
    error: str | None


class NoteDraft:
    def __init__(self, store, *, emit, executor=None):
        self.store, self.emit = store, emit
        self._owns_executor = executor is None
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix='Saydraft-notes')
        self._lock = threading.RLock()
        self._closed = self._saving = self._loaded = False
        self._generation = 0
        self._identifier, self._body, self._kind = uuid.uuid4().hex, '', 'scratchpad'
        self._revision = self._version = self._saved_version = 0
        self._error = None

    def snapshot(self):
        with self._lock:
            return DraftState(self._generation, self._identifier, self._body, self._kind,
                self._revision, self._version, self._version != self._saved_version,
                self._saving, self._loaded, self._error)

    def _publish(self):
        if not self._closed:
            try:
                self.emit(self.snapshot())
            except Exception:
                pass  # A failed/destroyed presenter cannot cancel an owned write.

    def _submit(self, operation):
        try:
            if self.executor is None:
                self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Saydraft-notes')
            return self.executor.submit(operation)
        except Exception:
            if self._owns_executor and self.executor is not None:
                self.executor.shutdown(wait=False, cancel_futures=False)
                self.executor = None
            raise

    def load(self, identifier=None):
        with self._lock:
            if self._closed or self._saving or self.snapshot().dirty:
                return False
            self._generation += 1
            generation = self._generation
            self._loaded, self._error = False, None
        self._publish()

        def read():
            try:
                note = self.store.get(identifier) if identifier is not None else self.store.active()
            except Exception:
                note, error = None, 'load'
            else:
                error = 'missing' if identifier is not None and note is None else None
            with self._lock:
                if self._closed or generation != self._generation:
                    return
                self._error = error
                if error is None:
                    self._identifier = note.id if note is not None else uuid.uuid4().hex
                    self._body = note.body if note is not None else ''
                    self._kind = note.kind if note is not None else 'scratchpad'
                    self._revision = note.revision if note is not None else 0
                    self._version = self._saved_version = 0
                    self._loaded = True
            self._publish()
        try:
            self._submit(read)
        except Exception:
            with self._lock:
                self._error = 'queue'
            self._publish()
            return False
        return True

    def new(self):
        with self._lock:
            if self._closed or self._saving or self.snapshot().dirty:
                return False
            self._generation += 1
            self._identifier, self._body, self._kind = uuid.uuid4().hex, '', 'scratchpad'
            self._revision = self._version = self._saved_version = 0
            self._loaded, self._error = True, None
        self._publish()
        return True

    def edit(self, body):
        with self._lock:
            if self._closed or not self._loaded or not isinstance(body, str):
                return False
            if body == self._body:
                return True
            self._body, self._version = body, self._version + 1
        return True

    def save(self, *, retry=False):
        with self._lock:
            if self._closed or not self._loaded or self._error and not retry:
                return False
            if self._saving:
                return True  # The in-flight loop reads the latest buffer again.
            if not self.snapshot().dirty:
                return True
            self._error, self._saving = None, True
        self._publish()
        try:
            self._submit(self._write)
        except Exception:
            with self._lock:
                self._saving, self._error = False, 'queue'
            self._publish()
            return False
        return True

    def _write(self):
        while True:
            with self._lock:
                generation, identifier, body, kind, revision, version = (self._generation,
                    self._identifier, self._body, self._kind, self._revision, self._version)
            try:
                # Untouched blank drafts need no database row. An existing note
                # cleared to empty still persists that explicit edit.
                note = self.store.save(identifier, body, expected_revision=revision, kind=kind) if (
                    revision or body.strip()) else None
            except NoteConflict:
                error = 'conflict'
            except ValueError:
                error = 'invalid'
            except Exception:
                error = 'storage'
            else:
                error = None
            with self._lock:
                if generation != self._generation:
                    self._saving = False
                    return
                if error is not None:
                    self._saving, self._error = False, error
                    settled = True
                else:
                    self._revision = note.revision if note is not None else 0
                    self._saved_version = version
                    settled = self._version == version
                    self._saving = not settled
            self._publish()
            if settled:
                return

    def save_copy(self):
        with self._lock:
            if self._closed or not self._loaded or self._saving:
                return False
            self._generation += 1
            self._identifier, self._kind = uuid.uuid4().hex, 'scratchpad'
            self._revision, self._saved_version = 0, -1
            self._error = None
        return self.save()

    def discard(self):
        """Explicitly discard only this unsaved buffer, never the stored note."""
        with self._lock:
            if self._closed or self._saving:
                return False
            self._saved_version, self._error = self._version, None
            self._loaded = False
            self._generation += 1
        return True

    def close(self, *, force=False):
        with self._lock:
            if not force and (self._saving or self.snapshot().dirty):
                return False
            self._closed = True
            self._generation += 1 if not self._saving else 0
        if self.executor is not None:
            self.executor.shutdown(wait=False, cancel_futures=False)
        return True
