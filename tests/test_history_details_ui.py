import csv
import io

import pytest

from saydraft.history import HistoryEntry
from tests.test_history_window import FakeClipboard, build_history, qt_modules


@pytest.fixture
def subject(tmp_path):
    from saydraft.ui.history_window import HistoryWindow

    qt = qt_modules()
    store = build_history(tmp_path)
    store.append(HistoryEntry("<a href='https://invalid.test'>Public fixture</a>", "um keep café", "keep café.",
        "balanced", "notes", 2, "Parakeet", llm_model="Qwen", llm_decision="rules_budget",
        timings_json='{"stt":0.2,"rules":0.001}'))
    clipboard, inserted = FakeClipboard(), []
    window = HistoryWindow(store=store, clipboard=clipboard, reinsert_callback=lambda text, row: inserted.append(text))
    try:
        yield window, qt, clipboard, inserted
    finally:
        window.close()
        window.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def test_diff_formats_plain_text_but_copy_and_paste_use_the_cleaned_result(subject):
    window, qt, clipboard, inserted = subject
    row = window.current_row()
    window.diff_toggle.setChecked(True)
    assert not window.raw_toggle.isChecked()
    fragments = []
    block = window.detail_editor.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            fragments.append((fragment.text(), fragment.charFormat()))
            iterator += 1
        block = block.next()
    assert any("um" in text and style.fontStrikeOut() for text, style in fragments)
    assert any("café." in text and style.fontUnderline() and
        style.background().color().name().lower() == window.diff_colors["insertBackground"].lower()
        for text, style in fragments)
    assert window.copy_current_text() and clipboard.texts == [row.cleaned_text]
    assert window.reinsert_current_text() and inserted == [row.cleaned_text]
    assert window.copy_button.text() == "Copy cleaned"
    window.raw_toggle.setChecked(True)
    assert not window.diff_toggle.isChecked() and window.detail_editor.toPlainText() == row.raw_text
    assert window.copy_current_text() and clipboard.texts[-1] == row.raw_text
    assert window.metadata_label.textFormat() == qt.QtCore.Qt.PlainText


def test_diff_selection_mime_keeps_windows_clipboard_privacy_markers(subject):
    from saydraft.insert._clipboard_win32 import PRIVACY_FORMATS

    window, qt, _, _ = subject
    window.diff_toggle.setChecked(True)
    cursor = window.detail_editor.textCursor()
    cursor.select(qt.QtGui.QTextCursor.Document)
    window.detail_editor.setTextCursor(cursor)
    data = window.detail_editor.createMimeDataFromSelection()
    for name in PRIVACY_FORMATS:
        format = f'application/x-qt-windows-mime;value="{name}"'
        assert data.hasFormat(format) and bytes(data.data(format)) == bytes(4)


def test_result_details_and_empty_filter_never_leave_stale_text(subject):
    window, _, _, _ = subject
    window.why_button.setChecked(True)
    assert not window.why_editor.isHidden()
    text = window.why_editor.toPlainText()
    assert "Qwen" in text and "rules_budget" in text and "0.001" in text
    window.search_edit.setText("there are no matching records")
    assert not window.export_button.isEnabled()
    assert not window.detail_editor.toPlainText() and not window.why_editor.toPlainText()


@pytest.mark.parametrize("format", ["md", "csv"])
def test_export_uses_only_filtered_rows_and_ignores_the_raw_diff_view(subject, tmp_path, format):
    window, _, _, _ = subject
    window.search_edit.setText("older")
    window.diff_toggle.setChecked(True)
    path = tmp_path / ("export." + format)
    assert window.export_to(path, format=format)
    text = path.read_text("utf-8")
    assert "Older clean." in text and "um older raw" in text
    assert "Newer clean" not in text and "keep café" not in text
    assert window.status_label.text() == "Exported 1 entries"
    if format == "csv":
        assert len(list(csv.DictReader(io.StringIO(text)))) == 1


def test_export_dialog_cancel_is_a_noop_and_missing_directory_is_visible(subject, tmp_path, monkeypatch):
    window, qt, _, _ = subject
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    previous = window.status_label.text()
    assert not window.choose_export() and window.status_label.text() == previous
    assert not window.export_to(tmp_path / "missing" / "history.md", format="md")
    assert "Could not export" in window.status_label.text()


def test_export_dialog_appends_the_selected_format_suffix(subject, tmp_path, monkeypatch):
    window, qt, _, _ = subject
    path = tmp_path / "chosen"
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(path), "CSV (*.csv)"))
    assert window.choose_export()
    assert path.with_suffix(".csv").is_file() and not path.exists()


def test_explicit_csv_filename_is_respected_even_with_the_markdown_filter(subject, tmp_path, monkeypatch):
    window, qt, _, _ = subject
    path = tmp_path / "chosen.csv"
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(path), "Markdown (*.md)"))
    assert window.choose_export()
    parsed = list(csv.DictReader(io.StringIO(path.read_text("utf-8"))))
    assert len(parsed) == len(window.filtered_rows)
