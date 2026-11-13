"""First-run PySide6 onboarding wizard."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.config import load_config, save_config
from saydraft.audio.devices import InputSelection
from saydraft.asr.selection import select_model
from saydraft.models.setup import setup_model_id
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
        model_benchmark_callback=None,
        model_benchmark_cancel_callback=None,
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
        self.model_benchmark_callback = model_benchmark_callback
        self.model_benchmark_cancel_callback = model_benchmark_cancel_callback
        self.shortcut_start_callback = shortcut_start_callback
        self.shortcut_cancel_callback = shortcut_cancel_callback
        self.shortcut_conflict_detector = shortcut_conflict_detector
        self.practice_callbacks = dict(open_callback=practice_open_callback, start_callback=practice_start_callback,
            stop_callback=practice_stop_callback, close_callback=practice_close_callback)
        self.config = load_config(config_path=self.config_path)
        self._completed = False
        self._finish_generation = 0
        self._dismissed = False
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
            ready_callback=lambda: not self.practice_page._generation and not self.practice_page._cleanup_failed
                and not self.models_page.benchmark_active and not self._finish_generation
                and not self.shortcuts_page.learning, waiting_status=self._finish_guidance)
        self.finish_status_label = self.style_page.status
        self.addPage(self.style_page)
        self.practice_page.settled.connect(self._practice_settled)
        self.models_page.benchmark_settled.connect(self._practice_settled)
        self.models_page.finish_checked.connect(self._finish_readiness)
        self.shortcuts_page.completeChanged.connect(self._practice_settled)

        self.title_timer = QtCore.QTimer(self)
        self.title_timer.setSingleShot(True)
        self.title_timer.timeout.connect(self._refresh_title_font)
        self.currentIdChanged.connect(lambda _page: self.title_timer.start(0))
        self.currentIdChanged.connect(self._cancel_finish_on_navigation)
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
            hardware_probe=self.model_hardware_probe, status_provider=self.model_status_provider,
            benchmark_callback=self.model_benchmark_callback, benchmark_cancel_callback=self.model_benchmark_cancel_callback,
            config_provider=self.practice_config,
            benchmark_directory=self.config_path.parent / 'hardware-benchmarks' if self.config_path else None)
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
        if self.model_picker.model_id != self.models_page.initial_model_id:
            select_model(config, self.model_picker.model_id, manual=True)
        selected = self.microphone_page.selection
        if selected != InputSelection.from_config(self.config):
            config['recording'].update(input_device=selected.name, input_hostapi=selected.hostapi)
        config['dictation']['styles'] = self.style_page.merge_changes(config['dictation'].get('styles', {}))
        return config

    def _finish_guidance(self):
        return ('Restart Saydraft before completing setup; practice cleanup could not be confirmed.'
            if self.practice_page._cleanup_failed else 'Checking current model files before saving setup…'
            if self._finish_generation else 'Performance check is stopping. Wait before finishing setup.'
            if self.models_page.benchmark_active else 'Wait for shortcut learning to stop before finishing setup.'
            if self.shortcuts_page.learning else 'Practice is stopping. Wait before finishing setup.'
            if self.practice_page._generation else 'Finish to save your choices and open Home.')

    def _practice_settled(self):
        self.finish_status_label.setText(self._finish_guidance())
        if self.currentPage() is self.style_page:
            self.style_page.completeChanged.emit()

    def download_selected_model(self) -> None:
        self.model_picker.start_download()

    def update_model_download_progress(self, value: int) -> None:
        self.model_progress.setValue(max(0, min(100, int(value))))

    def finish_onboarding(self) -> bool:
        if self._completed:
            return True
        if self._dismissed or self._finish_generation:
            return False
        self.microphone_page.stop_test()
        self.shortcuts_page.cancel_learning()
        self.practice_page.stop_session()
        self.models_page.cancel_benchmark()
        if self.models_page.benchmark_active:
            self.finish_status_label.setText('Performance check is still stopping. Wait for it to finish, then choose Finish again.')
            return False
        if self.practice_page._cleanup_failed:
            self.finish_status_label.setText('Restart Saydraft before completing setup; practice cleanup could not be confirmed.')
            return False
        if self.practice_page._generation:
            self.finish_status_label.setText('Practice is still stopping. Wait for its microphone and shortcuts to retire, then choose Finish again.')
            return False
        if self.shortcuts_page.learning:
            self.finish_status_label.setText("Wait for shortcut learning to stop before finishing setup.")
            return False
        if self.model_picker.task is not None:
            self.finish_status_label.setText('Model download is still running. Wait for installation to finish before completing setup.')
            return False
        try:
            cfg = self.practice_config()
            model_id = setup_model_id(cfg)
            self._finish_generation = self.models_page.verify_for_finish(model_id)
        except ValueError:
            self.finish_status_label.setText('Setup settings changed or conflict. Review the Shortcut and model steps before finishing.')
            return False
        except OSError:
            self.finish_status_label.setText('Could not read setup preferences. Check your configuration folder and try again.')
            return False
        if not self._finish_generation:
            self.finish_status_label.setText('Could not start the model check. Return to Set up models and try again.')
            return False
        self._practice_settled()
        return False  # The queued result, not the button callback, can authorize saving.

    @QtCore.Slot(int, str, object)
    def _finish_readiness(self, generation, model_id, result):
        if generation != self._finish_generation or self._dismissed or self._completed:
            return
        self._finish_generation = 0
        self._practice_settled()
        if (not isinstance(result, dict) or result.get('state') not in ('verified', 'compatible')):
            self.finish_status_label.setText('The selected speech model is not ready. Return to Set up models to install or check it. Your preferences have not been saved.')
            return
        if (self.practice_page._generation or self.practice_page._cleanup_failed
                or self.models_page.benchmark_active or self.shortcuts_page.learning):
            self.finish_status_label.setText('Setup work is still active. Wait for it to stop, then choose Finish again.')
            return
        try:
            # Re-merge current preferences after the asynchronous file check.
            cfg = self.practice_config()
            if setup_model_id(cfg) != model_id:
                self.finish_status_label.setText('Speech settings changed during the check. Review Set up models, then choose Finish again.')
                return
        except (OSError, ValueError):
            self.finish_status_label.setText('Setup settings changed or could not be read. Review your choices before finishing.')
            return
        if self._save_onboarding(cfg):
            self.model_picker.pause()
            super().accept()

    def _save_onboarding(self, cfg):
        try:
            cfg['app']['onboarded'] = True
            saved = save_config(cfg, self.config_path)
        except (OSError, ValueError):
            self.finish_status_label.setText("Could not save setup. Check your configuration folder and try Finish again.")
            return False
        self.config = saved
        self._completed = True
        self.finish_status_label.setText('Setup saved. Opening Home.')
        if self.on_config_applied is not None:
            self.on_config_applied(saved)
        return True

    def accept(self) -> None:
        if self._completed:
            super().accept()
        else:
            self.finish_onboarding()

    def _cancel_finish(self):
        self._finish_generation = 0
        self.models_page.cancel_finish_check()

    def _cancel_finish_on_navigation(self, _page):
        if self._finish_generation:
            self._cancel_finish()

    def showEvent(self, event):
        self._dismissed = False
        super().showEvent(event)
        if self.currentPage() is self.style_page:
            self._practice_settled()

    def hideEvent(self, event):
        if self._finish_generation and not self._completed:
            self._cancel_finish()
        super().hideEvent(event)

    def reject(self) -> None:
        self._dismissed = True
        self._cancel_finish()
        self.microphone_page.stop_test()
        self.shortcuts_page.cancel_learning()
        self.practice_page.stop_session()
        self.models_page.cancel_checks()
        self.model_picker.pause()
        super().reject()
