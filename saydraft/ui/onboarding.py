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
from saydraft.ui.onboarding_models import OnboardingModelsPage
from saydraft.ui.onboarding_shortcuts import OnboardingShortcutsPage
from saydraft.ui.onboarding_practice import OnboardingPracticePage
from saydraft.ui.onboarding_style import OnboardingStylePage


class OnboardingWizard(QtWidgets.QWizard):
    PAGE_WELCOME = 0
    PAGE_MIC = 1
    PAGE_MODEL = 2
    PAGE_HOTKEY = 3
    PAGE_PRACTICE = 4
    PAGE_STYLE = PAGE_DONE = 5

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
        model_hardware_probe=None,
        model_status_provider=None,
        shortcut_start_callback=None,
        shortcut_cancel_callback=None,
        shortcut_conflict_detector=None,
        practice_open_callback=None,
        practice_start_callback=None,
        practice_stop_callback=None,
        practice_close_callback=None,
    ):
        super().__init__()
        self.qt = qt_modules
        self.config_path = Path(config_path) if config_path is not None else None
        self.on_config_applied = on_config_applied
        self.model_download_callback = model_download_callback
        self.microphone_start_callback = microphone_start_callback
        self.microphone_stop_callback = microphone_stop_callback
        self.microphone_devices_provider = microphone_devices_provider
        self.model_hardware_probe = model_hardware_probe
        self.model_status_provider = model_status_provider
        self.shortcut_start_callback = shortcut_start_callback
        self.shortcut_cancel_callback = shortcut_cancel_callback
        self.shortcut_conflict_detector = shortcut_conflict_detector
        self.practice_callbacks = dict(open_callback=practice_open_callback, start_callback=practice_start_callback,
            stop_callback=practice_stop_callback, close_callback=practice_close_callback)
        self.config = load_config(config_path=self.config_path)
        self._completed = False
        # Saved preferences, rather than an optional display hint, own the staged binding.
        self.hotkey_hint = str(self.config["hotkeys"]["speech"]).upper()

        self.setWindowTitle("Saydraft Setup")
        self.setWizardStyle(QtWidgets.QWizard.ModernStyle)
        self.setMinimumSize(640, 440)
        self.setOption(QtWidgets.QWizard.NoBackButtonOnStartPage, True)

        self.addPage(self._welcome_page())
        self.addPage(self._microphone_page())
        self.addPage(self._model_page())
        self.addPage(self._hotkey_page())
        self.practice_page = OnboardingPracticePage(config_provider=self.practice_config, **self.practice_callbacks)
        self.addPage(self.practice_page)
        self.style_page = OnboardingStylePage(self.config, sample_provider=self.practice_page.last_raw,
            ready_callback=lambda: not self.practice_page._generation and not self.practice_page._cleanup_failed)
        self.finish_status_label = self.style_page.status
        self.addPage(self.style_page)
        self.practice_page.settled.connect(self._practice_settled)

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
        subtitle = QtWidgets.QLabel("Your voice never leaves this PC.")
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
        page = OnboardingModelsPage(self.config, download_callback=self.model_download_callback,
            hardware_probe=self.model_hardware_probe, status_provider=self.model_status_provider)
        self.models_page = page
        self.model_picker = page.picker
        self.model_combo = self.model_picker.combo
        self.model_progress = self.model_picker.progress
        self.download_button = self.model_picker.download_button
        self.model_status_label = self.model_picker.status
        return page

    def _hotkey_page(self) -> QtWidgets.QWizardPage:
        self.shortcuts_page = OnboardingShortcutsPage(self.config,
            start_callback=self.shortcut_start_callback, cancel_callback=self.shortcut_cancel_callback,
            conflict_detector=self.shortcut_conflict_detector)
        return self.shortcuts_page

    def practice_config(self):
        config = load_config(config_path=self.config_path)
        config['hotkeys'] = self.shortcuts_page.merge_changes(config['hotkeys'])
        if self.model_picker.model_id != configured_model_id(self.config):
            select_model(config, self.model_picker.model_id, manual=True)
        selected = self.microphone_page.selection
        if selected != InputSelection.from_config(self.config):
            config['recording'].update(input_device=selected.name, input_hostapi=selected.hostapi)
        config['dictation']['styles'] = self.style_page.merge_changes(config['dictation'].get('styles', {}))
        return config

    def _practice_settled(self):
        self.finish_status_label.setText('Restart Saydraft before completing setup; practice cleanup could not be confirmed.'
            if self.practice_page._cleanup_failed else 'Finish to save your choices and open Home.')
        if self.currentPage() is self.style_page:
            self.style_page.completeChanged.emit()

    def download_selected_model(self) -> None:
        self.model_picker.start_download()

    def update_model_download_progress(self, value: int) -> None:
        self.model_progress.setValue(max(0, min(100, int(value))))

    def finish_onboarding(self) -> bool:
        if self._completed:
            return True
        self.microphone_page.stop_test()
        self.shortcuts_page.cancel_learning()
        self.practice_page.stop_session()
        if self.practice_page._cleanup_failed:
            self.finish_status_label.setText('Restart Saydraft before completing setup; practice cleanup could not be confirmed.')
            return False
        if self.practice_page._generation:
            self.finish_status_label.setText('Practice is still stopping. Wait for its microphone and shortcuts to retire, then choose Finish again.')
            return False
        if self.shortcuts_page.learning:
            self.finish_status_label.setText("Wait for shortcut learning to stop before finishing setup.")
            return False
        try:
            # Merge only setup edits into the latest saved preferences. An open
            # Hub can save unrelated settings while the wizard is still visible.
            cfg = load_config(config_path=self.config_path)
            try:
                cfg["hotkeys"] = self.shortcuts_page.merge_changes(cfg["hotkeys"])
            except ValueError:
                self.finish_status_label.setText("Shortcut settings changed or conflict. Review the Shortcut step before finishing.")
                return False
            cfg["app"]["onboarded"] = True
            cfg['dictation']['styles'] = self.style_page.merge_changes(cfg['dictation'].get('styles', {}))
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
        self.finish_status_label.setText("Setup saved. Opening Home. A compatible installed speech model is required for dictation.")
        if self.on_config_applied is not None:
            self.on_config_applied(saved)
        return True

    def accept(self) -> None:
        if self.finish_onboarding():
            self.model_picker.pause()
            super().accept()

    def reject(self) -> None:
        self.microphone_page.stop_test()
        self.shortcuts_page.cancel_learning()
        self.practice_page.stop_session()
        self.models_page.cancel_checks()
        self.model_picker.pause()
        super().reject()
