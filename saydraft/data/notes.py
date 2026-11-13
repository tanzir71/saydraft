"""Local Notes with optimistic revisions; drafts never overwrite a newer edit."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
import unicodedata
import uuid

from .db import SCHEMA_VERSION, migrate_database

MAX_NOTE_BYTES = 1024 * 1024
KINDS = frozenset(('scratchpad', 'command', 'ask', 'meeting'))


class NoteConflict(ValueError):
    def __init__(self):
        super().__init__('This note changed or was deleted. Keep this draft and reload, or save it as a new note.')


@dataclass(frozen=True)
class Note:
    id: str
    kind: str
    title: str
    body: str
    created_at: str
    updated_at: str
    revision: int


@dataclass(frozen=True)
class NoteSummary:
    id: str
    kind: str
    title: str
    preview: str
    created_at: str
    updated_at: str
    revision: int


def _identifier(value):
    if not isinstance(value, str) or len(value) != 32 or uuid.UUID(value).hex != value:
        raise ValueError('Invalid note identifier')
    return value


def _revision(value):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid note revision')
    return value


def _search(value):
    return unicodedata.normalize('NFC', value).casefold()


class NoteStore:
    def __init__(self, db_path, *, clock=None):
        self.db_path = Path(db_path)
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat(timespec='microseconds'))
        self._initialized = False
        self._initialization = threading.Lock()

    @contextmanager
    def _connect(self):
        with self._initialization:
            if not self._initialized:
                migrate_database(self.db_path)
                self._initialized = True
        connection = sqlite3.connect(self.db_path.resolve().as_uri() + '?mode=rw', uri=True, timeout=3)
        connection.row_factory = sqlite3.Row
        try:
            if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
                raise ValueError('Notes database changed version; reopen Saydraft before saving')
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _note(row):
        if row is None:
            return None
        note = Note(**dict(row))
        _identifier(note.id)
        if (type(note.revision) is not int or note.revision < 1 or note.kind not in KINDS
                or any(not isinstance(value, str) for value in (note.title, note.body, note.created_at, note.updated_at))):
            raise ValueError('Invalid stored note; existing data has been preserved')
        return note

    def get(self, identifier):
        with self._connect() as connection:
            return self._note(connection.execute(
                'SELECT id, kind, title, body, created_at, updated_at, revision FROM notes WHERE id=?',
                (_identifier(identifier),)).fetchone())

    def active(self):
        with self._connect() as connection:
            return self._note(connection.execute('''SELECT n.id, n.kind, n.title, n.body,
                n.created_at, n.updated_at, n.revision FROM notes AS n JOIN note_state AS s
                ON n.id=s.note_id WHERE s.name='scratchpad' ''').fetchone())

    def list(self, query='', *, limit=200):
        if not isinstance(query, str) or len(query) > 512 or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('Invalid note search')
        pattern = '%' + _search(query).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        with self._connect() as connection:
            results = tuple(NoteSummary(**dict(row)) for row in connection.execute('''SELECT id, kind, title,
                substr(body, 1, 180) AS preview, created_at, updated_at, revision FROM notes
                WHERE search_text LIKE ? ESCAPE '\\' ORDER BY updated_at DESC, id DESC LIMIT ?''', (pattern, limit)))

            for note in results:
                _identifier(note.id)
                if (type(note.revision) is not int or note.revision < 1 or note.kind not in KINDS
                        or any(not isinstance(value, str) for value in (note.title, note.preview, note.created_at, note.updated_at))):
                    raise ValueError('Invalid stored note; existing data has been preserved')
            return results

    def save(self, identifier, body, *, expected_revision=0, kind='scratchpad', activate=True):
        identifier, revision = _identifier(identifier), _revision(expected_revision)
        if (not isinstance(body, str) or len(body.encode('utf-8')) > MAX_NOTE_BYTES
                or not isinstance(kind, str) or kind not in KINDS or type(activate) is not bool):
            raise ValueError('Invalid note or note exceeds the 1 MiB limit')
        title = next((' '.join(line.split())[:100] for line in body.splitlines() if line.strip()), 'Untitled note')
        now = self.clock()
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            previous = connection.execute('SELECT kind FROM notes WHERE id=?', (identifier,)).fetchone()
            if previous is not None and previous['kind'] != kind:
                raise NoteConflict()
            if revision == 0:
                changed = connection.execute('''INSERT OR IGNORE INTO notes
                    (id, kind, title, body, search_text, created_at, updated_at, revision)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)''', (identifier, kind, title, body, _search(body), now, now)).rowcount
            else:
                changed = connection.execute('''UPDATE notes SET title=?, body=?, search_text=?,
                    updated_at=?, revision=revision+1 WHERE id=? AND revision=?''',
                    (title, body, _search(body), now, identifier, revision)).rowcount
            if changed != 1:
                raise NoteConflict()
            if activate:
                connection.execute("INSERT INTO note_state(name,note_id) VALUES ('scratchpad',?) "
                    'ON CONFLICT(name) DO UPDATE SET note_id=excluded.note_id', (identifier,))
            return self._note(connection.execute('''SELECT id, kind, title, body, created_at,
                updated_at, revision FROM notes WHERE id=?''', (identifier,)).fetchone())

    def delete(self, identifier, *, expected_revision):
        identifier, revision = _identifier(identifier), _revision(expected_revision)
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if connection.execute('DELETE FROM notes WHERE id=? AND revision=?', (identifier, revision)).rowcount != 1:
                raise NoteConflict()
            connection.execute('DELETE FROM note_state WHERE note_id=?', (identifier,))
