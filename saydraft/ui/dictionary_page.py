"""Structured, staged Dictionary editing with private provenance and portable I/O."""

import copy
from dataclasses import dataclass
import json
from pathlib import Path
import re

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.dictionary.portable import export_dictionary, prepare_import
from saydraft.dictionary.store import DictionarySnapshot, entry_source, term_key, validate_dictionary_edit
from .private_text import PrivatePlainTextEdit


@dataclass(frozen=True)
class _Row:
    position: object
    term: str
    value: str | None
    source: str


class _Entries(QtCore.QAbstractTableModel):
    def __init__(self, parent):
        super().__init__(parent)
        self.rows, self.pairs = [], False

    def replace(self, rows, pairs):
        self.beginResetModel()
        self.rows, self.pairs = rows, pairs
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else 3 if self.pairs else 2

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or role != QtCore.Qt.DisplayRole:
            return None
        row = self.rows[index.row()]
        return (row.term, row.value, row.source)[index.column()] if self.pairs else (row.term, row.source)[index.column()]

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return ("You say", "Write", "Source")[section] if self.pairs else ("Term", "Source")[section]
        return None


class _SourceChips(QtWidgets.QStyledItemDelegate):
    @staticmethod
    def font(base):
        font = QtGui.QFont(base)
        if font.pixelSize() > 0:
            font.setPixelSize(max(12, round(font.pixelSize() * .75)))
        else:
            font.setPointSizeF(max(9, font.pointSizeF() * .75))
        return font

    def paint(self, painter, option, index):
        if index.column() != index.model().columnCount() - 1:
            return super().paint(painter, option, index)
        background = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(background, index)
        background.text = ""
        option.widget.style().drawControl(QtWidgets.QStyle.CE_ItemViewItem, background, painter, option.widget)
        text = index.data() or "Manual"
        font = self.font(option.font)
        metrics = QtGui.QFontMetrics(font)
        width, height = metrics.horizontalAdvance(text) + 16, metrics.height() + 6
        rect = QtCore.QRectF(option.rect.x() + 8, option.rect.center().y() - height / 2, width, height)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(option.palette.color(QtGui.QPalette.AlternateBase))
        painter.drawRoundedRect(rect, height / 2, height / 2)
        painter.setPen(option.palette.color(QtGui.QPalette.Text))
        painter.setFont(font)
        painter.drawText(rect, QtCore.Qt.AlignCenter, text)
        painter.restore()


class DictionaryPage(QtWidgets.QWidget):
    status_changed = QtCore.Signal(str)
    reload_requested = QtCore.Signal()

    def __init__(self, path):
        super().__init__()
        self.path, self.snapshot = Path(path), None
        self._imports, self._claims = {}, {}
        self._loaded_text = "{}"
        self._current_data = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QtWidgets.QLabel("Words that matter to you.")
        title.setProperty("role", "display")
        title.setWordWrap(True)
        layout.addWidget(title)
        learning = QtWidgets.QVBoxLayout()
        self.learn_checkbox = QtWidgets.QCheckBox("Suggest words from corrections")
        self.learn_checkbox.setToolTip("Compare the original field after insertion to suggest corrected words. Password and unreadable fields are skipped.")
        self.auto_add_checkbox = QtWidgets.QCheckBox("Auto-add to dictionary")
        self.auto_add_checkbox.setToolTip("Save suggested words automatically and show an Undo action.")
        self.learn_checkbox.toggled.connect(self.auto_add_checkbox.setEnabled)
        learning.addWidget(self.learn_checkbox)
        learning.addWidget(self.auto_add_checkbox)
        layout.addLayout(learning)
        toolbar = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search terms and replacements")
        self.search.setAccessibleName("Search Dictionary")
        toolbar.addWidget(self.search, 1)
        self.import_button = QtWidgets.QPushButton("Import…")
        self.export_button = QtWidgets.QPushButton("Export…")
        toolbar.addWidget(self.import_button)
        toolbar.addWidget(self.export_button)
        layout.addLayout(toolbar)
        self.kind = QtWidgets.QComboBox()
        self.kind.setAccessibleName("Dictionary entry type")
        for caption, value in (("Terms", "user_terms"), ("Protected terms", "protected_terms"), ("Replacement pairs", "replacements")):
            self.kind.addItem(caption, value)
        layout.addWidget(self.kind)
        self.model = _Entries(self)
        self.table = QtWidgets.QTableView()
        self.table.setAccessibleName("Dictionary entries and sources")
        self.table.setModel(self.model)
        self.table.setItemDelegate(_SourceChips(self.table))
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(140)
        layout.addWidget(self.table, 1)
        form = QtWidgets.QHBoxLayout()
        self.term_edit = QtWidgets.QLineEdit()
        self.term_edit.setPlaceholderText("Term or spoken phrase")
        self.term_edit.setAccessibleName("Term or spoken phrase")
        self.value_edit = QtWidgets.QLineEdit()
        self.value_edit.setPlaceholderText("Replacement text")
        self.value_edit.setAccessibleName("Replacement text")
        form.addWidget(self.term_edit, 1)
        form.addWidget(self.value_edit, 1)
        layout.addLayout(form)
        actions = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QPushButton("Add")
        self.update_button = QtWidgets.QPushButton("Update")
        self.update_button.setAccessibleName("Update selected Dictionary entry")
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.remove_button.setAccessibleName("Remove selected Dictionary entry")
        self.manual_button = QtWidgets.QPushButton("Make manual")
        self.manual_button.setToolTip("Saving this claim retires the entry's previous learning Undo.")
        for button in (self.add_button, self.update_button, self.remove_button, self.manual_button):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.status_label = QtWidgets.QLabel()
        self.status_label.setTextFormat(QtCore.Qt.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.advanced = QtWidgets.QCheckBox("Advanced JSON")
        self.advanced.setChecked(False)
        self.json_editor = PrivatePlainTextEdit()
        self.json_editor.setObjectName("dictionaryEditor")
        self.json_editor.setAccessibleName("Advanced Dictionary JSON")
        self.json_editor.setMinimumHeight(140)
        self.json_editor.hide()
        self.advanced.toggled.connect(self.json_editor.setVisible)
        layout.addWidget(self.advanced)
        layout.addWidget(self.json_editor)
        self.reload_button = QtWidgets.QPushButton("Reload saved Dictionary")
        self.reload_button.setToolTip("Discard unsaved Dictionary edits and reload the saved file.")
        self.reload_button.clicked.connect(self.reload_requested)
        layout.addWidget(self.reload_button)
        self.search.textChanged.connect(self._rows)
        self.kind.currentIndexChanged.connect(self._rows)
        self.table.selectionModel().currentChanged.connect(self._selection)
        self.json_editor.textChanged.connect(self._sync_json)
        self.add_button.clicked.connect(self.add_entry)
        self.update_button.clicked.connect(self.update_entry)
        self.remove_button.clicked.connect(self.remove_entry)
        self.manual_button.clicked.connect(self.make_manual)
        self.import_button.clicked.connect(self.choose_import)
        self.export_button.clicked.connect(self.choose_export)
        self.json_editor.setPlainText("{}")

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        self._imports, self._claims = {}, {}
        self._loaded_text = json.dumps(snapshot.editable, ensure_ascii=False, indent=2) + "\n"
        self.json_editor.setPlainText(self._loaded_text)
        self.note("")

    def set_invalid(self, raw):
        self.snapshot = None
        self._imports, self._claims = {}, {}
        self._loaded_text = raw
        self.json_editor.setPlainText(raw)
        self.advanced.setChecked(True)
        self.note("Could not load Dictionary. Repair the saved JSON, then reload it.")

    def data(self):
        try:
            data = json.loads(self.json_editor.toPlainText())
            validate_dictionary_edit(self.snapshot or DictionarySnapshot({}, None), data)
            return data
        except (ValueError, RecursionError) as exc:
            raise ValueError("Dictionary JSON is invalid: " + str(exc)) from exc

    @property
    def dirty(self):
        if self.form_changed():
            return True
        if self.snapshot is None:
            return self.json_editor.toPlainText() != self._loaded_text
        try:
            return self.data() != self.snapshot.editable or bool(self.imports or self.manual_claims)
        except ValueError:
            return True

    def form_changed(self):
        row = self._selected()
        return (self.term_edit.text() != (row.term if row else "") or
            self.kind.currentData() == "replacements" and self.value_edit.text() != (row.value or "" if row else ""))

    def commit_form(self):
        return self._edit("update" if self._selected() is not None else "add") if self.form_changed() else True

    @property
    def imports(self):
        data = self._current_data or {}
        output = {}
        for category, records in self._imports.items():
            terms = data.get(category, {} if category == "replacements" else [])
            lookup = terms if category == "replacements" else set(terms)
            for key, record in records.items():
                if record["term"] in lookup and (category != "replacements" or lookup[record["term"]] == record["value"]):
                    output.setdefault(category, {})[key] = copy.deepcopy(record)
        return output

    @property
    def manual_claims(self):
        return [(category, term) for (category, _key), term in self._claims.items()]

    def note(self, message):
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))
        self.status_changed.emit(message)

    def _sync_json(self):
        try:
            self._current_data = self.data()
        except ValueError as exc:
            self._current_data = None
            self.note(str(exc))
            self.advanced.setChecked(True)
        self._rows()

    def _source(self, category, term, value):
        key = term_key(term)
        if (category, key) in self._claims:
            return "Manual"
        record = self._imports.get(category, {}).get(key)
        if record and record["term"] == term and (category != "replacements" or record["value"] == value):
            return "Imported"
        return entry_source(self.snapshot, category, term, value)

    def _rows(self, *_args):
        category = self.kind.currentData()
        pairs = category == "replacements"
        self.value_edit.setVisible(pairs)
        data = self._current_data or {}
        values = data.get(category, {} if pairs else [])
        query = self.search.text().casefold().strip()
        rows = []
        for position, term in enumerate(values):
            value = values[term] if pairs else None
            source = self._source(category, term, value)
            if not query or query in (term + " " + (value or "") + " " + source).casefold():
                rows.append(_Row(term if pairs else position, term, value, source))
        self.model.replace(rows, pairs)
        header = self.table.horizontalHeader()
        for index in range(self.model.columnCount() - 1):
            header.setSectionResizeMode(index, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(self.model.columnCount() - 1, QtWidgets.QHeaderView.Fixed)
        self.table.setColumnWidth(self.model.columnCount() - 1, max(104,
            QtGui.QFontMetrics(_SourceChips.font(self.table.font())).horizontalAdvance("Imported") + 32))
        self.table.verticalHeader().setDefaultSectionSize(max(36, self.table.fontMetrics().height() + 14))
        allowed = self.snapshot is not None and self._current_data is not None
        self.add_button.setEnabled(allowed)
        self.import_button.setEnabled(allowed)
        self.export_button.setEnabled(self._current_data is not None)
        self._selection()

    def _selected(self):
        index = self.table.currentIndex()
        return self.model.rows[index.row()] if index.isValid() and index.row() < len(self.model.rows) else None

    def _selection(self, *_args):
        row = self._selected()
        self.term_edit.setText(row.term if row else "")
        self.value_edit.setText(row.value or "" if row else "")
        for button in (self.update_button, self.remove_button):
            button.setEnabled(row is not None and self.snapshot is not None)
        self.manual_button.setEnabled(row is not None and row.source != "Manual" and self.snapshot is not None)

    def _commit(self, data, *, imports=None, claims=None):
        imports = self._imports if imports is None else imports
        claims = self._claims if claims is None else claims
        # Only metadata for entries still present in this staged document travels
        # to Save; raw JSON edits may have removed an earlier imported entry.
        valid_imports = {}
        for category, records in imports.items():
            values = data.get(category, {} if category == "replacements" else [])
            lookup = values if category == "replacements" else set(values)
            for key, record in records.items():
                if record["term"] in lookup and (category != "replacements" or lookup[record["term"]] == record["value"]):
                    valid_imports.setdefault(category, {})[key] = record
        validate_dictionary_edit(self.snapshot, data, imports=valid_imports,
            manual_claims=[(category, term) for (category, _key), term in claims.items()])
        self._imports, self._claims = valid_imports, claims
        self.json_editor.setPlainText(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    def _edit(self, operation):
        try:
            if self.snapshot is None:
                raise ValueError("Reload the repaired Dictionary before editing.")
            data, category = self.data(), self.kind.currentData()
            row = self._selected()
            pairs = category == "replacements"
            values = data.setdefault(category, {} if pairs else [])
            claims = self._claims.copy()
            if operation in ("remove", "manual"):
                if row is None:
                    return False
                if operation == "remove":
                    values.pop(row.position)
                claims[category, term_key(row.term)] = row.term
            else:
                term = re.sub(r"\s+", " ", self.term_edit.text()).strip()
                if not term:
                    raise ValueError("Enter a term or spoken phrase first.")
                if operation == "update" and row is None:
                    return False
                if any(term_key(value) == term_key(term) for position, value in enumerate(values)
                       if operation != "update" or (value if pairs else position) != row.position):
                    raise ValueError("This term or phrase is already in this list.")
                value = self.value_edit.text() if pairs else None
                if operation == "add":
                    if pairs:
                        values[term] = value
                    else:
                        values.append(term)
                elif row.term == term and row.value == value:
                    return True
                elif pairs:
                    data[category] = {term if key == row.position else key: value if key == row.position else old
                        for key, old in values.items()}
                else:
                    values[row.position] = term
                claims[category, term_key(term)] = term
            self._commit(data, claims=claims)
            self.note("Dictionary edit staged. Save changes to apply it.")
            return True
        except (OSError, ValueError) as exc:
            self.note(str(exc))
            return False

    def add_entry(self):
        return self._edit("add")

    def update_entry(self):
        return self._edit("update")

    def remove_entry(self):
        return self._edit("remove")

    def make_manual(self):
        return self._edit("manual")

    def import_file(self, path):
        try:
            if self.snapshot is None:
                raise ValueError("Reload the repaired Dictionary before importing.")
            result = prepare_import(self.data(), path)
            imports = copy.deepcopy(self._imports)
            for category, records in result.imports.items():
                imports.setdefault(category, {}).update(records)
            self._commit(result.data, imports=imports)
            self.note(f"Staged {result.added} new entries; {result.skipped} already present; {result.conflicts} existing replacements kept. Save changes to apply.")
            return True
        except (OSError, ValueError, RecursionError) as exc:
            self.note("Could not import Dictionary: " + str(exc))
            return False

    def export_file(self, path):
        try:
            if Path(path).resolve() == self.path.resolve():
                raise ValueError("Choose another file to export a copy of Dictionary.")
            export_dictionary(path, self.data())
            self.note("Exported Dictionary copy. Staged edits are included.")
            return True
        except (OSError, ValueError, RecursionError) as exc:
            self.note("Could not export Dictionary: " + str(exc))
            return False

    def choose_import(self):
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(self, "Import Dictionary", "", "Dictionary JSON (*.json)")
        return self.import_file(path) if path else False

    def choose_export(self):
        dialog = QtWidgets.QFileDialog(self, "Export Dictionary copy")
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        dialog.setNameFilter("Dictionary JSON (*.json)")
        dialog.setDefaultSuffix("json")
        dialog.selectFile("saydraft-dictionary")
        try:
            if dialog.exec() != QtWidgets.QDialog.Accepted or not dialog.selectedFiles():
                return False
            return self.export_file(dialog.selectedFiles()[0])
        finally:
            dialog.deleteLater()
