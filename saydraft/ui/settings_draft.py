"""Staged preference tracking. No store writes and no capture or model callbacks."""
import copy
from PySide6 import QtCore, QtWidgets


class SettingsDraft(QtCore.QObject):
    changed = QtCore.Signal(int)

    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.refresh)
        excluded = {settings.section_combo, settings.dictionary_page.search, settings.dictionary_page.kind,
                    settings.dictionary_page.term_edit, settings.dictionary_page.value_edit,
                    settings.snippets_page.search, settings.snippets_page.trigger_edit,
                    settings.snippets_page.expansion_edit, settings.snippets_page.test_input,
                    settings.snippets_page.clipboard_sample, settings.snippets_page.test_output,
                    settings.microphone_page.device_combo}
        excluded.update((settings.shortcut_learner.primary, settings.languages_page.tiles.search,
                         settings.dictionary_editor, settings.snippets_editor))
        style = settings.styles_page
        excluded.update((style.translation_group, style.translation_language))
        excluded.update(getattr(style, name) for name in ("group", "language", "exe", "site", "title", "before", "after"))
        excluded.update((settings.dictionary_page.advanced, settings.snippets_page.advanced, settings.snippets_page.test_toggle))
        self.controls = []
        for widget in settings.findChildren(QtWidgets.QWidget):
            if widget in excluded:
                continue
            if isinstance(widget, QtWidgets.QLineEdit) and isinstance(widget.parent(), QtWidgets.QAbstractSpinBox):
                continue
            if isinstance(widget, QtWidgets.QLineEdit):
                self.controls.append((widget, "text", "setText"))
                widget.textChanged.connect(self.schedule)
            elif isinstance(widget, QtWidgets.QComboBox):
                self.controls.append((widget, "currentIndex", "setCurrentIndex"))
                widget.currentIndexChanged.connect(self.schedule)
            elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                self.controls.append((widget, "value", "setValue"))
                widget.valueChanged.connect(self.schedule)
            elif isinstance(widget, QtWidgets.QCheckBox):
                self.controls.append((widget, "isChecked", "setChecked"))
                widget.toggled.connect(self.schedule)
            elif isinstance(widget, QtWidgets.QPlainTextEdit) and not widget.isReadOnly():
                self.controls.append((widget, "toPlainText", "setPlainText"))
                widget.textChanged.connect(self.schedule)
        for widget in (settings.dictionary_page.term_edit, settings.dictionary_page.value_edit,
                       settings.snippets_page.trigger_edit, settings.snippets_page.expansion_edit):
            widget.textChanged.connect(self.schedule)
        settings.languages_page.changed.connect(self.schedule)
        style.translation_language.currentIndexChanged.connect(self.schedule)
        settings.dictionary_editor.textChanged.connect(self.schedule)
        settings.snippets_editor.textChanged.connect(self.schedule)
        settings.dictionary_page.status_changed.connect(self.schedule)
        settings.snippets_page.status_changed.connect(self.schedule)
        settings.microphone_page.device_combo.currentIndexChanged.connect(self.schedule)
        self.accept()

    def schedule(self, *_args):
        self.timer.start(0)

    def accept(self):
        self.settings.shortcut_target = None
        self.settings.shortcut_learner.hide()
        self.baseline = [getattr(widget, getter)() for widget, getter, _ in self.controls]
        self.selection = self.settings.microphone_page.selection
        self.targets = copy.deepcopy(self.settings.styles_page.translation_targets)
        self.refresh()

    def refresh(self):
        count = sum(getattr(widget, getter)() != old for (widget, getter, _), old in zip(self.controls, self.baseline))
        count += self.settings.microphone_page.selection != self.selection
        count += self.settings.styles_page.translation_targets != self.targets
        count += bool(self.settings.dictionary_page.dirty)
        count += bool(self.settings.snippets_page.dirty)
        self.count = int(count)
        self.changed.emit(self.count)
        return self.count

    def discard(self):
        s = self.settings
        if any(task is not None for task in (s.model_picker.task, s.cleanup_picker.task, s._vad_download_task,
                s.labs_page.task, s.labs_page.command.task, s.microphone_page.whisper_controls.task)):
            s.status_label.setText("Pause or finish downloads before discarding model choices.")
            self.changed.emit(self.count)
            return False
        s.shortcut_learner.cancel_learning()
        if s.shortcut_learner.learning:
            s.status_label.setText("Wait for shortcut learning to stop before discarding changes.")
            return False
        s.shortcut_target = None
        s.shortcut_learner.hide()
        s.microphone_page.stop_test()
        blockers = [QtCore.QSignalBlocker(widget) for widget, _, _ in self.controls]
        for (widget, _, setter), old in zip(self.controls, self.baseline):
            getattr(widget, setter)(old)
        del blockers
        s.microphone_page.set_selection(self.selection)
        s.styles_page.translation_targets = copy.deepcopy(self.targets)
        s.styles_page._translation_group()
        # Rebuild staged documents from their current saved snapshots, not disk.
        if s._dictionary_snapshot is not None:
            s.dictionary_page.set_snapshot(s._dictionary_snapshot)
        if s.snippets_page.snapshot is not None:
            s.snippets_page.set_snapshot(s.snippets_page.snapshot)
        s.languages_page._update_note()
        s.languages_page.tiles.sync()
        s.privacy_page._actions()
        s.auto_add_dictionary_checkbox.setEnabled(s.learn_corrections_checkbox.isChecked())
        s.model_picker.update_license()
        s.model_picker.refresh_choices()
        s.refresh_labs()
        s.cleanup_picker.update_details()
        s.microphone_page.whisper_controls._controls()
        from .kit import Segmented
        for segment in s.findChildren(Segmented):
            if segment.source_combo is not None:
                segment.setCurrentIndex(segment.source_combo.currentIndex())
        s.styles_page.invalidate()
        s.status_label.setText("Changes discarded")
        self.refresh()
        return True
