import json
import sqlite3
from contextlib import closing

import pytest

from saydraft.data.db import SCHEMA_VERSION, migrate_database
from saydraft.history import DictationHistoryStore, HistoryEntry

V1_SQL = """CREATE TABLE dictations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
    app_name TEXT, raw_text TEXT NOT NULL, cleaned_text TEXT NOT NULL,
    mode TEXT NOT NULL, profile TEXT NOT NULL, duration_seconds REAL, model TEXT NOT NULL,
    owner_extra TEXT)
"""


def read(path, sql, params=()):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(sql, params).fetchall()


def v1_fixture(path, *, version=1):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(V1_SQL)
        connection.executemany("INSERT INTO dictations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            (1, "2026-11-01T12:00:00Z", "Notepad", "um meet at 42", "Meet at 42", "balanced", "notes", 3.0, "base", "keep me"),
            (7, "2026-11-02T13:00:00Z", "Editor", "বাংলা العربية", "বাংলা العربية", "raw", "general", 4.0, "small", "also keep me"),
        ])
        connection.execute("CREATE TABLE owner_table (value TEXT)")
        connection.execute("INSERT INTO owner_table VALUES ('preserve this table')")
        connection.execute(f"PRAGMA user_version={version}")


@pytest.mark.parametrize("version", [0, 1])
def test_additive_migration_preserves_every_history_value_and_unknown_owner_data(tmp_path, version):
    path = tmp_path / "history.db"
    v1_fixture(path, version=version)
    before = read(path, "SELECT * FROM dictations ORDER BY id")
    report = migrate_database(path)
    assert read(path, "SELECT * FROM dictations ORDER BY id")[0][:10] == before[0]
    assert read(path, "SELECT * FROM dictations ORDER BY id")[1][:10] == before[1]
    assert read(path, "SELECT value FROM owner_table") == [("preserve this table",)]
    assert read(path, "SELECT asr_model FROM dictations ORDER BY id") == [("base",), ("small",)]
    assert report.backup_path.name.startswith("history.db.bak-")
    assert read(report.backup_path, "SELECT * FROM dictations ORDER BY id") == before
    assert read(report.backup_path, "PRAGMA user_version") == [(version,)]
    assert read(path, "PRAGMA user_version") == [(SCHEMA_VERSION,)]
    assert read(path, "SELECT sum(dictations), sum(words), sum(audio_seconds) FROM stats_daily") == [(2, 5, 7.0)]


def test_imports_copy_sources_and_remain_idempotent(tmp_path):
    glossary = tmp_path / "glossary.json"
    snippets = tmp_path / "snippets.txt"
    profiles = tmp_path / "app_profiles.json"
    glossary.write_text(json.dumps({"user_terms": ["Kubernetes"], "protected_terms": ["Qt"],
                                    "replacements": {"say draft": "Saydraft"}}), encoding="utf-8")
    snippets.write_text("# comment\naddress=123 Main Street\n", encoding="utf-8")
    profiles.write_text(json.dumps([{"match": "Notepad", "profile": "notes", "mode": "aggressive",
                                     "paste_blocked": True}]), encoding="utf-8")
    sources = {path: path.read_bytes() for path in (glossary, snippets, profiles)}
    database = tmp_path / "history.db"
    first = migrate_database(database)
    assert first.imported == {"glossary": 3, "snippets": 1, "profiles": 1}
    assert first.backup_path is None  # New databases have no prior data to back up.
    assert read(database, "SELECT term, kind, replacement FROM dictionary ORDER BY id") == [
        ("Kubernetes", "user", None), ("Qt", "protected", None), ("say draft", "replacement", "Saydraft"),
    ]
    assert read(database, "SELECT trigger, expansion FROM snippets") == [("address", "123 Main Street")]
    settings = json.loads(read(database, "SELECT settings_json FROM styles")[0][0])
    assert settings["paste_blocked"] is True
    second = migrate_database(database)
    assert second.backup_path is None
    assert second.imported == {}
    assert {path: path.read_bytes() for path in sources} == sources


def test_wal_rows_are_in_the_pre_migration_backup(tmp_path):
    path = tmp_path / "history.db"
    v1_fixture(path)
    with closing(sqlite3.connect(path)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE dictations SET raw_text='latest WAL words' WHERE id=1")
        writer.commit()
        report = migrate_database(path)
        assert read(report.backup_path, "SELECT raw_text FROM dictations WHERE id=1") == [("latest WAL words",)]
        assert read(path, "SELECT raw_text FROM dictations WHERE id=1") == [("latest WAL words",)]


def test_failed_migration_rolls_back_all_schema_and_data_changes(tmp_path, monkeypatch):
    import saydraft.data.db as db

    path = tmp_path / "history.db"
    v1_fixture(path)
    before_columns = read(path, "PRAGMA table_info(dictations)")
    before_rows = read(path, "SELECT * FROM dictations")
    monkeypatch.setattr(db, "_TABLES", {"broken": "not valid SQL"})
    with pytest.raises(sqlite3.OperationalError):
        migrate_database(path)
    assert read(path, "PRAGMA table_info(dictations)") == before_columns
    assert read(path, "SELECT * FROM dictations") == before_rows
    assert len(list(tmp_path.glob("history.db.bak-*"))) == 1


def test_newer_schema_is_never_downgraded(tmp_path):
    path = tmp_path / "history.db"
    v1_fixture(path, version=99)
    original = path.read_bytes()
    with pytest.raises(ValueError, match="newer version"):
        migrate_database(path)
    assert path.read_bytes() == original


def test_invalid_import_can_be_repaired_without_touching_history(tmp_path):
    glossary = tmp_path / "glossary.json"
    glossary.write_text("broken JSON", encoding="utf-8")
    database = tmp_path / "history.db"
    migrate_database(database)
    assert glossary.read_text() == "broken JSON"
    glossary.write_text('{"user_terms":["Repaired"]}', encoding="utf-8")
    assert migrate_database(database).imported == {"glossary": 1}
    assert read(database, "SELECT term FROM dictionary") == [("Repaired",)]


def test_new_metadata_and_final_timings_preserve_text_and_do_not_double_count_stats(tmp_path):
    store = DictationHistoryStore(tmp_path / "history.db")
    entry_id = store.append(HistoryEntry("Notepad", "um three words", "Three clean words", "balanced", "notes", 2.0,
                                         "base", app_exe="notepad.exe", app_group="notes", language="en",
                                         timings_json=json.dumps({"stt": 0.4})))
    for _ in range(2):
        store.update_timings(entry_id, {"stt": 0.4, "insert": 0.3})
    row = store.list_recent()[0]
    assert (row.raw_text, row.cleaned_text) == ("um three words", "Three clean words")
    assert (row.app_exe, row.app_group, row.language, row.asr_model) == ("notepad.exe", "notes", "en", "base")
    assert json.loads(row.timings_json) == {"stt": 0.4, "insert": 0.3}
    stats = read(store.db_path, "SELECT dictations, words, audio_seconds, processing_seconds FROM stats_daily")
    assert stats[0][:3] == (1, 3, 2.0)
    assert stats[0][3] == pytest.approx(0.7)
