"""Shared Settings controls hosted by the Saydraft Hub."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.config import load_config, save_config
from saydraft.dictionary.store import read_dictionary, save_dictionary
from saydraft.autostart import WindowsAutoStartManager
from saydraft.paths import resolve_data_path
from saydraft.model_download import download_silero_vad_model
from saydraft.asr.selection import select_model
from saydraft.ui.download_task import DownloadTask, call_download
from saydraft.ui.model_picker import ModelPicker
from saydraft.ui.cleanup_picker import CleanupPicker
from saydraft.ui.languages_page import LanguagesPage
from saydraft.ui.hardware_page import HardwarePage
from saydraft.ui.labs_page import LabsPage
from saydraft.ui.styles_page import StylesPage
from saydraft.ui.dictionary_page import DictionaryPage
from saydraft.dictation.glossary import load_glossary
from saydraft.models.hardware import latest_report
from saydraft.asr.router import choose_route
from saydraft.hotkeys.wispr import shortcut_warning, wispr_running

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
    from saydraft.hotkeys.recording import recording_bindings
    keys = {name: hotkeys[name] for name in ("speech", "speech_alternative", "speech_mouse", "hands_free")
            if hotkeys.get(name, "").strip()}
    if not keys:
        return ["Enter at least one recording shortcut"]
    try:
        recording_bindings(keys, cancel_key=hotkeys.get("cancel", ""), save_key=hotkeys.get("save", ""),
                           paste_key=hotkeys.get("paste_last", ""))
    except ValueError as exc:
        return [str(exc)]
    return []


class SettingsPage(QtWidgets.QWidget):
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
        hardware_benchmark_callback=None,
        preview_download_callback=None,
        cleanup_download_callback=None,
        cleanup_runtime_download_callback=None,
        style_preview_callback=None,
        style_glossary_provider=None,
    ):
        super().__init__()
        self.qt = qt_modules
        self.config_path = Path(config_path) if config_path is not None else None
        self.autostart_manager = autostart_manager or WindowsAutoStartManager()
        self.on_config_applied = on_config_applied
        self.model_download_callback = model_download_callback
        self.vad_download_callback = vad_download_callback or download_silero_vad_model
        self.hardware_benchmark_callback = hardware_benchmark_callback
        self.preview_download_callback = preview_download_callback
        self.cleanup_download_callback = cleanup_download_callback
        self.cleanup_runtime_download_callback = cleanup_runtime_download_callback
        self.style_preview_callback = style_preview_callback
        self.style_glossary_provider = style_glossary_provider
        self._vad_download_task = None
        self.config = load_config(config_path=self.config_path)
        self.snippets_path = Path(snippets_path) if snippets_path is not None else resolve_project_path("snippets.txt")
        self.glossary_path = resolve_project_path(self.config["dictation"]["glossary_path"])
        self.app_profiles_path = resolve_project_path(self.config["dictation"]["app_profiles_path"])

        self.setAccessibleName("Saydraft Settings")
        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.tabBar().hide()
        self.section_combo = QtWidgets.QComboBox(self)
        self.section_combo.setAccessibleName("Settings section")
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setTextFormat(QtCore.Qt.PlainText)
        self.apply_button = QtWidgets.QPushButton("Apply", self)
        self.close_button = QtWidgets.QPushButton("Close", self)
        self.apply_button.clicked.connect(self.apply_changes)
        self.close_button.clicked.connect(lambda: self.window().close())

        self._build()
        self.section_combo.currentIndexChanged.connect(self.tabs.setCurrentIndex)
        self.tabs.currentChanged.connect(self._sync_section_index)
        self._load_values()
        for signal in (self.mode_combo.currentIndexChanged, self.profile_combo.currentIndexChanged,
                self.drop_message_period_checkbox.toggled, self.voice_enter_checkbox.toggled,
                self.app_profiles_editor.textChanged, self.snippets_editor.textChanged):
            signal.connect(self.styles_page.invalidate)
        self._refresh_shortcut_warning()
        self.languages_page.changed.connect(self._sync_language_model)
        self.languages_page.changed.connect(self.refresh_labs)
        self.model_combo.currentIndexChanged.connect(self._use_manual_model)
        self.model_combo.activated.connect(self._use_manual_model)
        self.model_picker.busy_changed.connect(lambda busy: self.languages_page.setEnabled(not busy))
        self._sync_language_model()
        self.tabs.currentChanged.connect(lambda index: self.refresh_labs())
        self.tabs.currentChanged.connect(lambda index: self._refresh_shortcut_warning() if self.tabs.tabText(index) == "Shortcuts" else None)

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        navigation = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel("Settings")
        label.setProperty("role", "eyebrow")
        navigation.addWidget(label)
        navigation.addWidget(self.section_combo, 1)
        layout.addLayout(navigation)
        layout.addWidget(self.tabs)

        footer = QtWidgets.QHBoxLayout()
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.apply_button)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

        self._add_tab(self._general_tab(), "General")
        self._add_tab(self._shortcuts_tab(), "Shortcuts")
        self.languages_page = LanguagesPage(self.config)
        self.language_combo = self.languages_page.combos[0]
        self._add_tab(self.languages_page, "Languages")
        self._add_tab(self._cleanup_tab(), "Cleanup")
        self.styles_page = StylesPage(self.config, config_provider=self._collect_config,
            profiles_provider=lambda: self._parse_json_editor(self.app_profiles_editor, list, "Per-app profiles"),
            snippets_provider=lambda: self.snippets_editor.toPlainText(), callback=self.style_preview_callback,
            glossary_provider=self.style_glossary_provider or (lambda: load_glossary(self.glossary_path)))
        self._add_tab(self.styles_page, "Style")
        self._add_tab(self._dictionary_tab(), "Dictionary")
        self._add_tab(self._snippets_tab(), "Snippets")
        self._add_tab(self._models_tab(), "Models")
        self.hardware_page = HardwarePage(callback=self.hardware_benchmark_callback,
            directory=self.config_path.parent / "hardware-benchmarks" if self.config_path else None)
        self._add_tab(self.hardware_page, "Performance")
        self.labs_page = LabsPage(self.config, callback=self.preview_download_callback,
            report_loader=lambda: latest_report(self.config_path.parent / "hardware-benchmarks" if self.config_path else None))
        self._add_tab(self.labs_page, "Labs")
        self.microphone_page = self._microphone_tab()
        self._add_tab(self.microphone_page, "Microphone")
        self._add_tab(self._privacy_tab(), "Privacy")
        self._add_tab(self._about_tab(), "About")
        self.sync_sections()

    def _add_tab(self, page, name):
        if not isinstance(page, QtWidgets.QAbstractScrollArea):
            page = self._scroll(page)
        self.tabs.addTab(page, name)

    def sync_sections(self):
        self.section_combo.blockSignals(True)
        self.section_combo.clear()
        self.section_combo.addItems([self.tabs.tabText(index) for index in range(self.tabs.count())])
        self.section_combo.setCurrentIndex(self.tabs.currentIndex())
        self.section_combo.blockSignals(False)

    def _sync_section_index(self, index):
        self.section_combo.blockSignals(True)
        self.section_combo.setCurrentIndex(index)
        self.section_combo.blockSignals(False)

    def _general_tab(self):
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        self.autostart_checkbox = QtWidgets.QCheckBox()
        self.auto_listen_checkbox = QtWidgets.QCheckBox()
        self.show_bar_checkbox = QtWidgets.QCheckBox("Show the idle Saydraft Bar")
        self.start_sound_checkbox = QtWidgets.QCheckBox("Play a tick when recording starts")
        self.end_sound_checkbox = QtWidgets.QCheckBox("Play a soft tick after insertion")
        self.notification_spin = QtWidgets.QSpinBox()
        self.notification_spin.setRange(1, 30)
        self.notification_spin.setSuffix(" s")
        self.retain_audio_checkbox = QtWidgets.QCheckBox("Save recordings locally for History retries")
        self.retain_audio_checkbox.setToolTip("Off by default. Enabling this retains future recording audio on this computer.")
        form.addRow("Start with Windows", self.autostart_checkbox)
        form.addRow("Auto-start listening", self.auto_listen_checkbox)
        form.addRow("Saydraft Bar", self.show_bar_checkbox)
        form.addRow("Start sound", self.start_sound_checkbox)
        form.addRow("End sound", self.end_sound_checkbox)
        form.addRow("Notification duration", self.notification_spin)
        return self._scroll(page)

    @staticmethod
    def _scroll(page):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _shortcuts_tab(self):
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        self.speech_hotkey_edit = QtWidgets.QLineEdit()
        self.alternative_hotkey_edit = QtWidgets.QLineEdit()
        self.mouse_hotkey_edit = QtWidgets.QLineEdit()
        self.mouse_hotkey_edit.setPlaceholderText("xbutton1, xbutton2, middle_mouse; blank disables")
        self.mouse_hotkey_edit.setToolTip("Hold a mouse button to dictate. Leave blank to disable this binding.")
        self.hands_free_hotkey_edit = QtWidgets.QLineEdit()
        self.hands_free_hotkey_edit.setPlaceholderText("ctrl+win+space; blank disables")
        self.hands_free_hotkey_edit.setToolTip("Toggle hands-free recording. The recording shortcut finishes it; Esc cancels it.")
        self.paste_last_hotkey_edit = QtWidgets.QLineEdit()
        self.paste_last_hotkey_edit.setPlaceholderText("shift+alt+z; blank disables")
        self.paste_last_hotkey_edit.setToolTip("Paste the latest saved transcript into the current field after releasing the shortcut.")
        self.save_hotkey_edit = QtWidgets.QLineEdit()
        self.cancel_hotkey_edit = QtWidgets.QLineEdit()
        self.tap_lock_spin = QtWidgets.QSpinBox()
        self.tap_lock_spin.setRange(0, 2000)
        self.tap_lock_spin.setSpecialValueText("Disabled")
        self.tap_lock_spin.setToolTip("Two taps of the same recording shortcut lock hands-free mode. "
                                     "Each tap must be shorter than 300 ms. Zero disables double-tap.")
        self.tap_lock_spin.setSuffix(" ms")
        form.addRow("Speech hotkey", self.speech_hotkey_edit)
        form.addRow("Alternate hotkey", self.alternative_hotkey_edit)
        form.addRow("Mouse recording shortcut", self.mouse_hotkey_edit)
        form.addRow("Hands-free shortcut", self.hands_free_hotkey_edit)
        form.addRow("Paste last transcript", self.paste_last_hotkey_edit)
        self.shortcut_warning_label = QtWidgets.QLabel()
        self.shortcut_warning_label.setWordWrap(True)
        form.addRow(self.shortcut_warning_label)
        for edit in (self.speech_hotkey_edit, self.alternative_hotkey_edit, self.mouse_hotkey_edit,
                     self.hands_free_hotkey_edit, self.paste_last_hotkey_edit, self.save_hotkey_edit, self.cancel_hotkey_edit):
            edit.textChanged.connect(lambda text: self._show_shortcut_warning())
        form.addRow("Save hotkey", self.save_hotkey_edit)
        form.addRow("Cancel hotkey", self.cancel_hotkey_edit)
        hotkey_help = QtWidgets.QLabel(
            'Hotkeys may be unavailable in admin windows. '
            f'<a href="{QtCore.QUrl.fromLocalFile(str(project_root() / "docs" / "HOTKEYS.md")).toString()}">'
            'Shortcut help</a>')
        hotkey_help.setWordWrap(True)
        hotkey_help.setOpenExternalLinks(True)
        form.addRow(hotkey_help)
        form.addRow("Double-tap interval", self.tap_lock_spin)
        return self._scroll(page)

    def _microphone_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        title = QtWidgets.QLabel("Microphone")
        title.setProperty("role", "display")
        layout.addWidget(title)
        help_text = QtWidgets.QLabel("Saydraft uses the default Windows input. Connect a microphone, then choose it as your default input in Windows sound settings. If access is blocked, allow desktop apps in Windows microphone privacy settings.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        sound = QtWidgets.QPushButton("Open Windows sound settings")
        sound.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl("ms-settings:sound")))
        privacy = QtWidgets.QPushButton("Open microphone privacy settings")
        privacy.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl("ms-settings:privacy-microphone")))
        layout.addWidget(sound)
        layout.addWidget(privacy)
        layout.addStretch()
        return page

    def _privacy_tab(self):
        from saydraft.privacy.netguard import NetworkGuard

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        heading = QtWidgets.QLabel("Your words stay on your machine.")
        heading.setProperty("role", "display")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        self.privacy_status = QtWidgets.QLabel()
        self.privacy_status.setWordWrap(True)
        layout.addWidget(self.privacy_status)
        explanation = QtWidgets.QLabel("Dictation and cleanup run locally. History, dictionary and retained audio stay on this PC. "
            "Model downloads happen only when you request them. Telemetry is disabled.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addWidget(self.retain_audio_checkbox)
        note = QtWidgets.QLabel("Audio history is off by default. Turning it on retains future recordings for recognition retry.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self.privacy_status.setText("Offline mode active" if NetworkGuard.is_installed() else "Offline policy unavailable")
        return self._scroll(page)

    def refresh_privacy(self):
        from saydraft.privacy.netguard import NetworkGuard
        self.privacy_status.setText("Offline mode active" if NetworkGuard.is_installed() else "Offline policy unavailable")

    def _cleanup_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(MODES)
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.addItems(PROFILES)
        self.drop_message_period_checkbox = QtWidgets.QCheckBox("Omit the final period in single-sentence messages")
        self.drop_message_period_checkbox.setToolTip(
            "Applies to Messages and Work-chat, or the chat profile. Questions and multi-sentence messages keep punctuation.")
        self.voice_enter_checkbox = QtWidgets.QCheckBox('Allow trailing “press enter” to send Enter after dictation')
        self.voice_enter_checkbox.setToolTip(
            "Off by default. End your dictation with the words “press enter”. Never runs in Email or Docs (including Notes). "
            "Raw and Code also use this command when enabled.")
        self.max_seconds_spin = QtWidgets.QSpinBox()
        self.max_seconds_spin.setRange(10, 3600)
        self.max_seconds_spin.setSuffix(" s")
        self.warning_seconds_spin = QtWidgets.QSpinBox()
        self.warning_seconds_spin.setRange(0, 3600)
        self.warning_seconds_spin.setSuffix(" s")
        form.addRow("Cleanup mode", self.mode_combo)
        form.addRow("Default profile", self.profile_combo)
        form.addRow("Messaging", self.drop_message_period_checkbox)
        form.addRow("Voice command", self.voice_enter_checkbox)
        form.addRow("Recording cap", self.max_seconds_spin)
        form.addRow("Warning time", self.warning_seconds_spin)
        layout.addLayout(form)
        self.app_profiles_editor = QtWidgets.QPlainTextEdit()
        self.app_profiles_editor.setObjectName("appProfilesEditor")
        self.app_profiles_editor.setToolTip('App group override: {"exe":"notepad.exe","app_group":"docs"}. '
                                           'Optional "site" matches a browser title hint.')
        layout.addWidget(QtWidgets.QLabel("Per-app profile JSON"))
        layout.addWidget(self.app_profiles_editor, 1)
        return page

    def _dictionary_tab(self):
        self.dictionary_page = DictionaryPage(self.glossary_path)
        self.learn_corrections_checkbox = self.dictionary_page.learn_checkbox
        self.auto_add_dictionary_checkbox = self.dictionary_page.auto_add_checkbox
        self.dictionary_editor = self.dictionary_page.json_editor
        self.reload_dictionary_button = self.dictionary_page.reload_button
        self.dictionary_page.reload_requested.connect(self.reload_dictionary)
        self.dictionary_page.status_changed.connect(self.status_label.setText)
        return self.dictionary_page

    def reload_dictionary(self):
        try:
            snapshot = read_dictionary(self.glossary_path)
        except (OSError, ValueError):
            self.status_label.setText("Could not reload Dictionary. Repair its JSON on disk, then reload.")
            return False
        self._dictionary_snapshot = snapshot
        self.dictionary_page.set_snapshot(snapshot)
        self.status_label.setText("Dictionary reloaded")
        return True

    def refresh_dictionary(self, _change=None):
        if self.dictionary_page.dirty:
            self.dictionary_page.note("Saved Dictionary changed. Your staged edits are kept; reload before saving them.")
            return False
        return self.reload_dictionary()

    def _snippets_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.snippets_editor = QtWidgets.QPlainTextEdit()
        self.snippets_editor.setObjectName("snippetsEditor")
        layout.addWidget(self.snippets_editor)
        return page

    def _models_tab(self):
        page = QtWidgets.QScrollArea()
        page.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        page.setWidget(content)
        layout = QtWidgets.QVBoxLayout(content)
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
        self.cleanup_picker = CleanupPicker(self.config, callback=self.cleanup_download_callback,
            runtime_callback=self.cleanup_runtime_download_callback,
            report=latest_report(self.config_path.parent / "hardware-benchmarks" if self.config_path else None))
        self.cleanup_picker.ready.connect(self._cleanup_model_ready)
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
        form.addRow("AI cleanup setup", self.cleanup_picker)
        form.addRow("GGUF model path", self.llm_path_edit)
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
        task.succeeded.connect(self._vad_download_succeeded)
        task.failed.connect(self._vad_download_failed)
        task.paused.connect(self.status_label.setText)
        task.finished.connect(self._finish_vad_download)
        task.start(lambda progress: call_download(self.vad_download_callback, progress,
                                                   pause_event=task.pause_event))

    @QtCore.Slot(str)
    def _vad_download_succeeded(self, path):
        self.status_label.setText("Speech detection ready. Apply Settings to use it.")

    @QtCore.Slot(str)
    def _vad_download_failed(self, error):
        self.status_label.setText(f"Could not download speech detection: {error}")

    @QtCore.Slot()
    def _finish_vad_download(self):
        self.vad_download_button.setEnabled(True)
        self.model_picker.setEnabled(True)
        self._vad_download_task = None

    def _load_values(self) -> None:
        cfg = self.config
        self.speech_hotkey_edit.setText(cfg["hotkeys"]["speech"])
        self.alternative_hotkey_edit.setText(cfg["hotkeys"]["speech_alternative"])
        self.mouse_hotkey_edit.setText(cfg["hotkeys"]["speech_mouse"])
        self.hands_free_hotkey_edit.setText(cfg["hotkeys"]["hands_free"])
        self.paste_last_hotkey_edit.setText(cfg["hotkeys"]["paste_last"])
        self.save_hotkey_edit.setText(cfg["hotkeys"]["save"])
        self.cancel_hotkey_edit.setText(cfg["hotkeys"]["cancel"])
        self.tap_lock_spin.setValue(int(cfg["hotkeys"]["tap_lock_ms"]))
        self.autostart_checkbox.setChecked(bool(cfg["app"]["start_with_windows"] or self.autostart_manager.is_enabled()))
        self.auto_listen_checkbox.setChecked(bool(cfg["app"]["auto_start_listening"]))
        self.show_bar_checkbox.setChecked(bool(cfg["app"]["show_bar"]))
        self.start_sound_checkbox.setChecked(bool(cfg["app"]["start_sound"]))
        self.end_sound_checkbox.setChecked(bool(cfg["app"]["end_sound"]))
        self.notification_spin.setValue(int(cfg["app"]["notification_duration"]))
        self.retain_audio_checkbox.setChecked(cfg["recording"].get("retain_audio", False))
        self._set_combo(self.mode_combo, cfg["dictation"]["mode"])
        self._set_combo(self.profile_combo, cfg["dictation"]["profile"])
        self.drop_message_period_checkbox.setChecked(cfg["dictation"]["drop_message_period"])
        self.voice_enter_checkbox.setChecked(cfg["dictation"]["voice_enter_enabled"])
        self.learn_corrections_checkbox.setChecked(cfg["dictation"]["learn_corrections"])
        self.auto_add_dictionary_checkbox.setChecked(cfg["dictation"]["auto_add_dictionary"])
        self.auto_add_dictionary_checkbox.setEnabled(self.learn_corrections_checkbox.isChecked())
        self.max_seconds_spin.setValue(int(cfg["recording"]["max_seconds"]))
        self.warning_seconds_spin.setValue(int(cfg["recording"]["warning_seconds"]))
        self._set_combo(self.device_combo, cfg["stt"]["device"])
        self._set_combo(self.compute_combo, cfg["stt"]["compute_type"])
        self.local_files_checkbox.setChecked(bool(cfg["stt"]["local_files_only"]))
        self.llm_enabled_checkbox.setChecked(bool(cfg["llm"]["enabled"]))
        self.llm_path_edit.setText(cfg["llm"]["model_path"])
        self._dictionary_snapshot = None
        try:
            self._dictionary_snapshot = read_dictionary(self.glossary_path)
        except (OSError, ValueError) as exc:
            # The bounded store already refused this file. Do not reread an
            # oversized or invalid-encoding file into the editor during startup.
            self.dictionary_page.set_invalid(str(exc))
        if self._dictionary_snapshot is not None:
            # Show exactly the snapshot that will be checked on save.
            self.dictionary_page.set_snapshot(self._dictionary_snapshot)
        self.snippets_editor.setPlainText(self._read_text(self.snippets_path))
        self.app_profiles_editor.setPlainText(self._read_text(self.app_profiles_path, default="[]\n"))

    def _set_combo(self, combo: QtWidgets.QComboBox, value: str) -> None:
        if combo.findText(value) < 0:
            combo.addItem(value)
        combo.setCurrentText(value)

    def apply_changes(self) -> bool:
        try:
            cfg = self._collect_config()
            self._refresh_shortcut_warning()
            conflicts = find_hotkey_conflicts(cfg["hotkeys"])
            if conflicts:
                self.status_label.setText("Hotkey conflict: " + "; ".join(conflicts))
                return False

            if not self.dictionary_page.commit_form():
                return False
            dictionary = self.dictionary_page.data()
            profiles = self._parse_json_editor(self.app_profiles_editor, list, "Per-app profiles")
            if self._dictionary_snapshot is None:
                raise ValueError("Dictionary could not be read. Repair its JSON on disk, then use Reload Dictionary.")
            if dictionary == self._dictionary_snapshot.editable and not (
                    self.dictionary_page.imports or self.dictionary_page.manual_claims):
                snapshot = read_dictionary(self.glossary_path)
            else:
                snapshot = save_dictionary(self.glossary_path, dictionary,
                    expected_revision=self._dictionary_snapshot.revision,
                    imports=self.dictionary_page.imports, manual_claims=self.dictionary_page.manual_claims)
        except (OSError, ValueError) as exc:
            self.status_label.setText(str(exc))
            return False

        saved = save_config(cfg, self.config_path)
        self._dictionary_snapshot = snapshot
        self.dictionary_page.set_snapshot(snapshot)
        self._write_text(self.snippets_path, self._normalized_plain_text(self.snippets_editor))
        self._write_json(self.app_profiles_path, profiles)
        self.autostart_manager.set_enabled(saved["app"]["start_with_windows"])
        self.config = saved
        if self.on_config_applied is not None:
            self.on_config_applied(saved)
        self.status_label.setText("Saved")
        return True

    def _refresh_shortcut_warning(self):
        self._wispr_running = wispr_running()
        self._show_shortcut_warning()

    def _show_shortcut_warning(self):
        values = {"speech": self.speech_hotkey_edit.text(), "speech_alternative": self.alternative_hotkey_edit.text(),
                  "speech_mouse": self.mouse_hotkey_edit.text(), "save": self.save_hotkey_edit.text(),
                  "hands_free": self.hands_free_hotkey_edit.text(),
                  "paste_last": self.paste_last_hotkey_edit.text(),
                  "cancel": self.cancel_hotkey_edit.text()}
        warning = shortcut_warning(values, detector=lambda: getattr(self, "_wispr_running", None))
        self.shortcut_warning_label.setText(warning)
        self.shortcut_warning_label.setVisible(bool(warning))

    def _collect_config(self) -> dict[str, Any]:
        cfg = json.loads(json.dumps(self.config))
        cfg["hotkeys"]["speech"] = self.speech_hotkey_edit.text().strip()
        cfg["hotkeys"]["speech_alternative"] = self.alternative_hotkey_edit.text().strip()
        cfg["hotkeys"]["speech_mouse"] = self.mouse_hotkey_edit.text().strip()
        cfg["hotkeys"]["hands_free"] = self.hands_free_hotkey_edit.text().strip()
        cfg["hotkeys"]["paste_last"] = self.paste_last_hotkey_edit.text().strip()
        cfg["hotkeys"]["save"] = self.save_hotkey_edit.text().strip()
        cfg["hotkeys"]["cancel"] = self.cancel_hotkey_edit.text().strip()
        cfg["hotkeys"]["tap_lock_ms"] = int(self.tap_lock_spin.value())
        cfg["app"]["start_with_windows"] = bool(self.autostart_checkbox.isChecked())
        cfg["app"]["auto_start_listening"] = bool(self.auto_listen_checkbox.isChecked())
        cfg["app"]["show_bar"] = bool(self.show_bar_checkbox.isChecked())
        cfg["app"]["start_sound"] = bool(self.start_sound_checkbox.isChecked())
        cfg["app"]["end_sound"] = bool(self.end_sound_checkbox.isChecked())
        cfg["app"]["notification_duration"] = int(self.notification_spin.value())
        cfg["recording"]["max_seconds"] = int(self.max_seconds_spin.value())
        cfg["recording"]["retain_audio"] = self.retain_audio_checkbox.isChecked()
        cfg["recording"]["warning_seconds"] = int(self.warning_seconds_spin.value())
        cfg["dictation"]["mode"] = self.mode_combo.currentText()
        cfg["dictation"]["profile"] = self.profile_combo.currentText()
        cfg["dictation"]["drop_message_period"] = self.drop_message_period_checkbox.isChecked()
        cfg["dictation"]["voice_enter_enabled"] = self.voice_enter_checkbox.isChecked()
        cfg["dictation"]["learn_corrections"] = self.learn_corrections_checkbox.isChecked()
        cfg["dictation"]["auto_add_dictionary"] = (self.learn_corrections_checkbox.isChecked()
            and self.auto_add_dictionary_checkbox.isChecked())
        self.styles_page.apply_to(cfg)
        select_model(cfg, self.model_picker.model_id, manual=False)
        self.languages_page.apply_to(cfg)
        self.labs_page.apply_to(cfg)
        cfg["stt"]["device"] = self.device_combo.currentText()
        cfg["stt"]["compute_type"] = self.compute_combo.currentText()
        cfg["stt"]["local_files_only"] = bool(self.local_files_checkbox.isChecked())
        cfg["llm"]["enabled"] = bool(self.llm_enabled_checkbox.isChecked())
        cfg["llm"]["model_path"] = self.llm_path_edit.text().strip()
        cfg["llm"]["backend"] = self.cleanup_picker.backend.currentData()
        return cfg

    @QtCore.Slot(str, str)
    def _cleanup_model_ready(self, path, backend):
        self.llm_path_edit.setText(path)
        self.cleanup_picker.backend.setCurrentIndex(self.cleanup_picker.backend.findData(backend))

    def refresh_labs(self, report=None):
        cfg = json.loads(json.dumps(self.config))
        self.languages_page.apply_to(cfg)
        self.labs_page.update_eligibility(cfg, report)
        self.cleanup_picker.refresh_recommendation(report if report is not None else latest_report(
            self.config_path.parent / "hardware-benchmarks" if self.config_path else None))

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

    def pause_downloads(self):
        self.model_picker.pause()
        self.labs_page.pause()
        self.cleanup_picker.pause()
        if self._vad_download_task is not None:
            self._vad_download_task.pause()

    def closeEvent(self, event):
        self.pause_downloads()
        super().closeEvent(event)

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
