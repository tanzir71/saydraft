import csv
import io
from pathlib import Path

import pytest

from saydraft.history import HistoryEntry
from tests.test_history_window import FakeClipboard, build_history, qt_modules, settle_history


@pytest.mark.parametrize('mode', ['translate', 'translation_failed'])
def test_spoken_translation_history_keeps_copy_labels_and_blocks_ordinary_audio_retry(subject, mode):
    window, qt, clipboard, inserted = subject
    target = 'El archivo está listo.' if mode == 'translate' else 'The file is ready.'
    identifier = window.store.append(HistoryEntry('Owned editor', 'The file is ready.', target, mode,
        'general', 1, 'fixture-asr', audio_path='owned.wav', language='en',
        edits_json='[{"type":"translation","target_language":"es"}]'))
    window.refresh()
    settle_history(window)
    window._select_id(identifier)
    settle_history(window)
    assert not window.retry_button.isEnabled() and not window.choose_retry() and not window.retry_current_audio()
    assert window.copy_current_text() and clipboard.texts[-1] == target
    if mode == 'translate':
        assert window.copy_button.text() == 'Copy translation' and window.reinsert_button.text() == 'Paste translation'
        assert window.reinsert_current_text() and inserted == [target]
    else:
        assert window.copy_button.text() == 'Copy recognized speech' and not window.reinsert_button.isEnabled()
        assert not window.reinsert_current_text() and not inserted
        assert not window.raw_toggle.isEnabled() and not window.diff_toggle.isEnabled()


@pytest.fixture
def subject(tmp_path):
    from saydraft.ui.history_page import HistoryPage

    qt = qt_modules()
    store = build_history(tmp_path)
    store.append(HistoryEntry("<a href='https://invalid.test'>Public fixture</a>", "um keep café", "keep café.",
        "balanced", "notes", 2, "Parakeet", llm_model="Qwen", llm_decision="rules_budget",
        timings_json='{"stt":0.2,"rules":0.001}'))
    clipboard, inserted = FakeClipboard(), []
    window = HistoryPage(store=store, clipboard=clipboard, reinsert_callback=lambda text, row: inserted.append(text))
    settle_history(window)
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


def test_failed_command_instruction_is_visible_and_copyable_without_dictation_retry_or_reinsert(subject):
    window, qt, clipboard, inserted = subject
    text = 'Make this shorter. العربية বাংলা <b>literal</b>'
    identifier = window.store.append(HistoryEntry('Public editor', text, '', 'command', 'command', 1,
        'fixture-asr', llm_model='fixture-edit', llm_decision='edit_failed:unavailable',
        edits_json='[{"type":"command_instruction","reason":"unavailable"}]', audio_path='public-fixture.wav'))
    window.refresh()
    settle_history(window)
    window._select_id(identifier)
    settle_history(window)
    assert window.current_row().id == identifier and window.detail_editor.toPlainText() == text
    assert window.copy_button.text() == 'Copy instruction' and 'Recognized instruction' in window.why_editor.toPlainText()
    assert not window.reinsert_button.isEnabled() and not window.retry_button.isEnabled()
    assert not window.choose_retry() and not window.retry_current_audio() and not window.reinsert_current_text()
    assert not inserted and window.copy_current_text() and clipboard.texts == [text]
    normal_id = window.store.append(HistoryEntry('Public editor', 'normal words', 'Normal words.', 'balanced', 'notes', 1, 'fixture-asr'))
    window.refresh()
    settle_history(window)
    window._select_id(normal_id)
    settle_history(window)
    assert window.raw_toggle.isEnabled() and window.diff_toggle.isEnabled() and window.reinsert_button.isEnabled()


def test_successful_command_provenance_is_visible_and_survives_both_export_formats(subject):
    from saydraft.data.history_view import export_history
    window, qt, clipboard, inserted = subject
    instruction = 'Make it shorter.'
    identifier = window.store.append(HistoryEntry('Public editor', 'I wanted to say the file arrived.', 'The file arrived.',
        'command', 'command', 1, 'fixture-asr', llm_model='fixture-edit', llm_decision='edit_validated',
        edits_json='[{"type":"command_edit","instruction":"Make it shorter."}]'))
    window.refresh()
    settle_history(window)
    window._select_id(identifier)
    settle_history(window)
    row = window.current_row()
    assert instruction in window.why_editor.toPlainText() and 'Edit model: fixture-edit' in window.why_editor.toPlainText()
    assert instruction in export_history([row], 'md')
    exported = list(csv.DictReader(io.StringIO(export_history([row], 'csv'))))
    assert instruction in exported[0]['edits_json']
    assert window.copy_current_text() and clipboard.texts == [row.cleaned_text]
    assert not window.reinsert_current_text() and not inserted


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
    settle_history(window)
    assert not window.export_button.isEnabled()
    assert not window.detail_editor.toPlainText() and not window.why_editor.toPlainText()


@pytest.mark.parametrize("format", ["md", "csv"])
def test_export_uses_only_filtered_rows_and_ignores_the_raw_diff_view(subject, tmp_path, format):
    window, _, _, _ = subject
    window.search_edit.setText("older")
    settle_history(window)
    window.diff_toggle.setChecked(True)
    path = tmp_path / ("export." + format)
    assert window.export_to(path, format=format)
    settle_history(window)
    text = path.read_text("utf-8")
    assert "Older clean." in text and "um older raw" in text
    assert "Newer clean" not in text and "keep café" not in text
    assert window.status_label.text() == "Exported 1 entries"
    if format == "csv":
        assert len(list(csv.DictReader(io.StringIO(text)))) == 1


def test_export_dialog_cancel_is_a_noop_and_missing_directory_is_visible(subject, tmp_path, monkeypatch):
    window, qt, _, _ = subject
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "exec", lambda dialog: qt.QtWidgets.QDialog.Rejected)
    previous = window.status_label.text()
    assert not window.choose_export() and window.status_label.text() == previous
    assert window.export_to(tmp_path / "missing" / "history.md", format="md")
    settle_history(window)
    assert "Could not export" in window.status_label.text()


def test_export_dialog_appends_the_selected_format_suffix(subject, tmp_path, monkeypatch):
    window, qt, _, _ = subject
    path = tmp_path / "chosen"

    def choose(dialog):
        assert dialog.acceptMode() == qt.QtWidgets.QFileDialog.AcceptSave
        assert not dialog.testOption(qt.QtWidgets.QFileDialog.DontConfirmOverwrite)
        assert dialog.defaultSuffix() == "md"
        dialog.selectNameFilter("CSV (*.csv)")
        dialog.filterSelected.emit("CSV (*.csv)")
        dialog.selectFile(str(path))
        assert dialog.defaultSuffix() == "csv"
        assert [Path(value) for value in dialog.selectedFiles()] == [path.with_suffix(".csv")]
        return qt.QtWidgets.QDialog.Accepted

    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "exec", choose)
    assert window.choose_export()
    settle_history(window)
    assert path.with_suffix(".csv").is_file() and not path.exists()


def test_explicit_csv_filename_is_respected_even_with_the_markdown_filter(subject, tmp_path, monkeypatch):
    window, qt, _, _ = subject
    path = tmp_path / "chosen.csv"

    def choose(dialog):
        dialog.selectFile(str(path))
        return qt.QtWidgets.QDialog.Accepted

    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "exec", choose)
    assert window.choose_export()
    settle_history(window)
    parsed = list(csv.DictReader(io.StringIO(path.read_text("utf-8"))))
    assert len(parsed) == len(window.filtered_rows)


def test_export_never_appends_a_suffix_after_the_dialog_confirms_a_target(subject, tmp_path, monkeypatch):
    window, qt, _, _ = subject
    selected = tmp_path / "explicit-target"
    sibling = selected.with_suffix(".md")
    sibling.write_text("existing sibling", encoding="utf-8")
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "exec", lambda dialog: qt.QtWidgets.QDialog.Accepted)
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "selectedFiles", lambda dialog: [str(selected)])
    assert window.choose_export()
    settle_history(window)
    assert selected.is_file() and sibling.read_text("utf-8") == "existing sibling"


def test_export_dialog_keeps_its_original_query_when_background_work_changes_the_display(subject, tmp_path, monkeypatch):
    window, qt, _, _ = subject
    window.search_edit.setText("older")
    settle_history(window)
    target = tmp_path / "frozen.csv"
    def choose(dialog):
        window.search_edit.setText("newer")
        settle_history(window)
        dialog.selectFile(str(target))
        return qt.QtWidgets.QDialog.Accepted
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "exec", choose)
    assert window.choose_export()
    settle_history(window)
    with target.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1 and rows[0]["cleaned_text"] == "Older clean."
    assert window.current_row().cleaned_text == "Newer clean Qwen Turbo."
