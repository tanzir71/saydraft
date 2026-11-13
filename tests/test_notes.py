from concurrent.futures import ThreadPoolExecutor
import sqlite3
from contextlib import closing
import uuid

import pytest

from saydraft.data.db import SCHEMA_VERSION, migrate_database
from saydraft.data.notes import MAX_NOTE_BYTES, NoteConflict, NoteStore


def identifier():
    return uuid.uuid4().hex


def test_note_round_trip_keeps_unicode_markup_and_active_draft_without_changing_history(tmp_path):
    path = tmp_path / 'history.db'
    store = NoteStore(path)
    assert not path.exists()
    body = '# <draft>\nবাংলা مرحبًا e\u0301quipe\n\n  keep spacing  \n'
    first = store.save(identifier(), body)
    assert first.revision == 1 and first.body == body
    assert NoteStore(path).active() == first and store.get(first.id) == first
    updated = store.save(first.id, body + 'New line', expected_revision=first.revision)
    assert updated.revision == 2 and updated.created_at == first.created_at
    assert store.get(first.id) == updated
    with closing(sqlite3.connect(path)) as connection, connection:
        assert connection.execute('SELECT count(*) FROM dictations').fetchone()[0] == 0


def test_external_edits_and_deletions_do_not_overwrite_or_resurrect_notes(tmp_path):
    path = tmp_path / 'history.db'
    first, second = NoteStore(path), NoteStore(path)
    note = first.save(identifier(), 'Original text')
    latest = second.save(note.id, 'Newer external edit', expected_revision=note.revision)
    with pytest.raises(NoteConflict):
        first.save(note.id, 'Stale draft', expected_revision=note.revision)
    with pytest.raises(NoteConflict):
        first.delete(note.id, expected_revision=note.revision)
    assert first.get(note.id) == latest
    second.delete(latest.id, expected_revision=latest.revision)
    with pytest.raises(NoteConflict):
        first.save(latest.id, 'Stale draft', expected_revision=latest.revision)
    assert first.active() is None and first.get(latest.id) is None


def test_search_is_unicode_casefolded_and_literal_sql_wildcards_are_not_operators(tmp_path):
    store = NoteStore(tmp_path / 'history.db')
    literal = store.save(identifier(), '100%_Ready\nবাংলা ÉQUIPE')
    store.save(identifier(), '100 percent ready')
    assert [row.id for row in store.list('%_')] == [literal.id]
    assert [row.id for row in store.list('e\u0301quipe')] == [literal.id]
    assert [row.id for row in store.list('বাংলা')] == [literal.id]
    assert store.list("' OR 1=1 --") == ()


def test_concurrent_saves_accept_exactly_one_writer_for_a_revision(tmp_path):
    path = tmp_path / 'history.db'
    stores = [NoteStore(path), NoteStore(path)]
    note = stores[0].save(identifier(), 'Original')
    stores[1].list()

    def save(pair):
        store, text = pair
        try:
            return store.save(note.id, text, expected_revision=1)
        except NoteConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = list(pool.map(save, zip(stores, ('First writer', 'Second writer'))))
    assert sum(row is not None for row in saved) == 1
    assert stores[0].get(note.id).revision == 2


def test_invalid_or_oversized_note_never_replaces_saved_content(tmp_path):
    store = NoteStore(tmp_path / 'history.db')
    note = store.save(identifier(), 'Keep this')
    for options in ({'body': 'x' * (MAX_NOTE_BYTES + 1)}, {'body': 'changed', 'expected_revision': True},
                    {'body': 'changed', 'kind': 'meeting'}, {'body': 'changed', 'kind': []}):
        arguments = {'body': 'changed', 'expected_revision': 1, **options}
        with pytest.raises((ValueError, NoteConflict)):
            store.save(note.id, **arguments)
    assert store.get(note.id) == note


def test_note_list_is_bounded_and_empty_existing_notes_are_retained(tmp_path):
    store = NoteStore(tmp_path / 'history.db')
    note = store.save(identifier(), 'First')
    store.save(identifier(), 'Second')
    blank = store.save(note.id, '', expected_revision=1)
    assert blank.title == 'Untitled note' and blank.body == ''
    assert len(store.list(limit=1)) == 1
    with pytest.raises(ValueError):
        store.list(limit=0)


def test_v2_upgrade_backs_up_existing_data_and_does_not_reimport_sources(tmp_path):
    path = tmp_path / 'history.db'
    migrate_database(path)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute('DROP TABLE note_state')
        connection.execute('DROP TABLE notes')
        connection.execute('PRAGMA user_version=2')
        connection.execute("INSERT INTO snippets(trigger, normalized, expansion, source) VALUES ('keep','keep','Original','manual')")
    before = set(tmp_path.iterdir())
    store = NoteStore(path)
    store.save(identifier(), 'A note')
    backups = [p for p in set(tmp_path.iterdir()) - before if p.name.startswith(path.name + '.bak-')]
    assert backups
    with closing(sqlite3.connect(path)) as connection, connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("SELECT expansion FROM snippets WHERE trigger='keep'").fetchone()[0] == 'Original'


@pytest.mark.parametrize('schema', [
    'secret TEXT',
    'id TEXT, kind TEXT, title TEXT, body TEXT, search_text TEXT, created_at TEXT, updated_at TEXT, revision INTEGER',
    'id TEXT PRIMARY KEY, kind TEXT, title TEXT, body TEXT, search_text TEXT, created_at TEXT, updated_at TEXT, revision INTEGER',
])
def test_unknown_notes_schema_is_preserved_and_rejected(tmp_path, schema):
    path = tmp_path / 'history.db'
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(f'CREATE TABLE notes({schema})')
        if schema == 'secret TEXT':
            connection.execute("INSERT INTO notes VALUES ('Preserve this fixture text')")
        else:
            connection.execute("INSERT INTO notes VALUES ('owner', 'scratchpad', 'Title', 'Keep বাংলা العربية', '', '', '', 1)")
    original = path.read_bytes()
    with pytest.raises(ValueError, match='Unrecognized Notes'):
        NoteStore(path).list()
    assert path.read_bytes() == original


def test_simultaneous_initializers_share_one_schema_and_preserve_all_notes(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    path = tmp_path / 'history.db'
    barrier = threading.Barrier(2)
    def initialize(text):
        store = NoteStore(path)
        barrier.wait(timeout=3)
        return store.save(identifier(), text)
    with ThreadPoolExecutor(max_workers=2) as pool:
        notes = list(pool.map(initialize, ('One', 'Two')))
    assert {row.body for row in notes} == {'One', 'Two'}
    assert {row.preview for row in NoteStore(path).list()} == {'One', 'Two'}


def test_initialized_store_refuses_newer_or_removed_database(tmp_path):
    path = tmp_path / 'history.db'
    store = NoteStore(path)
    note = store.save(identifier(), 'Keep this')
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute('PRAGMA user_version=999')
    with pytest.raises(ValueError, match='changed version'):
        store.save(note.id, 'Changed', expected_revision=1)
    path.unlink()
    with pytest.raises(sqlite3.OperationalError):
        store.get(note.id)
    assert not path.exists()
