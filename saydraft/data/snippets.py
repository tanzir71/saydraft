"""Transactional live snippets; legacy files are copied once and kept untouched."""

from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3

from .db import SCHEMA_VERSION, _backup, migrate_database
from saydraft.snippets import CANONICAL_SOURCE, MAX_BYTES, MAX_ENTRIES, parse_document, trigger_key, validate_entries


class SnippetConflict(ValueError):
    def __init__(self):
        super().__init__("Snippets changed. Reload saved Snippets before saving this draft.")


@dataclass(frozen=True)
class SnippetSnapshot:
    rows: tuple
    revision: str

    @property
    def editable(self):
        return {row[1]: row[3] for row in self.rows}


def _snapshot(connection):
    rows = tuple(connection.execute("SELECT id, trigger, normalized, expansion, source FROM snippets ORDER BY id LIMIT ?",
        (MAX_ENTRIES + 1,)).fetchall())
    if len(rows) > MAX_ENTRIES:
        raise ValueError("Saved Snippets exceed the entry limit.")
    validate_entries({row[1]: row[3] for row in rows})
    if len({trigger_key(row[1]) for row in rows}) != len(rows):
        raise ValueError("Saved Snippets contain duplicate trigger phrases. Repair the database before editing.")
    revision = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode("utf-8")).hexdigest()
    return SnippetSnapshot(rows, revision)


class SnippetStore:
    def __init__(self, db_path, *, legacy_path):
        self.path, self.legacy_path = Path(db_path), Path(legacy_path)
        if self.path.is_file():
            with self.connect() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > SCHEMA_VERSION:
                    raise ValueError("This history database requires a newer version of Saydraft")
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if (version == SCHEMA_VERSION and "legacy_imports" in tables and
                        connection.execute("SELECT 1 FROM legacy_imports WHERE source_path=?", (CANONICAL_SOURCE,)).fetchone()):
                    return
        migrate_database(self.path, import_paths={"snippets": self.legacy_path})
        with self.connect() as connection:
            if not connection.execute("SELECT 1 FROM legacy_imports WHERE source_path=?", (CANONICAL_SOURCE,)).fetchone():
                # Preserve the pre-adoption database, including old copied rows.
                _backup(connection, self.path)
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT 1 FROM legacy_imports WHERE source_path=?", (CANONICAL_SOURCE,)).fetchone():
                    return  # Another adopter committed while the backup was made.
                if self.legacy_path.is_file():
                    with self.legacy_path.open("rb") as stream:
                        raw = stream.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES:
                        raise ValueError("Legacy Snippets exceed the 4 MB import limit. The source is untouched.")
                    incoming = parse_document(raw.decode("utf-8-sig"))
                    # Before adoption the file was live and imported SQL rows
                    # were only a copy. Honor its latest edits/deletions; retain
                    # manually maintained database entries and the backup.
                    connection.execute("DELETE FROM snippets WHERE source='import'")
                    existing = {trigger_key(row[0]) for row in connection.execute("SELECT trigger FROM snippets")}
                    for trigger, expansion in incoming.items():
                        if trigger_key(trigger) not in existing:
                            connection.execute("INSERT INTO snippets(trigger, normalized, expansion, source) VALUES (?, ?, ?, 'import')",
                                (trigger, trigger_key(trigger), expansion))
                            existing.add(trigger_key(trigger))
                _snapshot(connection)
                connection.execute("INSERT INTO legacy_imports(source_path, sha256) VALUES (?, ?)",
                    (CANONICAL_SOURCE, hashlib.sha256(CANONICAL_SOURCE.encode()).hexdigest()))

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=.25)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def read(self):
        with self.connect() as connection:
            return _snapshot(connection)

    def check_revision(self, revision):
        if self.read().revision != revision:
            raise SnippetConflict()

    def save(self, entries, *, expected_revision):
        validate_entries(entries)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = _snapshot(connection)
            if current.revision != expected_revision:
                raise SnippetConflict()
            remaining = {trigger_key(trigger): (trigger, expansion) for trigger, expansion in entries.items()}
            for row_id, trigger, _normalized, expansion, _source in current.rows:
                new = remaining.pop(trigger_key(trigger), None)
                if new is None:
                    connection.execute("DELETE FROM snippets WHERE id=?", (row_id,))
                elif new != (trigger, expansion):
                    connection.execute("UPDATE snippets SET trigger=?, normalized=?, expansion=?, source='manual' WHERE id=?",
                        (new[0], trigger_key(new[0]), new[1], row_id))
            for key, (trigger, expansion) in remaining.items():
                connection.execute("INSERT INTO snippets(trigger, normalized, expansion, source) VALUES (?, ?, ?, 'manual')",
                    (trigger, key, expansion))
            return _snapshot(connection)
