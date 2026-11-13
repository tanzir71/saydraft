import csv
import io
import sqlite3
import threading

import pytest

from saydraft.history import DictationHistoryStore, HistoryEntry
from saydraft.data.history_view import HistoryExportCancelled, save_history_export


def populated(tmp_path, count=451):
    store = DictationHistoryStore(tmp_path / "history.db")
    with store._connect() as connection:
        connection.executemany("""INSERT INTO dictations(app_name,raw_text,cleaned_text,mode,profile,model,
            app_exe,language,llm_decision) VALUES (?,?,?,'balanced','notes',?,'public.exe','en',?)""",
            [("Public app", f"raw {i}", "Straße café বাংলা العربية 100%_literal" if i == 1 else f"Public result {i}",
                "unique-model" if i == 3 else "fixture", "rules_budget" if i == 7 else "disabled") for i in range(1, count + 1)])
    return store


def test_pages_cover_every_id_once_and_do_not_include_live_appends_until_refresh(tmp_path):
    store = populated(tmp_path)
    first = store.search_page(limit=200)
    assert (first.total, first.offset, first.ceiling_id) == (451, 0, 451)
    assert [row.id for row in first.rows] == list(range(451, 251, -1))
    assert first.selected.id == 451 and not hasattr(first.rows[0], "raw_text")
    added = store.append(HistoryEntry("New", "new", "New", "raw", "notes", 1, "fixture"))
    second = store.search_page(limit=200, offset=200, ceiling_id=first.ceiling_id)
    last = store.search_page(limit=200, offset=400, ceiling_id=first.ceiling_id)
    assert [row.id for page in (first, second, last) for row in page.rows] == list(range(451, 0, -1))
    assert store.search_page().rows[0].id == added
    located = store.search_page(limit=25, selected_id=1)
    assert located.selected.id == 1 and located.offset == 450
    assert store.search_page(limit=25, offset=10000).offset == 450


@pytest.mark.parametrize("query,expected", [("STRASSE", 1), ("CAFE\u0301", 1), ("বাংলা", 1), ("العربية", 1),
    ("100%_literal", 1), ("unique-model", 3), ("rules_budget", 7), ("' OR 1=1 --", None)])
def test_global_search_is_unicode_aware_literal_and_includes_metadata_beyond_the_latest_page(tmp_path, query, expected):
    page = populated(tmp_path).search_page(query=query)
    assert [row.id for row in page.rows] == ([expected] if expected else [])
    assert page.total == (1 if expected else 0)


def test_summary_is_bounded_and_only_selected_entry_loads_its_complete_text(tmp_path):
    store = populated(tmp_path, 2)
    text = "Public long text " * 2000
    with store._connect() as connection:
        connection.execute("UPDATE dictations SET raw_text=?,cleaned_text=?", (text, text))
    page = store.search_page()
    assert len(page.rows) == 2 and all(len(row.preview) <= 512 for row in page.rows)
    assert page.selected.raw_text == text and page.selected.cleaned_text == text
    assert store.get_row(1).raw_text == text and store.get_row(999) is None


def test_private_snapshot_freezes_complete_rows_and_cleans_up_without_changing_source_mode(tmp_path):
    store = populated(tmp_path, 3)
    with store._connect() as connection:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    snapshot = store.snapshot()
    path = snapshot.db_path
    assert path.parent == store.db_path.parent and path.is_file()
    store.append(HistoryEntry("New", "new", "New", "raw", "notes", 1, "fixture"))
    with store._connect() as connection:
        connection.execute("UPDATE dictations SET cleaned_text='Changed live' WHERE id=1")
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == mode
    assert snapshot.search_page().total == 3 and snapshot.get_row(1).cleaned_text != "Changed live"
    with snapshot._connect() as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM dictations")
    del snapshot
    assert not path.exists()


def test_live_writer_can_commit_between_online_backup_steps(tmp_path, monkeypatch):
    store = populated(tmp_path, 400)
    with store._connect() as connection:
        connection.execute("UPDATE dictations SET raw_text=?", ("public padding " * 500,))
    wrote = []
    def between_steps(seconds):
        if not wrote:
            wrote.append(store.append(HistoryEntry("Live", "live words", "Live words", "raw", "notes", 1, "fixture")))
    monkeypatch.setattr("saydraft.history.time.sleep", between_steps)
    snapshot = store.snapshot()
    assert wrote and store.get_row(wrote[0]).cleaned_text == "Live words"
    assert snapshot.search_page().total >= 400


def test_cancelled_snapshot_and_query_leave_source_and_temporary_files_intact(tmp_path):
    store = populated(tmp_path)
    with pytest.raises(InterruptedError):
        store.snapshot(cancelled=lambda: True)
    assert not list(tmp_path.glob(".saydraft-history-*.sqlite"))
    with pytest.raises(sqlite3.OperationalError):
        store.search_page(query="not present", cancelled=lambda: True)
    assert store.search_page().total == 451


@pytest.mark.parametrize("format", ["md", "csv"])
def test_export_streams_all_filtered_rows_from_one_frozen_view_while_live_history_changes(tmp_path, format):
    store = populated(tmp_path)
    view = store.snapshot()
    original = view.search_page(query="Public result")
    rows = view.iter_filtered(query=original.query, ceiling_id=original.ceiling_id)
    first = next(rows)
    store.append(HistoryEntry("New", "new", "Public result newly appended", "raw", "notes", 1, "fixture"))
    with store._connect() as connection:
        connection.execute("UPDATE dictations SET cleaned_text='changed source' WHERE id=1")
    def all_rows():
        yield first
        yield from rows
    target = tmp_path / ("export." + format)
    count = save_history_export(target, all_rows(), format)
    assert count == 450
    text = target.read_text("utf-8")
    assert "newly appended" not in text and "changed source" not in text
    if format == "csv":
        parsed = list(csv.DictReader(io.StringIO(text)))
        assert len(parsed) == 450 and parsed[0]["id"] == "451" and parsed[-1]["id"] == "2"
    else:
        assert text.count("## Dictation #") == 450


def test_mid_stream_failure_and_cancellation_never_publish_a_partial_destination(tmp_path, monkeypatch):
    store = populated(tmp_path, 3)
    target = tmp_path / "history.csv"
    target.write_bytes(b"Owner export")
    def broken():
        yield store.get_row(3)
        raise OSError("fixture cursor failure")
    with pytest.raises(OSError):
        save_history_export(target, broken(), "csv")
    assert target.read_bytes() == b"Owner export"
    cancelled = threading.Event()
    real_fsync = __import__("os").fsync
    def cancel_at_flush(descriptor):
        real_fsync(descriptor)
        cancelled.set()
    monkeypatch.setattr("saydraft.data.history_view.os.fsync", cancel_at_flush)
    with pytest.raises(HistoryExportCancelled):
        save_history_export(target, store.iter_filtered(), "csv", cancelled=cancelled.is_set)
    assert target.read_bytes() == b"Owner export"
    assert not list(tmp_path.glob(".history.csv.*.tmp"))


@pytest.mark.parametrize("options", [{"limit": 0}, {"limit": 201}, {"offset": -1}, {"ceiling_id": -1}, {"query": "x" * 513}],
    ids=["zero-size", "oversized-page", "offset", "ceiling", "query"])
def test_invalid_query_ranges_are_refused(tmp_path, options):
    with pytest.raises(ValueError):
        populated(tmp_path, 1).search_page(**options)
