"""PySide6 history window."""

from __future__ import annotations

import os
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtWidgets

from saydraft.dictation.glossary import learn_word
from saydraft.history import DictationHistoryStore, HistoryRow
from .private_text import PrivatePlainTextEdit


def add_word_to_dictionary_action(
    selected_text: str,
    *,
    glossary_path: str | os.PathLike[str] = "glossary.json",
) -> str | None:
    term = " ".join((selected_text or "").split())
    if not term:
        return None

    learn_word(glossary_path, term)
    return term


class HistoryWindow(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        qt_modules=None,
        store: DictationHistoryStore | None = None,
        db_path: str | os.PathLike[str] | None = None,
        clipboard: Any | None = None,
        reinsert_callback: Callable[[str, HistoryRow], None] | Callable[[str], None] | None = None,
        retry_callback=None,
        glossary_path: str | os.PathLike[str] = "glossary.json",
        limit: int = 200,
    ):
        super().__init__()
        self.qt = qt_modules
        self.store = store or DictationHistoryStore(db_path)
        if clipboard is None and os.name == "nt":
            from saydraft.insert.clipboard_win import WindowsClipboard
            clipboard = WindowsClipboard()
        self.clipboard = clipboard
        self.reinsert_callback = reinsert_callback
        self.retry_callback = retry_callback
        self._retry_source_id = None
        self.glossary_path = Path(glossary_path)
        self.limit = int(limit)
        self.rows: list[HistoryRow] = []
        self.filtered_rows: list[HistoryRow] = []

        self.setWindowTitle("Saydraft History")
        self.setMinimumSize(860, 560)
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setPlaceholderText("Search history")
        self.list_widget = QtWidgets.QListWidget(self)
        self.detail_editor = PrivatePlainTextEdit(self)
        self.detail_editor.setReadOnly(True)
        self.raw_toggle = QtWidgets.QCheckBox("Show raw transcript", self)
        self.metadata_label = QtWidgets.QLabel("", self)
        self.copy_button = QtWidgets.QPushButton("Copy", self)
        self.restore_clipboard_button = QtWidgets.QPushButton("Restore clipboard", self)
        self.restore_clipboard_button.setVisible(hasattr(self.clipboard, "recover"))
        self.reinsert_button = QtWidgets.QPushButton("Re-insert", self)
        self.add_dictionary_button = QtWidgets.QPushButton("Add Selection to Dictionary", self)
        self.retry_button = QtWidgets.QPushButton("Retry with All languages", self)
        self.retry_button.setToolTip("Recognize saved audio locally and save a new History entry for review.")
        self.retry_button.setEnabled(False)
        self.status_label = QtWidgets.QLabel("", self)

        self._build_layout()
        self._connect_signals()
        self.refresh()

    def _build_layout(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.addWidget(self.search_edit)

        body = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.list_widget)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.metadata_label)
        right_layout.addWidget(self.raw_toggle)
        right_layout.addWidget(self.detail_editor, 1)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.reinsert_button)
        buttons.addWidget(self.add_dictionary_button)
        buttons.addWidget(self.retry_button)
        right_layout.addLayout(buttons)
        recovery = QtWidgets.QHBoxLayout()
        recovery.addWidget(self.status_label, 1)
        recovery.addWidget(self.restore_clipboard_button)
        right_layout.addLayout(recovery)

        body.addWidget(left)
        body.addWidget(right)
        body.setStretchFactor(0, 1)
        body.setStretchFactor(1, 2)
        root.addWidget(body, 1)

    def _connect_signals(self) -> None:
        self.search_edit.textChanged.connect(lambda _text: self.apply_filter())
        self.list_widget.currentRowChanged.connect(lambda _row: self.update_detail())
        self.raw_toggle.toggled.connect(lambda _checked: self.update_detail())
        self.copy_button.clicked.connect(self.copy_current_text)
        self.restore_clipboard_button.clicked.connect(self.restore_clipboard)
        self.reinsert_button.clicked.connect(self.reinsert_current_text)
        self.add_dictionary_button.clicked.connect(self.add_selection_to_dictionary)
        self.retry_button.clicked.connect(self.retry_current_audio)

    def refresh(self) -> None:
        self.restore_clipboard_button.setEnabled(getattr(self.clipboard, "pending", None) is not None)
        selected = self.current_row()
        self.rows = self.store.list_recent(limit=self.limit)
        self.apply_filter()
        if selected is not None:
            self._select_id(selected.id)

    def apply_filter(self) -> None:
        query = self.search_edit.text().strip().lower()
        if query:
            self.filtered_rows = [row for row in self.rows if self._row_matches(row, query)]
        else:
            self.filtered_rows = list(self.rows)

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for row in self.filtered_rows:
            self.list_widget.addItem(self._item_text(row))
        self.list_widget.blockSignals(False)

        if self.filtered_rows:
            self.list_widget.setCurrentRow(0)
        else:
            self.detail_editor.clear()
            self.metadata_label.setText("")
            self.retry_button.setEnabled(False)

    def current_row(self) -> HistoryRow | None:
        index = self.list_widget.currentRow()
        if 0 <= index < len(self.filtered_rows):
            return self.filtered_rows[index]
        return None

    def current_text(self) -> str:
        row = self.current_row()
        if row is None:
            return ""
        return row.raw_text if self.raw_toggle.isChecked() else row.cleaned_text

    def update_detail(self) -> None:
        row = self.current_row()
        if row is None:
            self.detail_editor.clear()
            self.metadata_label.setText("")
            self.retry_button.setEnabled(False)
            return

        self.retry_button.setEnabled(bool(row.audio_path and self.retry_callback and self._retry_source_id is None))

        self.detail_editor.setPlainText(self.current_text())
        self.metadata_label.setText(
            " | ".join(
                part
                for part in (
                    row.created_at,
                    row.app_name or "Unknown app",
                    row.mode,
                    row.profile,
                    row.model,
                    self._duration_text(row),
                    self._retry_origin(row),
                )
                if part
            )
        )

    def _retry_origin(self, row):
        try:
            edits = json.loads(row.edits_json)
        except (TypeError, ValueError):
            return ""
        for item in edits if isinstance(edits, list) else []:
            if isinstance(item, dict) and item.get("type") == "asr_retry":
                source_id = item.get("source_history_id")
                if type(source_id) is int:
                    return f"Retry of #{source_id}"
        return ""

    def _select_id(self, row_id):
        for index, row in enumerate(self.filtered_rows):
            if row.id == row_id:
                self.list_widget.setCurrentRow(index)
                return

    def retry_current_audio(self):
        row = self.current_row()
        if row is None or not row.audio_path or self.retry_callback is None or self._retry_source_id is not None:
            return False
        self._retry_source_id = row.id
        self.retry_button.setEnabled(False)
        self.status_label.setText("Retrying saved audio…")
        if not self.retry_callback(row):
            self._retry_source_id = None
            self.update_detail()
            self.status_label.setText("Finish the current dictation or retry before starting another.")
            return False
        return True

    def finish_retry(self, row_id):
        selected = self.current_row()
        source_selected = selected is not None and selected.id == self._retry_source_id
        self._retry_source_id = None
        self.refresh()
        if row_id and source_selected:
            self.search_edit.clear()
            self._select_id(row_id)
        self.update_detail()
        self.status_label.setText("Retry saved as a new History entry" if row_id else "Retry could not finish; check the notification.")

    def copy_current_text(self) -> bool:
        text = self.current_text()
        if not text:
            return False
        clipboard = self.clipboard or QtWidgets.QApplication.clipboard()
        try:
            clipboard.setText(text)
        except (OSError, ValueError):
            self.status_label.setText("Could not copy. Try again when the clipboard is available.")
            return False
        self.restore_clipboard_button.setEnabled(getattr(self.clipboard, "pending", None) is not None)
        self.status_label.setText("Copied")
        return True

    def restore_clipboard(self) -> bool:
        try:
            restored = bool(self.clipboard and self.clipboard.recover())
        except OSError:
            restored = False
        self.restore_clipboard_button.setEnabled(getattr(self.clipboard, "pending", None) is not None)
        self.status_label.setText("Clipboard ready" if restored else "Could not restore clipboard yet. Try again.")
        return restored

    def reinsert_current_text(self) -> bool:
        row = self.current_row()
        text = self.current_text()
        if row is None or not text or self.reinsert_callback is None:
            return False
        try:
            self.reinsert_callback(text, row)
        except TypeError:
            self.reinsert_callback(text)
        self.status_label.setText("Queued for insertion")
        return True

    def add_selection_to_dictionary(self) -> str | None:
        selected = self.detail_editor.textCursor().selectedText()
        learned = add_word_to_dictionary_action(
            selected,
            glossary_path=self.glossary_path,
        )
        if learned:
            self.status_label.setText(f"Added {learned}")
        else:
            self.status_label.setText("Select text first")
        return learned

    def _row_matches(self, row: HistoryRow, query: str) -> bool:
        haystack = " ".join(
            str(value or "")
            for value in (
                row.app_name,
                row.raw_text,
                row.cleaned_text,
                row.mode,
                row.profile,
                row.model,
            )
        ).lower()
        return query in haystack

    def _item_text(self, row: HistoryRow) -> str:
        preview = " ".join(row.cleaned_text.split())
        if not preview and row.audio_path:
            preview = "Recording saved for recognition retry"
        if len(preview) > 80:
            preview = preview[:77] + "..."
        app = row.app_name or "Unknown"
        return f"{preview}  [{app}]"

    def _duration_text(self, row: HistoryRow) -> str:
        if row.duration_seconds is None:
            return ""
        return f"{row.duration_seconds:.1f}s"
