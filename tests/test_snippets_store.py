import json
import sqlite3

import pytest

from saydraft.data.db import migrate_database
from saydraft.data.snippets import SnippetConflict, SnippetStore
from saydraft.snippets import dump_document, parse_document, validate_entries


def store(tmp_path, text="addr=123 Main\n"):
    legacy = tmp_path / "snippets.txt"
    legacy.write_text(text, "utf-8")
    return SnippetStore(tmp_path / "history.db", legacy_path=legacy), legacy


def test_adoption_uses_latest_live_file_keeps_manual_rows_and_backs_up_previous_sql_copy(tmp_path):
    legacy, db = tmp_path / "snippets.txt", tmp_path / "history.db"
    legacy.write_text("old=Copied earlier\nsig=Old\n", "utf-8")
    migrate_database(db, import_paths={"snippets": legacy})
    with sqlite3.connect(db) as connection:
        connection.execute("INSERT INTO snippets(trigger,normalized,expansion,source) VALUES ('owner','owner','Keep','manual')")
        connection.execute("CREATE TABLE owner_extension (value TEXT)")
        connection.execute("INSERT INTO owner_extension VALUES ('Keep too')")
        connection.execute("INSERT INTO dictations(raw_text,cleaned_text,mode,profile,model,asr_model) VALUES ('Public old raw','Public cleaned','balanced','notes','fixture','fixture')")
        history = connection.execute("SELECT * FROM dictations").fetchall()
    raw = b'# latest edits\nsig=Current\nSIG=Last spelling wins\n'
    legacy.write_bytes(raw)
    current = SnippetStore(db, legacy_path=legacy)
    assert current.read().editable == {"owner": "Keep", "SIG": "Last spelling wins"}
    assert legacy.read_bytes() == raw
    backups = list(tmp_path.glob("history.db.bak-*"))
    assert backups
    with sqlite3.connect(backups[-1]) as connection:
        assert connection.execute("SELECT expansion FROM snippets WHERE trigger='old'").fetchone() == ("Copied earlier",)
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT value FROM owner_extension").fetchone() == ("Keep too",)
        assert connection.execute("SELECT * FROM dictations").fetchall() == history


def test_multiline_unicode_equals_backslashes_variables_and_spaces_survive_restart_and_no_legacy_resurrection(tmp_path):
    subject, legacy = store(tmp_path)
    source = legacy.read_bytes()
    before = subject.read()
    entries = {"My signature": "  বাংলা\nالعربية\n{date}\n{clipboard}\nC:\\new\\1=a  "}
    saved = subject.save(entries, expected_revision=before.revision)
    assert saved.editable == entries and legacy.read_bytes() == source
    legacy.write_text("addr=Edited old copy\nnew=Should stay in old copy\n", "utf-8")
    reopened = SnippetStore(subject.path, legacy_path=legacy)
    assert reopened.read().editable == entries
    empty = reopened.save({}, expected_revision=saved.revision)
    assert empty.editable == {}
    migrate_database(subject.path, import_paths={"snippets": legacy})
    assert SnippetStore(subject.path, legacy_path=legacy).read().editable == {}


def test_stale_drafts_and_failed_transactions_preserve_the_newer_complete_store(tmp_path):
    subject, _ = store(tmp_path)
    snapshot = subject.read()
    latest = subject.save({"new": "Current"}, expected_revision=snapshot.revision)
    with pytest.raises(SnippetConflict):
        subject.save({"old": "Stale"}, expected_revision=snapshot.revision)
    with sqlite3.connect(subject.path) as connection:
        connection.execute("CREATE TRIGGER reject_new BEFORE INSERT ON snippets BEGIN SELECT RAISE(ABORT, 'fixture failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        subject.save({"different": "Fails after delete"}, expected_revision=latest.revision)
    assert subject.read() == latest


@pytest.mark.parametrize("raw", [b'\xff', b'x' * (4 * 1024 * 1024 + 1), b'{broken'], ids=["encoding", "oversized", "json"])
def test_invalid_legacy_adoption_does_not_mark_it_complete_and_repair_can_be_retried(tmp_path, raw):
    legacy, db = tmp_path / "snippets.txt", tmp_path / "history.db"
    legacy.write_bytes(raw)
    with pytest.raises(ValueError):
        SnippetStore(db, legacy_path=legacy)
    assert legacy.read_bytes() == raw
    legacy.write_text("repaired=Ready\n", "utf-8")
    assert SnippetStore(db, legacy_path=legacy).read().editable == {"repaired": "Ready"}


def test_document_round_trip_is_lossless_and_strict_editor_refuses_ambiguous_legacy_lines():
    values = {"sig": "\n  A=B\n{clipboard}\n  ", "বাংলা": "العربية"}
    assert parse_document(dump_document(values)) == values
    assert parse_document("# old comments\nignored line\nsig=First\nSIG=Last\n") == {"SIG": "Last"}
    assert parse_document("{name}=Literal legacy phrase\n", strict=True) == {"{name}": "Literal legacy phrase"}
    with pytest.raises(ValueError, match="trigger=expansion"):
        parse_document("broken draft", strict=True)
    for data in ({"Café": "a", "CAFE\u0301": "b"}, {"": "a"}, {"a\nline": "b"}, {"x": "\0"}, {"x": "a" * 65537}):
        with pytest.raises(ValueError):
            validate_entries(data)


def test_default_runtime_reads_canonical_table_after_legacy_changes(tmp_path, monkeypatch):
    from saydraft.core.preferences import read_snippets
    subject, legacy = store(tmp_path)
    subject.save({"Signature": "Two\nlines"}, expected_revision=subject.read().revision)
    legacy.write_text("wrong=Old file\n", "utf-8")
    monkeypatch.setattr("saydraft.history.default_history_path", lambda: subject.path)
    monkeypatch.setattr("saydraft.core.preferences.resolve_data_path", lambda value: legacy)
    assert read_snippets() == {"Signature": "Two\nlines"}
    assert json.loads(dump_document(subject.read().editable)) == {"Signature": "Two\nlines"}


def test_newer_database_is_refused_without_backup_or_mutation(tmp_path):
    db, legacy = tmp_path / "history.db", tmp_path / "snippets.txt"
    with sqlite3.connect(db) as connection:
        connection.execute("PRAGMA user_version=999")
    legacy.write_bytes(b"sig=Keep untouched\n")
    original = db.read_bytes()
    with pytest.raises(ValueError, match="newer"):
        SnippetStore(db, legacy_path=legacy)
    assert db.read_bytes() == original and not list(tmp_path.glob("history.db.bak-*"))
    assert legacy.read_bytes() == b"sig=Keep untouched\n"


def test_combined_document_budget_includes_editable_json_formatting():
    from saydraft.snippets import MAX_BYTES
    entries = {f"phrase{i}": "x" * 65536 for i in range(63)}
    entries["last"] = ""
    remaining = MAX_BYTES - len(json.dumps(entries, ensure_ascii=False).encode("utf-8")) - 1
    entries["last"] = "x" * remaining
    assert len(json.dumps(entries, ensure_ascii=False).encode("utf-8")) < MAX_BYTES
    with pytest.raises(ValueError, match="4 MB"):
        dump_document(entries)
