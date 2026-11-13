"""First-run PySide6 onboarding wizard."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.config import load_config, save_config
from saydraft.audio.devices import InputSelection
from saydraft.asr.selection import configured_model_id, select_model
from saydraft.ui.microphone_page import MicrophonePage
from saydraft.ui.model_picker import ModelPicker


class OnboardingWizard(QtWidgets.QWizard):
    PAGE_WELCOME = 0
    PAGE_MIC = 1
    PAGE_MODEL = 2
    PAGE_HOTKEY = 3
    PAGE_DONE = 4

    def __init__(
        self,
        *,
        qt_modules=None,
        config_path: str | os.PathLike[str] | None = None,
        on_config_applied: Callable[[dict[str, Any]], None] | None = None,
        model_download_callback: Callable[[str, Callable[[int], None]], None] | None = None,
        hotkey_hint: str | None = None,
        microphone_start_callback=None,
        microphone_stop_callback=None,
        microphone_devices_provider=None,
    ):
        super().__init__()
        self.qt = qt_modules
        self.config_path = Path(config_path) if config_path is not None else None
        self.on_config_applied = on_config_applied
        self.model_download_callback = model_download_callback
        self.microphone_start_callback = microphone_start_callback
        self.microphone_stop_callback = microphone_stop_callback
        self.microphone_devices_provider = microphone_devices_provider
        self.config = load_config(config_path=self.config_path)
        self._completed = False
        self.hotkey_hint = hotkey_hint or str(self.config["hotkeys"]["speech"]).upper()

        self.setWindowTitle("Saydraft Setup")
        self.setWizardStyle(QtWidgets.QWizard.ModernStyle)
        self.setMinimumSize(640, 440)
        self.setOption(QtWidgets.QWizard.NoBackButtonOnStartPage, True)

        self.addPage(self._welcome_page())
        self.addPage(self._microphone_page())
        self.addPage(self._model_page())
        self.addPage(self._hotkey_page())
        self.addPage(self._done_page())

        self.title_timer = QtCore.QTimer(self)
        self.title_timer.setSingleShot(True)
        self.title_timer.timeout.connect(self._refresh_title_font)
        self.currentIdChanged.connect(lambda _page: self.title_timer.start(0))
        QtWidgets.QApplication.instance().fontChanged.connect(self._schedule_title_font)

    @QtCore.Slot()
    def _schedule_title_font(self):
        self.title_timer.start(0)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.FontChange, QtCore.QEvent.StyleChange) and hasattr(self, "title_timer"):
            self.title_timer.start(0)

    def _refresh_title_font(self):
        page = self.currentPage()
        if page is None:
            return
        # Qt 6.11 derives this label with pointSize() + 4, even when the app
        # uses pixels (-1 points). Repair the heading without freezing body
        # fonts or recreating/hiding the page during an active input test.
        font = QtGui.QFont(self.font())
        if font.pixelSize() > 0:
            font.setPixelSize(font.pixelSize() + 4)
        else:
            font.setPointSizeF(font.pointSizeF() + 3)
        font.setBold(True)
        for label in self.findChildren(QtWidgets.QLabel):
            if label.isVisibleTo(self) and label.text() == page.title() and not page.isAncestorOf(label):
                label.setFont(font)

    def _welcome_page(self) -> QtWidgets.QWizardPage:
        page = QtWidgets.QWizardPage()
        page.setTitle("Welcome")
        layout = QtWidgets.QVBoxLayout(page)
        title = QtWidgets.QLabel("Saydraft")
        title.setObjectName("onboardingTitle")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 600;")
        subtitle = QtWidgets.QLabel("Offline dictation that stays in your tray.")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        return page

    def _microphone_page(self) -> QtWidgets.QWizardPage:
        page = QtWidgets.QWizardPage()
        page.setTitle("Microphone")
        layout = QtWidgets.QVBoxLayout(page)
        self.microphone_page = MicrophonePage(self.config,
            start_callback=self.microphone_start_callback,
            stop_callback=self.microphone_stop_callback,
            devices_provider=self.microphone_devices_provider,
            apply_label="Finish setup", show_title=False)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(self.microphone_page)
        layout.addWidget(scroll)
        self.microphone_scroll = scroll
        self.level_bar = self.microphone_page.level_bar
        self.mic_status_label = self.microphone_page.status
        return page

    def _model_page(self) -> QtWidgets.QWizardPage:
        page = QtWidgets.QWizardPage()
        page.setTitle("Model")
        layout = QtWidgets.QVBoxLayout(page)
        self.model_picker = ModelPicker(self.config, callback=self.model_download_callback)
        self.model_combo = self.model_picker.combo
        self.model_progress = self.model_picker.progress
        self.download_button = self.model_picker.download_button
        self.model_status_label = self.model_picker.status
        layout.addWidget(self.model_picker)
        layout.addStretch(1)
        return page

    def _hotkey_page(self) -> QtWidgets.QWizardPage:
        page = QtWidgets.QWizardPage()
        page.setTitle("Hotkey")
        layout = QtWidgets.QVBoxLayout(page)
        self.hotkey_hint_label = QtWidgets.QLabel(self.hotkey_hint)
        self.hotkey_hint_label.setObjectName("hotkeyHint")
        self.hotkey_hint_label.setAlignment(QtCore.Qt.AlignCenter)
        self.hotkey_hint_label.setStyleSheet("font-size: 24px; font-weight: 600;")
        self.hotkey_test_field = QtWidgets.QPlainTextEdit()
        self.hotkey_test_field.setPlaceholderText("Dictated text appears here during the tutorial")
        self.hotkey_test_field.textChanged.connect(self._update_hotkey_status)
        self.hotkey_status_label = QtWidgets.QLabel("Waiting for tutorial text")
        self.hotkey_status_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(QtWidgets.QLabel("Hold the speech hotkey and dictate into this field."))
        layout.addWidget(self.hotkey_hint_label)
        layout.addWidget(self.hotkey_test_field, 1)
        layout.addWidget(self.hotkey_status_label)
        return page

    def _done_page(self) -> QtWidgets.QWizardPage:
        page = QtWidgets.QWizardPage()
        page.setTitle("Done")
        layout = QtWidgets.QVBoxLayout(page)
        self.finish_status_label = QtWidgets.QLabel("Ready to dictate")
        self.finish_status_label.setWordWrap(True)
        self.finish_status_label.setTextFormat(QtCore.Qt.PlainText)
        self.finish_status_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(self.finish_status_label)
        layout.addStretch(1)
        return page

    def download_selected_model(self) -> None:
        self.model_picker.start_download()

    def update_model_download_progress(self, value: int) -> None:
        self.model_progress.setValue(max(0, min(100, int(value))))

    def finish_onboarding(self) -> bool:
        if self._completed:
            return True
        self.microphone_page.stop_test()
        try:
            # Merge only setup edits into the latest saved preferences. An open
            # Hub can save unrelated settings while the wizard is still visible.
            cfg = load_config(config_path=self.config_path)
            cfg["app"]["onboarded"] = True
            if self.model_picker.model_id != configured_model_id(self.config):
                select_model(cfg, self.model_picker.model_id, manual=True)
            selection = self.microphone_page.selection
            if selection != InputSelection.from_config(self.config):
                cfg["recording"].update(input_device=selection.name, input_hostapi=selection.hostapi)
            saved = save_config(cfg, self.config_path)
        except (OSError, ValueError):
            self.finish_status_label.setText("Could not save setup. Check your configuration folder and try Finish again.")
            return False
        self.config = saved
        self._completed = True
        self.finish_status_label.setText("Ready to dictate")
        if self.on_config_applied is not None:
            self.on_config_applied(saved)
        return True

    def accept(self) -> None:
        if self.finish_onboarding():
            self.model_picker.pause()
            super().accept()

    def reject(self) -> None:
        self.microphone_page.stop_test()
        self.model_picker.pause()
        super().reject()

    def _update_hotkey_status(self) -> None:
        if self.hotkey_test_field.toPlainText().strip():
            self.hotkey_status_label.setText("Tutorial text received")
        else:
            self.hotkey_status_label.setText("Waiting for tutorial text")
