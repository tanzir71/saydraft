"""Structured staged snippets with a private, clipboard-free test panel."""

import re

from PySide6 import QtCore, QtWidgets

from saydraft.core.preferences import protect_snippets, restore_snippets
from saydraft.snippets import dump_document, parse_document, resolve_mapping, trigger_key, validate_entries
from .private_text import PrivatePlainTextEdit


class _Entries(QtCore.QAbstractTableModel):
    def __init__(self, parent):
        super().__init__(parent)
        self.rows = []

    def replace(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else 2

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid() and role == QtCore.Qt.DisplayRole:
            value = self.rows[index.row()][index.column()]
            return value if index.column() == 0 else value.replace("\n", " / ")
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        return ("When you say", "Write")[section] if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole else None


class SnippetsPage(QtWidgets.QWidget):
    status_changed = QtCore.Signal(str)
    reload_requested = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.snapshot, self._entries = None, {}
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QtWidgets.QLabel("Say a little. Write a lot.")
        title.setProperty("role", "display")
        title.setWordWrap(True)
        layout.addWidget(title)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search triggers and expansions")
        self.search.setAccessibleName("Search Snippets")
        layout.addWidget(self.search)
        self.model = _Entries(self)
        self.table = QtWidgets.QTableView()
        self.table.setAccessibleName("Snippet triggers and expansions")
        self.table.setModel(self.model)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.setMinimumHeight(140)
        self.table.setMaximumHeight(150)
        layout.addWidget(self.table, 1)
        self.trigger_edit = QtWidgets.QLineEdit()
        self.trigger_edit.setPlaceholderText("Spoken trigger phrase")
        self.trigger_edit.setAccessibleName("Spoken snippet trigger")
        layout.addWidget(self.trigger_edit)
        self.expansion_edit = PrivatePlainTextEdit()
        self.expansion_edit.setPlaceholderText("Text to write, including multiple lines")
        self.expansion_edit.setAccessibleName("Snippet expansion")
        self.expansion_edit.setMinimumHeight(80)
        self.expansion_edit.setMaximumHeight(110)
        layout.addWidget(self.expansion_edit)
        variables = QtWidgets.QHBoxLayout()
        self.date_button = QtWidgets.QPushButton("Insert {date}")
        self.clipboard_button = QtWidgets.QPushButton("Insert {clipboard}")
        for button, text in ((self.date_button, "{date}"), (self.clipboard_button, "{clipboard}")):
            button.clicked.connect(lambda _checked=False, text=text: self._insert_variable(text))
            variables.addWidget(button)
        variables.addStretch()
        layout.addLayout(variables)
        hint = QtWidgets.QLabel("{date} writes the local date (YYYY-MM-DD). {clipboard} uses copied text when you dictate this phrase. Double braces keep a variable literal: {{date}}.")
        hint.setWordWrap(True)
        hint.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(hint)
        actions = QtWidgets.QHBoxLayout()
        self.add_button, self.update_button, self.remove_button, self.new_button = [
            QtWidgets.QPushButton(text) for text in ("Add", "Update", "Remove", "New snippet")]
        self.update_button.setAccessibleName("Update selected snippet")
        self.remove_button.setAccessibleName("Remove selected snippet")
        for button in (self.add_button, self.update_button, self.remove_button, self.new_button):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(QtCore.Qt.PlainText)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        self.test_toggle = QtWidgets.QCheckBox("Test a trigger")
        layout.addWidget(self.test_toggle)
        self.test_panel = QtWidgets.QWidget()
        test_layout = QtWidgets.QVBoxLayout(self.test_panel)
        test_layout.setContentsMargins(0, 0, 0, 0)
        self.test_input, self.clipboard_sample, self.test_output = [PrivatePlainTextEdit() for _ in range(3)]
        for editor, name in ((self.test_input, "Snippet test phrase"), (self.clipboard_sample, "Clipboard sample for snippet test"),
                (self.test_output, "Snippet test result")):
            editor.setAccessibleName(name)
            editor.setPlaceholderText(name)
            editor.setFixedHeight(90)
            test_layout.addWidget(editor)
        self.test_output.setReadOnly(True)
        self.test_button = QtWidgets.QPushButton("Test expansion")
        test_layout.addWidget(self.test_button)
        note = QtWidgets.QLabel("Preview uses the sample above. It never reads your clipboard, records History or pastes text.")
        note.setWordWrap(True)
        test_layout.addWidget(note)
        self.test_toggle.toggled.connect(self.test_panel.setVisible)
        self.test_panel.hide()
        layout.addWidget(self.test_panel)
        self.advanced = QtWidgets.QCheckBox("Advanced JSON / legacy text")
        layout.addWidget(self.advanced)
        self.json_editor = PrivatePlainTextEdit()
        self.json_editor.setObjectName("snippetsEditor")
        self.json_editor.setAccessibleName("Advanced Snippets document")
        self.json_editor.setMinimumHeight(140)
        self.json_editor.hide()
        self.advanced.toggled.connect(self.json_editor.setVisible)
        layout.addWidget(self.json_editor)
        self.reload_button = QtWidgets.QPushButton("Reload saved Snippets")
        self.reload_button.setToolTip("Discard this draft and reload saved Snippets.")
        layout.addWidget(self.reload_button)
        self.reload_button.clicked.connect(self.reload_requested)
        self.search.textChanged.connect(self._rows)
        self.table.selectionModel().currentChanged.connect(self._selection)
        self.json_editor.textChanged.connect(self._sync_json)
        self.add_button.clicked.connect(lambda: self._edit("add"))
        self.update_button.clicked.connect(lambda: self._edit("update"))
        self.remove_button.clicked.connect(lambda: self._edit("remove"))
        self.new_button.clicked.connect(self.clear_form)
        self.test_button.clicked.connect(self.test_expansion)
        self.json_editor.setPlainText("{}")

    def note(self, message):
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))
        self.status_changed.emit(message)

    def _insert_variable(self, text):
        self.expansion_edit.insertPlainText(text)
        self.expansion_edit.setFocus()

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.json_editor.setPlainText(dump_document(snapshot.editable))
        self.note("")

    def set_invalid(self, message):
        self.snapshot = None
        self.json_editor.setPlainText("Could not load saved Snippets.\n" + message)
        self.advanced.setChecked(True)
        self.note("Could not load saved Snippets. Repair the source or database, then reload.")

    def entries(self, *, include_form=False):
        entries = parse_document(self.json_editor.toPlainText(), strict=True)
        if include_form and self.form_changed():
            entries = self._edited(entries, "update" if self._selected() else "add")
        return entries

    @property
    def dirty(self):
        try:
            return self.form_changed() or self.snapshot is None or self.entries() != self.snapshot.editable
        except ValueError:
            return True

    def _selected(self):
        index = self.table.currentIndex()
        return self.model.rows[index.row()] if index.isValid() and index.row() < len(self.model.rows) else None

    def form_changed(self):
        selected = self._selected() or ("", "")
        return (self.trigger_edit.text(), self.expansion_edit.toPlainText()) != selected

    def clear_form(self):
        self.table.clearSelection()
        self.table.setCurrentIndex(QtCore.QModelIndex())
        self._selection()

    def _sync_json(self):
        try:
            self._entries = self.entries()
        except ValueError as exc:
            self._entries = None
            self.advanced.setChecked(True)
            self.note(str(exc))
        self._rows()

    def _rows(self, *_args):
        query = self.search.text().casefold().strip()
        self.model.replace([(trigger, text) for trigger, text in (self._entries or {}).items()
            if not query or query in (trigger + " " + text).casefold()])
        self.table.verticalHeader().setDefaultSectionSize(max(36, self.table.fontMetrics().height() + 14))
        enabled = self.snapshot is not None and self._entries is not None
        for button in (self.add_button, self.new_button, self.date_button, self.clipboard_button, self.test_button):
            button.setEnabled(enabled)
        self._selection()

    def _selection(self, *_args):
        selected = self._selected()
        self.trigger_edit.setText(selected[0] if selected else "")
        self.expansion_edit.setPlainText(selected[1] if selected else "")
        for button in (self.update_button, self.remove_button):
            button.setEnabled(selected is not None and self.snapshot is not None)

    def _edited(self, entries, operation):
        if self.snapshot is None:
            raise ValueError("Reload saved Snippets before editing.")
        entries = dict(entries)
        selected = self._selected()
        if operation == "remove":
            if selected:
                entries.pop(selected[0])
        else:
            trigger = re.sub(r"\s+", " ", self.trigger_edit.text()).strip()
            if not trigger:
                raise ValueError("Enter a spoken trigger phrase first.")
            if any(trigger_key(key) == trigger_key(trigger) for key in entries
                    if operation != "update" or selected is None or key != selected[0]):
                raise ValueError("This trigger phrase is already in Snippets.")
            value = self.expansion_edit.toPlainText()
            if not value:
                raise ValueError("Enter the text this phrase should write first.")
            if operation == "update" and selected:
                entries = {trigger if key == selected[0] else key: value if key == selected[0] else old
                    for key, old in entries.items()}
            else:
                entries[trigger] = value
        return validate_entries(entries)

    def _edit(self, operation):
        try:
            self.json_editor.setPlainText(dump_document(self._edited(self.entries(), operation)))
            self.note("Snippet edit staged. Save changes to apply it.")
            return True
        except ValueError as exc:
            self.note(str(exc))
            return False

    def commit_form(self):
        return self._edit("update" if self._selected() else "add") if self.form_changed() else True

    def test_expansion(self):
        try:
            text = self.test_input.toPlainText()
            if len(text) > 4096:
                raise ValueError("Keep the test phrase under 4096 characters.")
            entries = self.entries(include_form=True)
            originals = {}
            protected, mapping = protect_snippets(text, entries, originals=originals)
            mapping, failed = resolve_mapping(protected, mapping, originals,
                clipboard_reader=lambda: self.clipboard_sample.toPlainText())
            self.test_output.setPlainText(restore_snippets(protected, mapping))
            self.note("Some expansions exceeded the test limit; their spoken triggers were kept." if failed
                else "Preview ready. Nothing saved, copied or pasted.")
            return not failed
        except (ValueError, RecursionError) as exc:
            self.test_output.clear()
            self.note(str(exc))
            return False
