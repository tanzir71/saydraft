import csv
import threading
import time
from types import SimpleNamespace

import pytest

from saydraft.history import HistoryEntry, HistorySnapshot
from tests.test_history_window import FakeClipboard, qt_modules, settle_history
from tests.test_history_queries import populated


def until(condition, timeout=8):
    application = qt_modules().QtWidgets.QApplication.instance()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if condition():
            return
        time.sleep(.003)
    raise AssertionError("Owned History condition did not finish")


@pytest.fixture
def subject(tmp_path):
    from saydraft.ui.history_page import HistoryPage
    qt = qt_modules()
    store, clipboard = populated(tmp_path), FakeClipboard()
    window = HistoryPage(store=store, clipboard=clipboard, limit=25)
    settle_history(window)
    try:
        yield SimpleNamespace(window=window, store=store, clipboard=clipboard, qt=qt, path=tmp_path)
    finally:
        window.close()
        window.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def test_paging_global_search_and_external_selection_reach_the_oldest_record(subject):
    w = subject.window
    assert w.list_widget.count() == 25 and w.current_row().id == 451
    assert w.page_label.text() == "1–25 of 451" and not w.newer_button.isEnabled()
    w.older_button.click()
    settle_history(w)
    assert w.current_row().id == 426 and w.page_label.text() == "26–50 of 451"
    w.newer_button.click()
    settle_history(w)
    assert w.current_row().id == 451
    w.search_edit.setText("STRASSE")
    assert w.loading and not w.copy_button.isEnabled() and not w.copy_current_text()
    settle_history(w)
    assert w.current_row().id == 1 and w.list_widget.count() == 1
    w.search_edit.clear()
    w._select_id(1)
    settle_history(w)
    assert w.current_row().id == 1 and w._page.offset == 450 and not w.older_button.isEnabled()


def test_refresh_keeps_older_selection_and_paging_snapshot_excludes_new_entries(subject):
    w = subject.window
    w._select_id(200)
    settle_history(w)
    subject.store.append(HistoryEntry("Live", "new", "Newest live", "raw", "notes", 1, "fixture"))
    w.newer_button.click()
    settle_history(w)
    assert w._page.total == 451
    w._select_id(200)
    settle_history(w)
    w.refresh()
    settle_history(w)
    assert w.current_row().id == 200 and w._page.total == 452
    w.latest_button.click()
    settle_history(w)
    assert w.current_row().id == 452 and w._page.offset == 0


def test_late_search_result_cannot_replace_new_query_and_gui_remains_responsive(subject, monkeypatch):
    w = subject.window
    entered, release, threads, ticks = threading.Event(), threading.Event(), [], []
    original = HistorySnapshot.search_page
    def controlled(view, **options):
        threads.append(threading.get_ident())
        if options["query"] == "slow":
            entered.set()
            assert release.wait(5)
            return original(view, query="STRASSE")
        return original(view, **options)
    monkeypatch.setattr(HistorySnapshot, "search_page", controlled)
    try:
        w.search_edit.setText("slow")
        until(entered.is_set)
        subject.qt.QtCore.QTimer.singleShot(0, lambda: ticks.append("GUI alive"))
        w.search_edit.setText("unique-model")
        until(lambda: bool(ticks) and not w.search_timer.isActive())
        assert w.loading and not w.copy_current_text() and not subject.clipboard.texts
        release.set()
        settle_history(w)
        assert w.current_row().id == 3 and w._page.query == "unique-model"
        assert len(set(threads)) == 1 and threads[0] != threading.get_ident()
    finally:
        release.set()


def test_outdated_detail_cannot_be_copied_after_another_selection(subject, monkeypatch):
    w = subject.window
    entered, release, gui_threads = threading.Event(), threading.Event(), []
    original = HistorySnapshot.get_row
    def controlled(view, row_id, **options):
        if row_id == 450:
            entered.set()
            assert release.wait(5)
            return original(view, row_id)
        return original(view, row_id, **options)
    monkeypatch.setattr(HistorySnapshot, "get_row", controlled)
    w.detail_editor.textChanged.connect(lambda: gui_threads.append(threading.get_ident()))
    try:
        w.list_widget.setCurrentRow(1)
        until(entered.is_set)
        w.list_widget.setCurrentRow(2)
        assert not w.copy_current_text()
        release.set()
        settle_history(w)
        assert w.current_row().id == 449 and w.copy_current_text()
        assert subject.clipboard.texts == ["Public result 449"]
        assert gui_threads and set(gui_threads) == {threading.get_ident()}
    finally:
        release.set()


def test_export_includes_every_match_not_just_current_page_and_retains_the_displayed_snapshot(subject):
    w = subject.window
    w.older_button.click()
    settle_history(w)
    subject.store.append(HistoryEntry("Live", "new", "New after browsing", "raw", "notes", 1, "fixture"))
    target = subject.path / "all.csv"
    assert w.export_to(target, format="csv")
    settle_history(w)
    with target.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 451 and len(w.rows) == 25
    assert rows[0]["id"] == "451" and rows[-1]["id"] == "1"
    assert w.status_label.text() == "Exported 451 entries"


def test_export_cancellation_preserves_destination_and_does_not_block_new_snapshot_queries(subject, monkeypatch):
    from saydraft.data.history_view import save_history_export
    w = subject.window
    entered, release = threading.Event(), threading.Event()
    target = subject.path / "existing.csv"
    target.write_bytes(b"Owner destination")
    old_path = w._snapshot.db_path
    def controlled(*args, **options):
        entered.set()
        assert release.wait(5)
        return save_history_export(*args, **options)
    monkeypatch.setattr("saydraft.ui.history_jobs.save_history_export", controlled)
    try:
        assert w.export_to(target, format="csv")
        until(entered.is_set)
        w.refresh()
        until(lambda: not w.loading)
        assert w._snapshot.db_path != old_path and old_path.is_file()
        assert w._exporting and not w.export_button.isEnabled()
        w.cancel_export_button.click()
        release.set()
        settle_history(w)
        assert target.read_bytes() == b"Owner destination" and w.status_label.text() == "Export cancelled"
        until(lambda: not old_path.exists())
        assert not list(subject.path.glob(".existing.csv.*.tmp"))
    finally:
        release.set()


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"], ids=["database", "wal", "shm", "journal"])
def test_export_cannot_overwrite_the_live_database_or_its_sidecars(subject, suffix):
    w = subject.window
    original = subject.store.db_path.read_bytes()
    target = subject.store.db_path.with_name(subject.store.db_path.name + suffix)
    existed = target.exists()
    assert w.export_to(target, format="csv")
    settle_history(w)
    assert "Could not export" in w.status_label.text()
    assert subject.store.db_path.read_bytes() == original and target.exists() == existed
    assert subject.store.search_page().total == 451


def test_failed_search_clears_prior_results_and_cannot_export_the_old_filter(subject, monkeypatch):
    w = subject.window
    def unavailable(*args, **kwargs):
        raise OSError("fixture denied")
    monkeypatch.setattr(HistorySnapshot, "search_page", unavailable)
    w.search_edit.setText("new filter")
    settle_history(w)
    assert not w.detail_editor.toPlainText() and not w.list_widget.count()
    assert not w.export_button.isEnabled() and not w.export_to(subject.path / "wrong.csv", format="csv")
    assert not (subject.path / "wrong.csv").exists()


def test_close_retires_inflight_work_and_refuses_new_admissions(subject, monkeypatch):
    w = subject.window
    entered, finished = threading.Event(), threading.Event()
    def cooperative(view, **options):
        entered.set()
        deadline = time.monotonic() + 5
        while not options["cancelled"]() and time.monotonic() < deadline:
            time.sleep(.003)
        finished.set()
        raise InterruptedError("cancelled owned task")
    monkeypatch.setattr(HistorySnapshot, "search_page", cooperative)
    w.search_edit.setText("cancel on close")
    until(entered.is_set)
    w.close()
    until(finished.is_set)
    assert w.jobs.closed and not w.jobs.page(999, fresh=True, query="")
