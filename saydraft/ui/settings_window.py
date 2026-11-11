"""In-process PySide6 settings window."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.config import load_config, save_config
from saydraft.autostart import WindowsAutoStartManager
from saydraft.paths import resolve_data_path
from saydraft.model_download import download_silero_vad_model
from saydraft.asr.selection import select_model
from saydraft.ui.download_task import DownloadTask, call_download
from saydraft.ui.model_picker import ModelPicker
from saydraft.ui.languages_page import LanguagesPage
from saydraft.asr.router import choose_route

logger = logging.getLogger(__name__)

MODES = ("raw", "balanced", "aggressive")
PROFILES = ("general", "email", "chat", "notes", "code/comments")




def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_project_path(value: str | os.PathLike[str], *, base: Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path if base is not None else resolve_data_path(path)


def find_hotkey_conflicts(hotkeys: dict[str, str]) -> list[str]:
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for name in ("speech", "speech_alternative", "save", "cancel"):
        value = " ".join(str(hotkeys.get(name, "")).lower().split())
        if not value:
            continue
        if value in seen:
            conflicts.append(f"{seen[value]} and {name} both use {value}")
        else:
            seen[value] = name
    return conflicts


class SettingsWindow(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        qt_modules=None,
        config_path: str | os.PathLike[str] | None = None,
        snippets_path: str | os.PathLike[str] | None = None,
        autostart_manager: WindowsAutoStartManager | None = None,
        on_config_applied: Callable[[dict[str, Any]], None] | None = None,
        model_download_callback: Callable[[str, Callable[[int], None]], None] | None = None,
        vad_download_callback=None,
    ):
        super().__init__()
        self.qt = qt_modules
        self.config_path = Path(config_path) if config_path is not None else None
        self.autostart_manager = autostart_manager or WindowsAutoStartManager()
        self.on_config_applied = on_config_applied
        self.model_download_callback = model_download_callback
        self.vad_download_callback = vad_download_callback or download_silero_vad_model
        self._vad_download_task = None
        self.config = load_config(config_path=self.config_path)
        self.snippets_path = Path(snippets_path) if snippets_path is not None else resolve_project_path("snippets.txt")
        self.glossary_path = resolve_project_path(self.config["dictation"]["glossary_path"])
        self.app_profiles_path = resolve_project_path(self.config["dictation"]["app_profiles_path"])

        self.setWindowTitle("Saydraft Settings")
        self.setMinimumSize(760, 560)
        self.tabs = QtWidgets.QTabWidget(self)
        self.status_label = QtWidgets.QLabel("", self)
        self.apply_button = QtWidgets.QPushButton("Apply", self)
        self.close_button = QtWidgets.QPushButton("Close", self)
        self.apply_button.clicked.connect(self.apply_changes)
        self.close_button.clicked.connect(self.close)

        self._build()
        self._load_values()
        self.languages_page.changed.connect(self._sync_language_model)
        self.model_combo.currentIndexChanged.connect(self._use_manual_model)
        self.model_combo.activated.connect(self._use_manual_model)
        self.model_picker.busy_changed.connect(lambda busy: self.languages_page.setEnabled(not busy))
        self._sync_language_model()

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tabs)

        footer = QtWidgets.QHBoxLayout()
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.apply_button)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

        self.tabs.addTab(self._general_tab(), "General")
        self.languages_page = LanguagesPage(self.config)
        self.language_combo = self.languages_page.combos[0]
        self.tabs.addTab(self.languages_page, "Languages")
        self.tabs.addTab(self._cleanup_tab(), "Cleanup")
        self.tabs.addTab(self._dictionary_tab(), "Dictionary")
        self.tabs.addTab(self._snippets_tab(), "Snippets")
        self.tabs.addTab(self._models_tab(), "Models")
        self.tabs.addTab(self._about_tab(), "About")

    def _general_tab(self):
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        self.speech_hotkey_edit = QtWidgets.QLineEdit()
        self.alternative_hotkey_edit = QtWidgets.QLineEdit()
        self.save_hotkey_edit = QtWidgets.QLineEdit()
        self.cancel_hotkey_edit = QtWidgets.QLineEdit()
        self.tap_lock_spin = QtWidgets.QSpinBox()
        self.tap_lock_spin.setRange(100, 2000)
        self.tap_lock_spin.setSuffix(" ms")
        self.autostart_checkbox = QtWidgets.QCheckBox()
        self.auto_listen_checkbox = QtWidgets.QCheckBox()
        self.notification_spin = QtWidgets.QSpinBox()
        self.notification_spin.setRange(1, 30)
        self.notification_spin.setSuffix(" s")
        self.retain_audio_checkbox = QtWidgets.QCheckBox("Save recordings locally for History retries")
        self.retain_audio_checkbox.setToolTip("Off by default. Enabling this retains future recording audio on this computer.")

        form.addRow("Speech hotkey", self.speech_hotkey_edit)
        form.addRow("Alternate hotkey", self.alternative_hotkey_edit)
        form.addRow("Save hotkey", self.save_hotkey_edit)
        form.addRow("Cancel hotkey", self.cancel_hotkey_edit)
        form.addRow("Tap lock threshold", self.tap_lock_spin)
        form.addRow("Start with Windows", self.autostart_checkbox)
        form.addRow("Auto-start listening", self.auto_listen_checkbox)
        form.addRow("Notification duration", self.notification_spin)
        form.addRow("Audio history", self.retain_audio_checkbox)
        return page

    def _cleanup_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(MODES)
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.addItems(PROFILES)
        self.max_seconds_spin = QtWidgets.QSpinBox()
        self.max_seconds_spin.setRange(10, 3600)
        self.max_seconds_spin.setSuffix(" s")
        self.warning_seconds_spin = QtWidgets.QSpinBox()
        self.warning_seconds_spin.setRange(0, 3600)
        self.warning_seconds_spin.setSuffix(" s")
        form.addRow("Cleanup mode", self.mode_combo)
        form.addRow("Default profile", self.profile_combo)
        form.addRow("Recording cap", self.max_seconds_spin)
        form.addRow("Warning time", self.warning_seconds_spin)
        layout.addLayout(form)
        self.app_profiles_editor = QtWidgets.QPlainTextEdit()
        self.app_profiles_editor.setObjectName("appProfilesEditor")
        layout.addWidget(QtWidgets.QLabel("Per-app profile JSON"))
        layout.addWidget(self.app_profiles_editor, 1)
        return page

    def _dictionary_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.dictionary_editor = QtWidgets.QPlainTextEdit()
        self.dictionary_editor.setObjectName("dictionaryEditor")
        layout.addWidget(self.dictionary_editor)
        return page

    def _snippets_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.snippets_editor = QtWidgets.QPlainTextEdit()
        self.snippets_editor.setObjectName("snippetsEditor")
        layout.addWidget(self.snippets_editor)
        return page

    def _models_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        self.model_picker = ModelPicker(self.config, callback=self.model_download_callback)
        self.model_combo = self.model_picker.combo
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.addItems(("cpu", "cuda", "auto"))
        self.compute_combo = QtWidgets.QComboBox()
        self.compute_combo.addItems(("int8", "float16", "float32"))
        self.local_files_checkbox = QtWidgets.QCheckBox()
        self.llm_enabled_checkbox = QtWidgets.QCheckBox()
        self.llm_path_edit = QtWidgets.QLineEdit()
        self.model_progress = self.model_picker.progress
        self.download_button = self.model_picker.download_button
        self.llm_link_button = QtWidgets.QPushButton("Open LLM Link")
        self.llm_link_button.clicked.connect(self.open_llm_download_link)
        self.vad_download_button = QtWidgets.QPushButton("Download speech detection (2.3 MB)")
        self.vad_download_button.clicked.connect(self.download_vad_model)
        self.vad_license = QtWidgets.QLabel('Silero Team · <a href="https://github.com/snakers4/silero-vad/blob/v5.0/LICENSE">MIT license</a>')
        self.vad_license.setOpenExternalLinks(True)
        self.vad_license.setAccessibleName("Silero speech detection model license: MIT")

        form.addRow("Speech model", self.model_picker)
        form.addRow("Device", self.device_combo)
        form.addRow("Compute type", self.compute_combo)
        form.addRow("Use local model files only", self.local_files_checkbox)
        form.addRow("Enable local LLM cleanup", self.llm_enabled_checkbox)
        form.addRow("GGUF model path", self.llm_path_edit)
        form.addRow("LLM model link", self.llm_link_button)
        form.addRow("Speech detection", self.vad_download_button)
        form.addRow("Model license", self.vad_license)
        layout.addLayout(form)
        return page

    def _about_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        label = QtWidgets.QLabel("Saydraft")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setObjectName("aboutTitle")
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def download_vad_model(self):
        if self._vad_download_task is not None or self.model_picker.task is not None:
            return
        task = DownloadTask(self)
        self._vad_download_task = task
        self.vad_download_button.setEnabled(False)
        self.model_picker.setEnabled(False)
        self.model_progress.setValue(0)
        self.status_label.setText("Downloading speech detection…")
        task.progress.connect(self.model_progress.setValue)
        task.succeeded.connect(lambda path: self.status_label.setText("Speech detection ready. Apply Settings to use it."))
        task.failed.connect(lambda error: self.status_label.setText(f"Could not download speech detection: {error}"))
        task.paused.connect(self.status_label.setText)
        task.finished.connect(self._finish_vad_download)
        task.finished.connect(task.deleteLater)
        task.start(lambda progress: call_download(self.vad_download_callback, progress,
                                                   pause_event=task.pause_event))

    def _finish_vad_download(self):
        self.vad_download_button.setEnabled(True)
        self.model_picker.setEnabled(True)
        self._vad_download_task = None

    def _load_values(self) -> None:
        cfg = self.config
        self.speech_hotkey_edit.setText(cfg["hotkeys"]["speech"])
        self.alternative_hotkey_edit.setText(cfg["hotkeys"]["speech_alternative"])
        self.save_hotkey_edit.setText(cfg["hotkeys"]["save"])
        self.cancel_hotkey_edit.setText(cfg["hotkeys"]["cancel"])
        self.tap_lock_spin.setValue(int(cfg["hotkeys"]["tap_lock_ms"]))
        self.autostart_checkbox.setChecked(bool(cfg["app"]["start_with_windows"] or self.autostart_manager.is_enabled()))
        self.auto_listen_checkbox.setChecked(bool(cfg["app"]["auto_start_listening"]))
        self.notification_spin.setValue(int(cfg["app"]["notification_duration"]))
        self.retain_audio_checkbox.setChecked(cfg["recording"].get("retain_audio", False))
        self._set_combo(self.mode_combo, cfg["dictation"]["mode"])
        self._set_combo(self.profile_combo, cfg["dictation"]["profile"])
        self.max_seconds_spin.setValue(int(cfg["recording"]["max_seconds"]))
        self.warning_seconds_spin.setValue(int(cfg["recording"]["warning_seconds"]))
        self._set_combo(self.device_combo, cfg["stt"]["device"])
        self._set_combo(self.compute_combo, cfg["stt"]["compute_type"])
        self.local_files_checkbox.setChecked(bool(cfg["stt"]["local_files_only"]))
        self.llm_enabled_checkbox.setChecked(bool(cfg["llm"]["enabled"]))
        self.llm_path_edit.setText(cfg["llm"]["model_path"])
        self.dictionary_editor.setPlainText(self._read_text(self.glossary_path, default='{"user_terms": [], "protected_terms": [], "replacements": {}}\n'))
        self.snippets_editor.setPlainText(self._read_text(self.snippets_path))
        self.app_profiles_editor.setPlainText(self._read_text(self.app_profiles_path, default="[]\n"))

    def _set_combo(self, combo: QtWidgets.QComboBox, value: str) -> None:
        if combo.findText(value) < 0:
            combo.addItem(value)
        combo.setCurrentText(value)

    def apply_changes(self) -> bool:
        try:
            cfg = self._collect_config()
            conflicts = find_hotkey_conflicts(cfg["hotkeys"])
            if conflicts:
                self.status_label.setText("Hotkey conflict: " + "; ".join(conflicts))
                return False

            dictionary = self._parse_json_editor(self.dictionary_editor, dict, "Dictionary")
            profiles = self._parse_json_editor(self.app_profiles_editor, list, "Per-app profiles")
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return False

        saved = save_config(cfg, self.config_path)
        self._write_json(self.glossary_path, dictionary)
        self._write_text(self.snippets_path, self._normalized_plain_text(self.snippets_editor))
        self._write_json(self.app_profiles_path, profiles)
        self.autostart_manager.set_enabled(saved["app"]["start_with_windows"])
        self.config = saved
        if self.on_config_applied is not None:
            self.on_config_applied(saved)
        self.status_label.setText("Saved")
        return True

    def _collect_config(self) -> dict[str, Any]:
        cfg = json.loads(json.dumps(self.config))
        cfg["hotkeys"]["speech"] = self.speech_hotkey_edit.text().strip()
        cfg["hotkeys"]["speech_alternative"] = self.alternative_hotkey_edit.text().strip()
        cfg["hotkeys"]["save"] = self.save_hotkey_edit.text().strip()
        cfg["hotkeys"]["cancel"] = self.cancel_hotkey_edit.text().strip()
        cfg["hotkeys"]["tap_lock_ms"] = int(self.tap_lock_spin.value())
        cfg["app"]["start_with_windows"] = bool(self.autostart_checkbox.isChecked())
        cfg["app"]["auto_start_listening"] = bool(self.auto_listen_checkbox.isChecked())
        cfg["app"]["notification_duration"] = int(self.notification_spin.value())
        cfg["recording"]["max_seconds"] = int(self.max_seconds_spin.value())
        cfg["recording"]["retain_audio"] = self.retain_audio_checkbox.isChecked()
        cfg["recording"]["warning_seconds"] = int(self.warning_seconds_spin.value())
        cfg["dictation"]["mode"] = self.mode_combo.currentText()
        cfg["dictation"]["profile"] = self.profile_combo.currentText()
        select_model(cfg, self.model_picker.model_id, manual=False)
        self.languages_page.apply_to(cfg)
        cfg["stt"]["device"] = self.device_combo.currentText()
        cfg["stt"]["compute_type"] = self.compute_combo.currentText()
        cfg["stt"]["local_files_only"] = bool(self.local_files_checkbox.isChecked())
        cfg["llm"]["enabled"] = bool(self.llm_enabled_checkbox.isChecked())
        cfg["llm"]["model_path"] = self.llm_path_edit.text().strip()
        return cfg

    def _sync_language_model(self):
        if not self.languages_page.routing.isChecked() or self.model_picker.task is not None:
            return
        route = choose_route(self.languages_page.pins(),
                             english_max=self.languages_page.english_max.isChecked())
        index = self.model_combo.findData(route.model_id)
        if index >= 0:
            self.model_combo.blockSignals(True)
            self.model_combo.setCurrentIndex(index)
            self.model_combo.blockSignals(False)
            self.model_picker.update_license()

    def _use_manual_model(self):
        self.languages_page.routing.setChecked(False)

    def download_selected_model(self) -> None:
        if self._vad_download_task is None:
            self.model_picker.start_download()

    def closeEvent(self, event):
        self.model_picker.pause()
        if self._vad_download_task is not None:
            self._vad_download_task.pause()
        super().closeEvent(event)

    def open_llm_download_link(self) -> None:
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl("https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF")
        )

    def show_tab(self, tab_name: str | None) -> None:
        if not tab_name:
            return
        target = str(tab_name).strip().lower()
        aliases = {"llm": "models", "model": "models", "help": "about"}
        target = aliases.get(target, target)
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index).lower() == target:
                self.tabs.setCurrentIndex(index)
                return

    def _parse_json_editor(self, editor: QtWidgets.QPlainTextEdit, expected_type: type, label: str):
        try:
            value = json.loads(editor.toPlainText() or "null")
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} JSON error: {exc.msg}") from exc
        if not isinstance(value, expected_type):
            raise ValueError(f"{label} must be {expected_type.__name__}")
        return value

    def _read_text(self, path: Path, default: str = "") -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return default

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_json(self, path: Path, value: Any) -> None:
        self._write_text(path, json.dumps(value, indent=2) + "\n")

    def _normalized_plain_text(self, editor: QtWidgets.QPlainTextEdit) -> str:
        text = editor.toPlainText().rstrip()
        return text + "\n" if text else ""
