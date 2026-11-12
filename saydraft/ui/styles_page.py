"""Reusable group matrix with real-processor rules and optional current-AI previews."""

import json
from dataclasses import replace

from PySide6 import QtCore, QtWidgets

from saydraft.cleanup.styles import select_style, style_for
from saydraft.context.app_groups import app_group
from saydraft.core.preferences import parse_snippets, select_context
from saydraft.core.style_preview import MAX_PREVIEW, StylePreviewRequest, render_style_preview
from .private_text import PrivatePlainTextEdit

GROUP_LABELS = {"messages": "Messages", "work_chat": "Work chat", "email": "Email", "docs": "Docs & notes",
    "code": "Code", "ai_chat": "AI chat", "general": "Other"}
TONE_LABELS = {"formal": "Formal", "casual": "Casual", "very_casual": "Very casual"}
LEVEL_LABELS = {1: "1 · Verbatim-ish", 2: "2 · Light", 3: "3 · Balanced", 4: "4 · Polished"}


class StylesPage(QtWidgets.QScrollArea):
    def __init__(self, config, *, config_provider, profiles_provider=lambda: [], snippets_provider=lambda: "",
                 glossary_provider, callback=None):
        super().__init__()
        self.config_provider, self.profiles_provider = config_provider, profiles_provider
        self.snippets_provider, self.glossary_provider, self.callback = snippets_provider, glossary_provider, callback
        self._generation, self._pending = 0, None
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.refresh)
        self.setWidgetResizable(True)
        body = QtWidgets.QWidget()
        self.setWidget(body)
        layout = QtWidgets.QVBoxLayout(body)
        intro = QtWidgets.QLabel("Choose a style for each app group. Default follows your cleanup settings; app overrides take priority.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.matrix = QtWidgets.QTableWidget(len(GROUP_LABELS), 3)
        self.matrix.setHorizontalHeaderLabels(["App group", "Tone", "Cleanup"])
        self.matrix.verticalHeader().hide()
        self.matrix.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.matrix.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tones, self.levels = {}, {}
        saved = config["dictation"].get("styles", {})
        for row, (group, label) in enumerate(GROUP_LABELS.items()):
            self.matrix.setItem(row, 0, QtWidgets.QTableWidgetItem(label))
            for column, values, mapping, field in ((1, TONE_LABELS, self.tones, "tone"), (2, LEVEL_LABELS, self.levels, "intensity")):
                combo = QtWidgets.QComboBox()
                combo.addItem("Default", None)
                for value, name in values.items():
                    combo.addItem(name, value)
                combo.setCurrentIndex(max(0, combo.findData(saved.get(group, {}).get(field))))
                combo.setAccessibleName(f"{label} {field}")
                combo.setEnabled(group != "code")
                if group == "code":
                    combo.setToolTip("Code uses spoken-code formatting and skips prose styles.")
                mapping[group] = combo
                self.matrix.setCellWidget(row, column, combo)
                combo.currentIndexChanged.connect(lambda index, selected=group: self._row_changed(selected))
        self.matrix.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.matrix.verticalHeader().sectionResized.connect(self._fit_matrix)
        self.matrix.horizontalHeader().geometriesChanged.connect(self._fit_matrix)
        self._fit_matrix()
        layout.addWidget(self.matrix)
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Preview group"))
        self.group = QtWidgets.QComboBox()
        self.group.setAccessibleName("Preview app group")
        for group, label in GROUP_LABELS.items():
            self.group.addItem(label, group)
        bar.addWidget(self.group, 1)
        self.ai_button = QtWidgets.QPushButton("Preview with current AI")
        self.ai_button.setEnabled(callback is not None)
        self.ai_button.clicked.connect(self.preview_ai)
        bar.addWidget(self.ai_button)
        layout.addLayout(bar)
        details = QtWidgets.QHBoxLayout()
        self.exe, self.site, self.title = (QtWidgets.QLineEdit() for _ in range(3))
        for edit, placeholder in ((self.exe, "App .exe (optional)"), (self.site, "Site hostname (optional)"),
                (self.title, "Window title (legacy overrides)")):
            edit.setPlaceholderText(placeholder)
            edit.setAccessibleName(placeholder)
            edit.textChanged.connect(self.invalidate)
            details.addWidget(edit)
        self.site.setToolTip("Test a site override. A Chrome browser is simulated when the app field is blank.")
        layout.addLayout(details)
        editors = QtWidgets.QHBoxLayout()
        self.before, self.after = PrivatePlainTextEdit(), PrivatePlainTextEdit()
        self.before.setPlainText("um like hello hello world.")
        self.after.setReadOnly(True)
        for name, editor in (("Before cleanup", self.before), ("Preview", self.after)):
            column = QtWidgets.QVBoxLayout()
            column.addWidget(QtWidgets.QLabel(name))
            editor.setAccessibleName(name)
            editor.setMinimumHeight(100)
            column.addWidget(editor)
            editors.addLayout(column)
        layout.addLayout(editors)
        self.status = QtWidgets.QLabel()
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.before.textChanged.connect(self.invalidate)
        self.group.currentIndexChanged.connect(self.invalidate)
        self.matrix.cellClicked.connect(self._select_group)
        self._defaults(config)

    def _fit_matrix(self, *_args):
        height = self.matrix.horizontalHeader().height() + sum(self.matrix.rowHeight(row) for row in range(self.matrix.rowCount())) + 2 * self.matrix.frameWidth()
        if height != self.matrix.height():
            self.matrix.setFixedHeight(height)

    def _select_group(self, row, column):
        self.group.setCurrentIndex(row)

    def _row_changed(self, group):
        if not self.exe.text().strip() and not self.site.text().strip():
            self.group.setCurrentIndex(self.group.findData(group))
        self.invalidate()

    def _defaults(self, config):
        options = {**config["dictation"], "styles": {}}
        for group in GROUP_LABELS:
            style = select_style(options, group)
            self.tones[group].setItemText(0, "Default · " + TONE_LABELS[style.tone])
            self.levels[group].setItemText(0, "Default · " + LEVEL_LABELS[style.intensity])

    def apply_to(self, config):
        config["dictation"]["styles"] = {group: fields for group in GROUP_LABELS if (fields := {
            field: mapping[group].currentData() for field, mapping in (("tone", self.tones), ("intensity", self.levels))
            if mapping[group].currentData() is not None})}

    @QtCore.Slot()
    def invalidate(self, *args):
        self._generation += 1
        self._pending = None
        self.ai_button.setEnabled(self.callback is not None)
        if self.isVisible():
            self.status.setText("Updating preview…")
            self.timer.start()

    def _request(self):
        text = self.before.toPlainText()
        if not text or len(text) > MAX_PREVIEW:
            raise ValueError("Type between 1 and 4,096 characters to preview cleanup.")
        cfg, profiles = self.config_provider(), self.profiles_provider()
        self._defaults(cfg)
        exe, site = self.exe.text().strip(), self.site.text().strip().lower()
        if site and not exe:
            exe = "chrome.exe"
        group = app_group(exe, site, profiles) if exe else self.group.currentData()
        self.group.setEnabled(not bool(exe))
        if exe:
            blocked = self.group.blockSignals(True)
            self.group.setCurrentIndex(self.group.findData(group))
            self.group.blockSignals(blocked)
        context = select_context(cfg, profiles, self.title.text() or None,
            app_group=group, app_exe=exe, app_site=site)
        context = replace(context, language=cfg["stt"]["language"] or "auto")
        return StylePreviewRequest(self._generation, text, context, self.glossary_provider(),
            tuple(sorted(parse_snippets(self.snippets_provider()).items())),
            cfg["dictation"]["drop_message_period"], cfg["dictation"]["voice_enter_enabled"],
            json.dumps(cfg["llm"], sort_keys=True))

    @QtCore.Slot()
    def refresh(self):
        self.timer.stop()
        try:
            request = self._request()
            result = render_style_preview(request)
        except ValueError as exc:
            self.after.clear()
            self.status.setText(str(exc))
            self.ai_button.setEnabled(False)
            return
        self.after.setPlainText(result.text)
        style = style_for(request.context)
        raw = request.context.mode == "raw"
        code = request.context.app_group == "code" or request.context.profile == "code/comments"
        bypass = raw or code or style.intensity == 1
        self.ai_button.setEnabled(self.callback is not None and not bypass and self._pending is None)
        policy = "Raw · styles skipped" if raw else "Code formatting" if code else (
            f"{TONE_LABELS[style.tone]} · {LEVEL_LABELS[style.intensity]}")
        self.status.setText(f"Rules preview · {GROUP_LABELS[request.context.app_group]} · "
            f"{policy}. "
            + ("Enter command previewed. " if result.enter_requested else "")
            + "AI preview uses the currently applied model. Nothing is recorded or pasted.")

    @QtCore.Slot()
    def preview_ai(self):
        self.timer.stop()
        try:
            request = self._request()
        except ValueError:
            self.refresh()
            return
        self.after.setPlainText(render_style_preview(request).text)
        self._pending = request
        self.ai_button.setEnabled(False)
        self.status.setText("Running AI preview…")
        if self.callback is None or not self.callback(request):
            self._pending = None
            self.ai_button.setEnabled(self.callback is not None)
            self.status.setText("Finish the current work before trying AI preview.")

    @QtCore.Slot(object)
    def accept_result(self, result):
        if result.request is not self._pending:
            return
        self._pending = None
        try:
            if self._request().key() != result.request.key():
                self.refresh()
                return
        except ValueError:
            self.refresh()
            return
        self.ai_button.setEnabled(self.callback is not None)
        if result.decision in ("unavailable", "closed", "obsolete", "invalid"):
            self.status.setText("AI preview unavailable. The rules preview remains available.")
        elif result.decision == "apply_settings":
            self.status.setText("Apply model changes before trying AI preview.")
        else:
            self.after.setPlainText(result.text)
            message = "AI preview" if result.decision == "accepted" else "Rules fallback"
            if result.enter_requested:
                message += " · Enter command previewed"
            if result.decision.startswith("prompt_"):
                message += ". AI is warming up; try again when ready."
            elif result.decision == "disabled":
                message += ". AI cleanup is off."
            else:
                message += ". Nothing was recorded or pasted."
            self.status.setText(message)

    def showEvent(self, event):
        super().showEvent(event)
        self.invalidate()

    def hideEvent(self, event):
        self.timer.stop()
        self._generation += 1
        self._pending = None
        super().hideEvent(event)
