"""Private History review controls hosted by the Saydraft Hub."""

from __future__ import annotations

import os
import json
from importlib.resources import files
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.dictation.glossary import learn_word
from saydraft.history import DictationHistoryStore, HistoryRow, HistorySummary
from saydraft.data.history_view import result_details, timestamp_label, transcript_diff
from .private_text import PrivatePlainTextEdit
from .history_jobs import HistoryJobs


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


class HistoryPage(QtWidgets.QWidget):
    def __init__(
        self,
        *,
        qt_modules=None,
        store: DictationHistoryStore | None = None,
        db_path: str | os.PathLike[str] | None = None,
        clipboard: Any | None = None,
        reinsert_callback: Callable[[str, HistoryRow], None] | Callable[[str], None] | None = None,
        retry_callback=None,
        cancel_retry_callback=None,
        retry_models_provider=None,
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
        self.cancel_retry_callback = cancel_retry_callback
        self.retry_models_provider = retry_models_provider
        self._retry_source_id = None
        self._retry_cancel_requested = False
        self._retry_follow_source = False
        self.glossary_path = Path(glossary_path)
        self.limit = max(1, min(200, int(limit)))
        self._page = self._snapshot = self._detail = None
        self._requested_selected_id = None
        self._loading, self._detail_loading, self._exporting = False, False, False
        self._generation = self._export_generation = 0
        self.diff_colors = json.loads(files("saydraft.ui.theme").joinpath("metadata.json").read_text("utf-8"))["history"]
        self.rows: list[HistorySummary] = []
        self.filtered_rows: list[HistorySummary] = []

        self.setAccessibleName("Saydraft History")
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setPlaceholderText("Search all History")
        self.search_edit.setAccessibleName("Search all History")
        self.search_edit.setToolTip("Search saved text, apps, languages, styles and models.")
        self.search_edit.setMaxLength(512)
        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setWordWrap(True)
        self.list_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.detail_editor = PrivatePlainTextEdit(self)
        self.detail_editor.setReadOnly(True)
        self.raw_toggle = QtWidgets.QCheckBox("Show raw transcript", self)
        self.diff_toggle = QtWidgets.QCheckBox("Show changes", self)
        self.diff_toggle.setToolTip("Inserted text is highlighted; removed text is struck through.")
        self.metadata_label = QtWidgets.QLabel("", self)
        self.metadata_label.setTextFormat(QtCore.Qt.PlainText)
        self.metadata_label.setWordWrap(True)
        self.why_button = QtWidgets.QPushButton("Why this result?", self)
        self.why_button.setCheckable(True)
        self.why_editor = PrivatePlainTextEdit(self)
        self.why_editor.setAccessibleName("Models, cleanup decision and timings")
        self.why_editor.setReadOnly(True)
        self.why_editor.setMaximumHeight(140)
        self.why_editor.hide()
        self.export_button = QtWidgets.QPushButton("Export…", self)
        self.export_button.setToolTip("Export all results matching this search as Markdown or CSV.")
        self.cancel_export_button = QtWidgets.QPushButton("Cancel export", self)
        self.cancel_export_button.hide()
        self.newer_button, self.older_button, self.latest_button = [QtWidgets.QPushButton(text, self)
            for text in ("Newer", "Older", "Refresh")]
        self.page_label = QtWidgets.QLabel("", self)
        self.page_label.setWordWrap(True)
        self.page_label.setTextFormat(QtCore.Qt.PlainText)
        self.copy_button = QtWidgets.QPushButton("Copy", self)
        self.restore_clipboard_button = QtWidgets.QPushButton("Restore clipboard", self)
        self.restore_clipboard_button.setVisible(hasattr(self.clipboard, "recover"))
        self.reinsert_button = QtWidgets.QPushButton("Re-insert", self)
        self.add_dictionary_button = QtWidgets.QPushButton("Add word", self)
        self.add_dictionary_button.setAccessibleName("Add selected text to Dictionary")
        self.retry_button = QtWidgets.QPushButton("Retry audio…", self)
        self.retry_button.setToolTip("Choose an installed speech model and AI cleanup on/off; save a new History entry for review.")
        self.retry_button.setEnabled(False)
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setTextFormat(QtCore.Qt.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.search_timer = QtCore.QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(lambda: self._load_page())
        self.jobs = HistoryJobs(self.store, self)
        self.jobs.ready.connect(self._accept_read, QtCore.Qt.QueuedConnection)
        self.jobs.exported.connect(self._accept_export, QtCore.Qt.QueuedConnection)

        self._build_layout()
        self._connect_signals()
        self.refresh()

    def _build_layout(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(self.search_edit, 1)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(self.cancel_export_button)
        root.addLayout(toolbar)

        body = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.list_widget)
        paging = QtWidgets.QHBoxLayout()
        paging.addWidget(self.newer_button)
        paging.addWidget(self.older_button)
        left_layout.addLayout(paging)
        left_layout.addWidget(self.page_label)
        left_layout.addWidget(self.latest_button)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.metadata_label)
        views = QtWidgets.QHBoxLayout()
        views.addWidget(self.raw_toggle)
        views.addWidget(self.diff_toggle)
        views.addStretch()
        right_layout.addLayout(views)
        right_layout.addWidget(self.detail_editor, 1)
        right_layout.addWidget(self.why_button)
        right_layout.addWidget(self.why_editor)
        buttons = QtWidgets.QGridLayout()
        for index, button in enumerate((self.copy_button, self.reinsert_button, self.add_dictionary_button, self.retry_button)):
            buttons.addWidget(button, index // 2, index % 2)
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
        self.list_widget.currentRowChanged.connect(self._selection_changed)
        self.newer_button.clicked.connect(lambda: self._turn_page(-1))
        self.older_button.clicked.connect(lambda: self._turn_page(1))
        self.latest_button.clicked.connect(lambda: self._load_page(fresh=True))
        self.cancel_export_button.clicked.connect(self._cancel_export)
        self.raw_toggle.toggled.connect(lambda checked: self._set_text_view("raw", checked))
        self.diff_toggle.toggled.connect(lambda checked: self._set_text_view("diff", checked))
        self.why_button.toggled.connect(self.why_editor.setVisible)
        self.export_button.clicked.connect(self.choose_export)
        self.copy_button.clicked.connect(self.copy_current_text)
        self.restore_clipboard_button.clicked.connect(self.restore_clipboard)
        self.reinsert_button.clicked.connect(self.reinsert_current_text)
        self.add_dictionary_button.clicked.connect(self.add_selection_to_dictionary)
        self.retry_button.clicked.connect(self.choose_retry)

    def refresh(self) -> None:
        self.restore_clipboard_button.setEnabled(getattr(self.clipboard, "pending", None) is not None)
        selected = self._selected_id()
        if selected is None and self.loading:
            selected = self._requested_selected_id
        self._load_page(fresh=True, selected_id=selected, offset=self._page.offset if self._page else 0)

    def apply_filter(self) -> None:
        self._retry_follow_source = False
        self._requested_selected_id = None
        self._generation += 1
        self.jobs.cancel_read()
        self._clear_for_read()
        self.search_timer.start()

    def show_last_diff(self):
        """Select the latest global entry, independent of the current search/page."""
        self._retry_follow_source = False
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self.diff_toggle.setChecked(True)
        self._load_page(fresh=True, offset=0, selected_id=None)

    @property
    def loading(self):
        return self._loading or self._detail_loading or self.search_timer.isActive()

    def _clear_for_read(self):
        self._loading, self._detail_loading, self._detail = True, False, None
        self.rows = self.filtered_rows = []
        self.list_widget.clear()
        self.page_label.setText("Loading History…")
        self.newer_button.setEnabled(False)
        self.older_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.update_detail()

    def _load_page(self, *, fresh=False, offset=0, selected_id=None):
        self._requested_selected_id = selected_id
        self.search_timer.stop()
        self._generation += 1
        self._clear_for_read()
        if fresh:
            self._snapshot = None
        if not self.jobs.page(self._generation, fresh=fresh, query=self.search_edit.text(),
                offset=offset, limit=self.limit, selected_id=selected_id):
            self._accept_read(self._generation, None)

    def _turn_page(self, direction):
        if self.loading or self._page is None:
            return False
        self._load_page(offset=max(0, self._page.offset + direction * self.limit))
        return True

    @QtCore.Slot(int, object)
    def _accept_read(self, generation, payload):
        if generation != self._generation or self.jobs.closed:
            return
        page_failed = self._loading
        self._loading = self._detail_loading = False
        if payload is None:
            self._detail = None
            if page_failed:
                self._page = self._snapshot = None
                self.rows = self.filtered_rows = []
                self.list_widget.clear()
                self.export_button.setEnabled(False)
                self.newer_button.setEnabled(False)
                self.older_button.setEnabled(False)
                self.page_label.setText("History unavailable")
            self.status_label.setText("Could not read History. Try Refresh." if page_failed else "Could not load this entry. Try Refresh.")
            self.update_detail()
            return
        kind, result, view = payload
        if kind == "detail":
            self._detail = result
            self.update_detail()
            return
        self._page, self._snapshot, self._detail = result, view, result.selected
        if self._retry_source_id is not None and result.selected is not None and result.selected.id != self._retry_source_id:
            self._retry_follow_source = False
        self.rows = self.filtered_rows = list(result.rows)
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for row in self.filtered_rows:
            self.list_widget.addItem(self._item_text(row))
        if result.selected is not None:
            self.list_widget.setCurrentRow(next(i for i, row in enumerate(self.rows) if row.id == result.selected.id))
        self.list_widget.blockSignals(False)
        self.newer_button.setEnabled(result.offset > 0)
        self.older_button.setEnabled(result.offset + len(result.rows) < result.total)
        self.page_label.setText(f"{result.offset + 1}–{result.offset + len(result.rows)} of {result.total}" if result.rows else
            "No matching entries" if result.query else "No dictations yet")
        self.export_button.setEnabled(bool(result.total) and not self._exporting)
        self.update_detail()

    def _selected_id(self):
        index = self.list_widget.currentRow()
        return self.rows[index].id if 0 <= index < len(self.rows) else None

    def _selection_changed(self, _index):
        row_id = self._selected_id()
        if row_id is not None and not self._loading and self._retry_source_id is not None:
            self._retry_follow_source = row_id == self._retry_source_id
        if row_id is None or self._loading or self._snapshot is None:
            self.update_detail()
            return
        self._generation += 1
        self._detail, self._detail_loading = None, True
        self.update_detail()
        if not self.jobs.detail(self._generation, self._snapshot, row_id):
            self._accept_read(self._generation, None)

    def current_row(self) -> HistoryRow | None:
        return self._detail if not self.loading and self._detail is not None and self._detail.id == self._selected_id() else None

    def current_text(self) -> str:
        row = self.current_row()
        if row is None:
            return ""
        return row.raw_text if self.raw_toggle.isChecked() or row.mode == 'command' and not row.cleaned_text else row.cleaned_text

    def update_detail(self) -> None:
        row = self.current_row()
        retrying = self._retry_source_id is not None
        self.retry_button.setText("Cancel retry" if retrying else "Retry audio…")
        self.retry_button.setToolTip("Cancel after the current recognition step; an already saved result stays in History."
            if retrying else "Choose an installed speech model and AI cleanup on/off; save a new History entry for review.")
        self.retry_button.setEnabled(bool(self.cancel_retry_callback and not self._retry_cancel_requested)
            if retrying else bool(row and row.mode not in ('command', 'ask', 'translate', 'translation_failed') and row.audio_path and self.retry_callback))
        for button in (self.copy_button, self.reinsert_button, self.add_dictionary_button):
            button.setEnabled(row is not None)
        if row is None:
            self.detail_editor.clear()
            self.metadata_label.setText("")
            self.why_editor.clear()
            return

        command = row.mode == 'command'
        ask = row.mode == 'ask'
        instruction = command and not row.cleaned_text
        self.raw_toggle.setText('Show question' if ask else 'Recognized instruction' if instruction else 'Show original selection' if command else 'Show raw transcript')
        self.raw_toggle.setEnabled(not instruction)
        self.diff_toggle.setEnabled(not instruction and not ask)
        if row.mode == 'translation_failed':
            self.raw_toggle.setEnabled(False)
            self.diff_toggle.setEnabled(False)
        self.reinsert_button.setEnabled(not command and not ask)
        if row.mode in ('translate', 'translation_failed'):
            self.retry_button.setToolTip('Ordinary audio retry does not translate. Start a new Translate dictation with the saved Style target.')
        if command:
            self.retry_button.setToolTip('Command audio cannot be retried as dictation. Hold Command again to speak a new instruction.')
        self.why_editor.setPlainText(result_details(row))
        self.copy_button.setText('Copy instruction' if instruction else "Copy raw" if self.raw_toggle.isChecked() else "Copy cleaned")
        self.reinsert_button.setText("Paste raw" if self.raw_toggle.isChecked() else "Paste cleaned")
        self.reinsert_button.setAccessibleName("Paste raw again" if self.raw_toggle.isChecked() else "Paste cleaned again")
        if row.mode == 'translate' and not self.raw_toggle.isChecked():
            self.copy_button.setText('Copy translation')
            self.reinsert_button.setText('Paste translation')
            self.reinsert_button.setAccessibleName('Paste translation again')
        if row.mode == 'translation_failed':
            self.copy_button.setText('Copy recognized speech')
            self.reinsert_button.setEnabled(False)
        if ask:
            self.copy_button.setText('Copy question' if self.raw_toggle.isChecked() else 'Copy answer')
            self.retry_button.setToolTip('Ask uses reviewed text, not a recording. Open Ask to send a new question.')
        if self.diff_toggle.isChecked() and not instruction and not ask:
            self._show_diff(row)
        else:
            self.detail_editor.setPlainText(self.current_text())
        self.metadata_label.setText(
            " | ".join(
                part
                for part in (
                    row.app_name or "Unknown app",
                    timestamp_label(row.created_at),
                    self._duration_text(row),
                    self._retry_origin(row),
                )
                if part
            )
        )

    def _set_text_view(self, view, checked):
        other = self.raw_toggle if view == "diff" else self.diff_toggle
        if checked:
            other.blockSignals(True)
            other.setChecked(False)
            other.blockSignals(False)
        self.update_detail()

    def _show_diff(self, row):
        runs = transcript_diff(row.raw_text, row.cleaned_text)
        self.detail_editor.clear()
        cursor = self.detail_editor.textCursor()
        cursor.beginEditBlock()
        previous = None
        for run in runs:
            if (previous is not None and previous.kind != "equal" and run.kind != "equal"
                    and previous.kind != run.kind and not previous.text[-1:].isspace() and not run.text[:1].isspace()):
                cursor.insertText("\u2009", QtGui.QTextCharFormat())
            style = QtGui.QTextCharFormat()
            if run.kind == "delete":
                style.setFontStrikeOut(True)
            elif run.kind == "insert":
                style.setBackground(QtGui.QColor(self.diff_colors["insertBackground"]))
                style.setForeground(QtGui.QColor(self.diff_colors["insertText"]))
                style.setFontUnderline(True)
            cursor.insertText(run.text, style)
            previous = run
        cursor.endEditBlock()
        cursor.movePosition(QtGui.QTextCursor.Start)
        self.detail_editor.setTextCursor(cursor)

    def choose_export(self):
        if self._loading or self.search_timer.isActive() or self._page is None or self._snapshot is None or self._exporting:
            return False
        # A nested native dialog can dispatch background refresh signals. Keep
        # the exact filter/view the user chose to export when opening it.
        page, view = self._page, self._snapshot
        dialog = QtWidgets.QFileDialog(self, "Export filtered history")
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        dialog.setNameFilters(["Markdown (*.md)", "CSV (*.csv)"])
        dialog.setSupportedSchemes(["file"])
        dialog.setDefaultSuffix("md")
        dialog.selectFile("saydraft-history")
        dialog.filterSelected.connect(lambda selected: dialog.setDefaultSuffix("csv" if selected.startswith("CSV") else "md"))
        try:
            if dialog.exec() != QtWidgets.QDialog.Accepted or not dialog.selectedFiles():
                return False
            # Qt applies the suffix before its native overwrite confirmation.
            # Never change the selected destination after that confirmation.
            destination = Path(dialog.selectedFiles()[0])
            format = "csv" if dialog.selectedNameFilter().startswith("CSV") else "md"
            if destination.suffix.lower() in (".md", ".csv"):
                format = destination.suffix.lower()[1:]
        finally:
            dialog.deleteLater()
        return self._start_export(destination, format=format, page=page, view=view)

    def export_to(self, path, *, format):
        if self._loading or self.search_timer.isActive() or self._snapshot is None or self._page is None:
            self.status_label.setText("Wait for History to finish loading before exporting.")
            return False
        return self._start_export(path, format=format, page=self._page, view=self._snapshot)

    def _start_export(self, path, *, format, page, view):
        if format not in ("md", "csv") or self._exporting:
            return False
        self._export_generation += 1
        if not self.jobs.export(self._export_generation, view, path, query=page.query,
                ceiling_id=page.ceiling_id, format=format):
            return False
        self._exporting = True
        self.export_button.setEnabled(False)
        self.cancel_export_button.setEnabled(True)
        self.cancel_export_button.show()
        self.status_label.setText("Exporting all matching entries…")
        return True

    def _cancel_export(self):
        self.jobs.cancel_export()
        self.cancel_export_button.setEnabled(False)
        self.status_label.setText("Cancelling export…")

    @QtCore.Slot(int, object)
    def _accept_export(self, generation, outcome):
        if generation != self._export_generation or self.jobs.closed:
            return
        self._exporting = False
        self.cancel_export_button.hide()
        self.export_button.setEnabled(not self._loading and self._page is not None and bool(self._page.total))
        status, count = outcome
        self.status_label.setText(f"Exported {count} entries" if status == "success" else "Export cancelled" if status == "cancelled"
            else "Could not export History. Choose another writable file and try again.")

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
                if self.list_widget.currentRow() != index:
                    self.list_widget.setCurrentRow(index)
                elif self._detail is None or self._detail.id != row_id:
                    self._selection_changed(index)
                return
        self._load_page(fresh=self._page is None or row_id > self._page.ceiling_id, selected_id=row_id)

    def choose_retry(self):
        if self._retry_source_id is not None:
            return self.cancel_retry()
        row = self.current_row()
        if row is None or row.mode in ('command', 'ask', 'translate', 'translation_failed') or not row.audio_path or self.retry_callback is None or self.jobs.closed:
            return False
        from saydraft.asr.retry import installed_retry_models
        from .history_retry import HistoryRetryDialog
        try:
            models = (self.retry_models_provider or installed_retry_models)()
        except Exception:
            self.status_label.setText("Could not read installed speech models. Check Settings → Models.")
            return False
        dialog = HistoryRetryDialog(models, source_model=row.asr_model or row.model, parent=self)
        try:
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return False
            options = dialog.options()
        finally:
            dialog.deleteLater()
        return self.retry_current_audio(options, row=row)

    def retry_current_audio(self, options=None, *, row=None):
        row = row or self.current_row()
        if (row is None or row.mode in ('command', 'ask', 'translate', 'translation_failed') or not row.audio_path or self.retry_callback is None
                or self._retry_source_id is not None or self.jobs.closed):
            return False
        self._retry_source_id = row.id
        self._retry_follow_source = self._selected_id() == row.id
        self._retry_cancel_requested = False
        self.update_detail()
        self.status_label.setText("Retrying saved audio locally; AI preparation may take a moment…")
        try:
            queued = self.retry_callback(row) if options is None else self.retry_callback(row, options)
        except Exception:
            queued = False
        if not queued:
            self._retry_source_id = None
            self.update_detail()
            self.status_label.setText("Finish the current dictation or retry before starting another.")
            return False
        return True

    def cancel_retry(self):
        if self._retry_source_id is None or self._retry_cancel_requested or self.cancel_retry_callback is None:
            return False
        try:
            queued = bool(self.cancel_retry_callback())
        except Exception:
            queued = False
        if queued:
            self._retry_cancel_requested = True
            self.update_detail()
            self.status_label.setText("Cancelling retry after the current recognition step…")
        return queued

    def finish_retry(self, row_id):
        selected = self.current_row()
        source_selected = self._retry_follow_source and (selected is None or selected.id == self._retry_source_id)
        cancelled = self._retry_cancel_requested
        self._retry_source_id = None
        self._retry_cancel_requested = False
        self._retry_follow_source = False
        self.refresh()
        if row_id and source_selected:
            self.search_edit.clear()
            self._select_id(row_id)
        self.update_detail()
        self.status_label.setText("Retry saved as a new History entry" if row_id else
            "Retry cancelled" if cancelled else "Retry could not finish; check the notification.")

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
        if row is None or row.mode in ('command', 'ask', 'translation_failed') or not text or self.reinsert_callback is None:
            return False
        try:
            queued = self.reinsert_callback(text, row)
        except TypeError:
            queued = self.reinsert_callback(text)
        if queued is False:
            self.status_label.setText("Dictation is busy. Try reinserting again when it finishes.")
            return False
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

    def _item_text(self, row: HistorySummary) -> str:
        preview = " ".join(row.preview.split())
        if not preview:
            preview = "Saved text" if row.has_text else "Recording saved for recognition retry" if row.has_audio else "No cleaned text"
        if len(preview) > 80:
            preview = preview[:77] + "..."
        app = row.app_name or "Unknown"
        return f"{app} · {timestamp_label(row.created_at)}\n{preview}"

    def _duration_text(self, row: HistoryRow) -> str:
        if row.duration_seconds is None:
            return ""
        return f"{row.duration_seconds:.1f}s"

    def closeEvent(self, event):
        self.cancel_retry()
        self.search_timer.stop()
        self.jobs.close()
        self._snapshot = None
        super().closeEvent(event)
