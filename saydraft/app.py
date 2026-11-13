"""Qt application shell for Saydraft."""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace
from typing import Callable, Sequence

from .config import load_config
from .crash_guard import install_crash_guard
from .model_download import download_asr_model
from .ui.history_page import HistoryPage
from .ui.hub import HubWindow
from .ui.onboarding import OnboardingWizard
from .ui.pill import SaydraftPill
from .ui.settings_page import SettingsPage
from .ui.tray import TrayCallbacks, TrayState, SaydraftTray

logger = logging.getLogger(__name__)


def _load_qt_modules():
    from PySide6 import QtCore, QtGui, QtWidgets

    return SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)


def create_worker_signals(QtCore):
    class SaydraftWorkerSignals(QtCore.QObject):
        recording_started = QtCore.Signal()
        recording_stopped = QtCore.Signal(float)
        audio_level_changed = QtCore.Signal(float)
        processing_started = QtCore.Signal()
        processing_finished = QtCore.Signal(str)
        error = QtCore.Signal(str)
        notification_requested = QtCore.Signal(str)
        history_updated = QtCore.Signal(int)
        history_retry_finished = QtCore.Signal(int)
        hardware_benchmark_finished = QtCore.Signal(object)
        preview_text_changed = QtCore.Signal(int, str)
        preview_unavailable = QtCore.Signal(int)
        dictionary_suggestion = QtCore.Signal(object)
        dictionary_changed = QtCore.Signal(object)
        style_preview_finished = QtCore.Signal(object)
        bar_updated = QtCore.Signal(object)
        listening_changed = QtCore.Signal(bool)

    return SaydraftWorkerSignals()


class WorkerController:
    """Connect Qt signals to the injected, UI-independent session worker."""

    supports_bar_updates = True

    def __init__(self, signals):
        self.signals = signals
        self.core = None
        self._bar_actions = None

    def _emit(self, name, *args):
        getattr(self.signals, name).emit(*args)

    def _bar_updated(self, update):
        from .core.bar_status import BarPhase

        # Native backend failure/Esc can cancel before the deferred click runs.
        # Retire that click even when its queue is discarded during teardown.
        if (update.phase == BarPhase.IDLE and update.reason == "cancelled"
                and self._bar_actions is not None and self._bar_actions.pending):
            self._bar_actions.cancel_pending()
        self.signals.bar_updated.emit(update)

    def start(self):
        from .core.container import create_services
        from .core.worker import SessionWorker

        config = load_config()
        services = create_services(
            config, level_callback=self.signals.audio_level_changed.emit,
            notify=self.signals.notification_requested.emit,
        )
        self.core = SessionWorker(services, emit=self._emit, bar_emit=self._bar_updated)
        if config["app"]["auto_start_listening"]:
            self.start_listening()

    def stop(self):
        if self.core is not None:
            core = self.core
            self.core = None
            if self._bar_actions is not None:
                self._bar_actions.close()
            else:
                core.shutdown()

    def start_listening(self):
        if self.core is not None:
            if self._bar_actions is not None:
                self._bar_actions.start_listening()
            else:
                self.core.hotkeys.start()

    def stop_listening(self):
        if self.core is not None:
            if self._bar_actions is not None:
                self._bar_actions.stop_listening()
            else:
                self.core.cancel()
                self.core.hotkeys.stop()

    def is_listening(self):
        return bool(self.core and self.core.hotkeys.enabled)

    def model_label(self):
        from .asr.selection import configured_model_id
        from .models.manifest import get_model

        config = self.core.services.config if self.core else load_config()
        model_id = (getattr(self.core.services.asr, "model_id", None) if self.core else None) or configured_model_id(config)
        try:
            return get_model(model_id)["label"]
        except ValueError:
            return model_id

    def hotkey_hint(self):
        config = self.core.services.config if self.core else load_config()
        return str(config["hotkeys"]["speech"]).upper()

    def is_hands_free(self):
        return bool(self.core and ((self._bar_actions is not None and self._bar_actions.pending)
            or self.core.hotkeys._controller.is_locked))

    def is_current_bar(self, generation):
        return bool(self.core and not self.core._closing and self.core.bar_status.is_current(generation))

    def request_bar_action(self, *, stop=False):
        if self.core is None:
            return False
        if self._bar_actions is not None and self._bar_actions.pending:
            if stop:
                self._bar_actions.cancel_pending()
                return True
            return False
        if not stop and not self.core.hotkeys.enabled:
            if self._bar_actions is None:
                from .core.bar_actions import BarActions
                core = self.core

                def changed():
                    if self.core is core:
                        self.signals.listening_changed.emit(bool(core.hotkeys.enabled))

                self._bar_actions = BarActions(core, changed=changed)
            return self._bar_actions.request_start()
        return bool(self.core.hotkeys._controller.request_hands_free(stop=stop))

    def history_store(self):
        return self.core.services.history if self.core else None

    def retry_history_audio(self, row, options=None):
        return bool(self.core and (self.core.retry_history(row) if options is None else self.core.retry_history(row, options)))

    def cancel_history_retry(self):
        return bool(self.core and self.core.cancel_history_retry())

    def benchmark_hardware(self):
        return bool(self.core and self.core.benchmark_hardware())

    def is_current_preview(self, generation, *, listening_only=True):
        return bool(self.core and self.core.is_current_preview(generation, listening_only=listening_only))

    def reinsert_text(self, text):
        queued = bool(self.core and self.core.reinsert_text(text))
        if not queued:
            self.signals.notification_requested.emit("Finish the current work before reinserting History text.")
        return queued

    def clipboard(self):
        return getattr(self.core.services.inserter, "clipboard", None) if self.core is not None else None

    def apply_config(self, config):
        if self.core is not None:
            if self._bar_actions is not None:
                self._bar_actions.configure(config)
            else:
                self.core.configure(config)

    def poll_corrections(self):
        if self.core is not None:
            self.core.poll_corrections()

    def is_current_correction(self, suggestion):
        return bool(self.core and self.core.is_current_correction(suggestion))

    def add_correction(self, suggestion, *, automatic=False):
        return bool(self.core and self.core.add_correction(suggestion, automatic=automatic))

    def undo_correction(self, receipt):
        return bool(self.core and self.core.undo_correction(receipt))

    def preview_style(self, request):
        return bool(self.core and self.core.preview_style(request))

    def style_glossary(self):
        from .dictation.glossary import Glossary
        return getattr(self.core.services.cleaner, "glossary", Glossary()) if self.core else Glossary()


class SaydraftApp:
    """Own the Qt event loop and worker signal wiring."""

    def __init__(
        self,
        argv: Sequence[str] | None = None,
        qt_modules=None,
        controller_factory: Callable[[object], object] | None = None,
        tray_factory: Callable[..., object] | None = None,
        pill_factory: Callable[..., object] | None = None,
        settings_window_factory: Callable[..., object] | None = None,
        history_window_factory: Callable[..., object] | None = None,
        hub_window_factory: Callable[..., object] | None = None,
        onboarding_window_factory: Callable[..., object] | None = None,
        config_loader: Callable[..., dict] | None = None,
        config_path=None,
        model_download_callback: Callable[[str, Callable[[int], None]], None] | None = None,
        crash_guard_installer: Callable[..., object] | None = None,
        sound_bank_factory: Callable[..., object] | None = None,
    ):
        self.argv = list(sys.argv if argv is None else argv)
        self.qt_modules = qt_modules
        self.controller_factory = controller_factory or WorkerController
        self.tray_factory = tray_factory or SaydraftTray
        self.pill_factory = pill_factory or SaydraftPill
        self.settings_window_factory = settings_window_factory or SettingsPage
        self.history_window_factory = history_window_factory or HistoryPage
        self.hub_window_factory = hub_window_factory or HubWindow
        self.onboarding_window_factory = onboarding_window_factory or OnboardingWizard
        self.config_loader = config_loader or load_config
        self.config_path = config_path
        self.model_download_callback = model_download_callback or download_asr_model
        self.crash_guard_installer = crash_guard_installer or install_crash_guard
        self.sound_bank_factory = sound_bank_factory
        self.bar_sounds = None
        self.qt_app = None
        self.signals = None
        self.controller = None
        self.tray = None
        self.pill = None
        self.settings_window = None
        self.history_window = None
        self.hub_window = None
        self.onboarding_window = None
        self.config = None
        self.crash_guard = None

    def run(self) -> int:
        qt_modules = self.qt_modules or _load_qt_modules()
        application = qt_modules.QtWidgets.QApplication.instance()
        if application is None:
            application = qt_modules.QtWidgets.QApplication(self.argv)

        application.setApplicationName("Saydraft")
        application.setQuitOnLastWindowClosed(False)
        if hasattr(qt_modules.QtGui, "QFontDatabase"):
            from .ui.fonts import install_bundled_fonts
            install_bundled_fonts(application, QtGui=qt_modules.QtGui)
        if hasattr(qt_modules.QtGui, "QPalette"):
            from .ui.theme import install_theme
            install_theme(application)

        self.qt_app = application
        self.config = self._load_app_config()
        self.signals = create_worker_signals(qt_modules.QtCore)
        self.controller = self.controller_factory(self.signals)
        self.tray = self.tray_factory(
            qt_modules=qt_modules,
            callbacks=TrayCallbacks(
                show_hub=self._show_hub,
                start_listening=self._start_listening,
                stop_listening=self._stop_listening,
                show_history=self._show_history,
                show_settings=self._show_settings,
                quit_app=getattr(application, "quit", lambda: None),
            ),
            model_label=self._controller_model_label(),
        )
        self.pill = self.pill_factory(
            qt_modules=qt_modules,
            hotkey_hint=self._controller_hotkey_hint(),
        )

        about_to_quit = getattr(application, "aboutToQuit", None)
        if about_to_quit is not None:
            about_to_quit.connect(self.controller.stop)

        self.signals.recording_started.connect(
            lambda: self.tray.set_state(TrayState.RECORDING)
        )
        typed_bar = bool(getattr(self.controller, "supports_bar_updates", False)) and hasattr(self.pill, "show_preparing")
        if typed_bar:
            from .ui.bar_sounds import BarSoundPresenter, sound_bank
            self.bar_sounds = BarSoundPresenter((self.sound_bank_factory or sound_bank)(application),
                current=self.controller.is_current_bar, state=lambda: self.pill.state,
                config=lambda: self.config)
            self.signals.bar_updated.connect(self._apply_bar_update, qt_modules.QtCore.Qt.QueuedConnection)
            if about_to_quit is not None:
                about_to_quit.connect(self.bar_sounds.close)
        else:
            self.signals.recording_started.connect(self._show_recording_bar)
        self.signals.audio_level_changed.connect(self.pill.update_level)
        self.signals.processing_started.connect(
            lambda: self.tray.set_state(TrayState.PROCESSING)
        )
        if not typed_bar:
            self.signals.processing_started.connect(self.pill.show_processing)
        self.signals.processing_finished.connect(
            lambda _text: self.tray.set_state(TrayState.IDLE)
        )
        if not typed_bar:
            self.signals.processing_finished.connect(lambda _text: self.pill.finish_success())
        self.signals.notification_requested.connect(self._log_notification)
        self.signals.notification_requested.connect(self.tray.show_notification)
        self.signals.error.connect(self._log_error)
        self.signals.error.connect(self._set_error_state)
        if not typed_bar:
            self.signals.error.connect(self.pill.show_error)
        self.signals.history_updated.connect(self._refresh_history)
        if hasattr(qt_modules.QtCore, "Qt"):
            self.signals.dictionary_changed.connect(self._refresh_dictionary, qt_modules.QtCore.Qt.QueuedConnection)
        else:
            self.signals.dictionary_changed.connect(self._refresh_dictionary)
        self.signals.history_retry_finished.connect(self._finish_history_retry)
        self.signals.hardware_benchmark_finished.connect(self._finish_hardware_benchmark)
        self.signals.preview_text_changed.connect(self._show_preview)
        self.signals.preview_unavailable.connect(self._preview_unavailable)
        if typed_bar:
            self.signals.listening_changed.connect(self._listening_changed, qt_modules.QtCore.Qt.QueuedConnection)
        else:
            self.signals.listening_changed.connect(self._listening_changed)
        if hasattr(self.pill, "start_requested") and hasattr(self.controller, "request_bar_action"):
            self.pill.start_requested.connect(lambda: self.controller.request_bar_action())
            self.pill.stop_requested.connect(lambda: self.controller.request_bar_action(stop=True))
            self.pill.fix_requested.connect(self._fix_bar_error)
            self.pill.hands_free_provider = self.controller.is_hands_free
        if about_to_quit is not None and hasattr(self.pill, "hide"):
            about_to_quit.connect(self.pill.hide)

        self.crash_guard = self.crash_guard_installer(
            notify=self.signals.notification_requested.emit
        )
        self.controller.start()
        self._configure_bar()
        if hasattr(qt_modules.QtCore, "QTimer") and hasattr(self.controller, "add_correction"):
            from .ui.dictionary_toast import DictionaryPresenter
            self.dictionary_presenter = DictionaryPresenter(self.controller,
                config=lambda: self.config, parent=application)
            self.signals.dictionary_suggestion.connect(self.dictionary_presenter.suggest, qt_modules.QtCore.Qt.QueuedConnection)
            self.signals.dictionary_changed.connect(self.dictionary_presenter.changed, qt_modules.QtCore.Qt.QueuedConnection)
            self.signals.recording_started.connect(self.dictionary_presenter.retire_suggestion)
            if about_to_quit is not None:
                about_to_quit.connect(self.dictionary_presenter.close)
        if hasattr(qt_modules.QtCore, "QTimer") and hasattr(self.controller, "poll_corrections"):
            self.correction_timer = qt_modules.QtCore.QTimer(application)
            self.correction_timer.timeout.connect(self.controller.poll_corrections)
            self.correction_timer.start(250)
            if about_to_quit is not None:
                about_to_quit.connect(self.correction_timer.stop)
        self._sync_listening_state()
        if hasattr(self.tray, "set_model_label"):
            self.tray.set_model_label(self._controller_model_label())
        self._show_onboarding_if_needed()
        return int(application.exec())

    def _apply_bar_update(self, update):
        from .core.bar_status import BarPhase, BarUpdate

        if not isinstance(update, BarUpdate) or not self.controller.is_current_bar(update.generation):
            return
        if update.phase == BarPhase.PREPARING:
            self.pill.show_preparing(hands_free=self.controller.is_hands_free())
        elif update.phase == BarPhase.LISTENING:
            if update.reason == "command":
                self.pill.show_recording(hands_free=self.controller.is_hands_free(), command=True)
            else:
                self._show_recording_bar()
        elif update.phase == BarPhase.PROCESSING:
            self.pill.show_processing()
        elif update.phase == BarPhase.NOT_INSERTED:
            self.pill.show_not_inserted(update.reason, saved=update.saved)
        elif update.phase == BarPhase.ERROR:
            message = {"microphone_unavailable": "No microphone", "model_unavailable": "Speech model unavailable",
                "processing_failed": "Could not complete dictation"}.get(update.reason, "Dictation unavailable")
            self.pill.show_error(message, fix_page="microphone" if update.reason == "microphone_unavailable" else "models")
        elif update.phase in (BarPhase.INSERTED, BarPhase.IDLE):
            self.pill.finish_success()
        if self.bar_sounds is not None:
            self.bar_sounds.handle(update)

    def _show_recording_bar(self):
        provider = getattr(self.controller, "is_hands_free", None)
        if provider is not None and hasattr(self.pill, "set_hands_free"):
            self.pill.show_recording(hands_free=provider())
        else:
            self.pill.show_recording()

    def _configure_bar(self):
        cfg = self.config if isinstance(self.config, dict) else {}
        if hasattr(self.pill, "set_paste_hint"):
            self.pill.set_paste_hint(cfg.get("hotkeys", {}).get("paste_last", "shift+alt+z"))
        if hasattr(self.pill, "set_idle_enabled"):
            self.pill.set_idle_enabled(cfg.get("app", {}).get("show_bar", True))

    def _fix_bar_error(self, page):
        self._show_settings()
        tabs = getattr(self.settings_window, "tabs", None)
        if tabs is not None:
            label = "Microphone" if page == "microphone" else "Models"
            for index in range(tabs.count()):
                if tabs.tabText(index) == label:
                    tabs.setCurrentIndex(index)
                    break

    def _show_preview(self, generation, text):
        current = getattr(self.controller, "is_current_preview", None)
        if current and current(generation):
            self.pill.update_preview(text)

    def _preview_unavailable(self, generation):
        current = getattr(self.controller, "is_current_preview", None)
        if current and current(generation, listening_only=False):
            self.pill.clear_preview()
            if getattr(self, "_preview_failure_generation", None) != generation:
                self._preview_failure_generation = generation
                self.tray.show_notification("Live preview unavailable for this recording. Default recognition continues. "
                                            "Check English preview in Settings → Labs.")

    def _log_notification(self, message: str) -> None:
        logger.info("Notification requested: %s", message)

    def _log_error(self, message: str) -> None:
        logger.error("Worker error: %s", message)

    def _set_error_state(self, message: str) -> None:
        if "microphone" in str(message).lower():
            self.tray.set_state(TrayState.NO_MICROPHONE)
            return
        self.tray.set_state(TrayState.IDLE)

    def _start_listening(self) -> None:
        if hasattr(self.controller, "start_listening"):
            self.controller.start_listening()
        self.tray.set_listening(True)

    def _stop_listening(self) -> None:
        if hasattr(self.controller, "stop_listening"):
            self.controller.stop_listening()
        self.tray.set_listening(False)

    def _show_history(self) -> None:
        self._show_hub("History")

    def _refresh_history(self, row_id):
        if self.hub_window is not None:
            self.hub_window.refresh()
        if hasattr(self.tray, "set_model_label"):
            self.tray.set_model_label(self._controller_model_label())

    def _refresh_dictionary(self, change):
        refresh = getattr(self.settings_window, "refresh_dictionary", None)
        if refresh is not None:
            refresh(change)

    def _retry_history_audio(self, row, options=None):
        callback = getattr(self.controller, "retry_history_audio", None)
        return bool(callback and (callback(row) if options is None else callback(row, options)))

    def _finish_history_retry(self, row_id):
        if self.history_window is not None and hasattr(self.history_window, "finish_retry"):
            self.history_window.finish_retry(row_id)

    def _benchmark_hardware(self):
        callback = getattr(self.controller, "benchmark_hardware", None)
        return bool(callback and callback())

    def _finish_hardware_benchmark(self, report):
        page = getattr(self.settings_window, "hardware_page", None)
        if page is not None:
            page.finish(report)
        refresh = getattr(self.settings_window, "refresh_labs", None)
        if report is not None and refresh is not None:
            refresh(report)
        if self.hub_window is not None:
            self.hub_window.home_page.refresh()

    def _show_settings(self) -> None:
        self._show_hub("Settings")

    def _hub_tier(self):
        from pathlib import Path
        from .models.hardware import latest_report

        report = latest_report(Path(self.config_path).parent / "hardware-benchmarks" if self.config_path else None)
        assessment = report.get("assessment") if isinstance(report, dict) else None
        tier = assessment.get("tier") if isinstance(assessment, dict) else None
        return tier if tier in ("lite", "standard", "pro") else "pending"

    def _ensure_hub(self):
        if self.hub_window is None:
            self.hub_window = self.hub_window_factory(
                settings_options=dict(qt_modules=self.qt_modules, config_path=self.config_path,
                    on_config_applied=self._on_settings_applied, model_download_callback=self.model_download_callback,
                    hardware_benchmark_callback=self._benchmark_hardware,
                    style_preview_callback=getattr(self.controller, "preview_style", None),
                    style_glossary_provider=getattr(self.controller, "style_glossary", None)),
                history_options=dict(qt_modules=self.qt_modules, store=self._controller_history_store(),
                    clipboard=self.controller.clipboard() if hasattr(self.controller, "clipboard") else None,
                    reinsert_callback=self._reinsert_history_text, retry_callback=self._retry_history_audio,
                    cancel_retry_callback=getattr(self.controller, "cancel_history_retry", None)),
                settings_page_factory=self.settings_window_factory, history_page_factory=self.history_window_factory,
                shortcut=self._controller_hotkey_hint, model=self._controller_model_label, tier=self._hub_tier)
            self.settings_window = self.hub_window.settings_page
            self.history_window = self.hub_window.history_page
            page = getattr(self.settings_window, "styles_page", None)
            if page is not None:
                qt = self.qt_modules or _load_qt_modules()
                self.signals.style_preview_finished.connect(page.accept_result, qt.QtCore.Qt.QueuedConnection)
            about = getattr(self.qt_app, "aboutToQuit", None)
            if about is not None:
                about.connect(self.hub_window.close)

    def _show_hub(self, page="Home"):
        self._ensure_hub()
        self.hub_window.show_page(page)
        self.hub_window.show()
        self.hub_window.raise_()
        self.hub_window.activateWindow()

    def _show_onboarding_if_needed(self) -> None:
        cfg = self.config if isinstance(self.config, dict) else {}
        if bool(cfg.get("app", {}).get("onboarded", False)):
            return
        self._show_onboarding()

    def _show_onboarding(self) -> None:
        if self.onboarding_window is None:
            self.onboarding_window = self.onboarding_window_factory(
                qt_modules=self.qt_modules,
                config_path=self.config_path,
                on_config_applied=self._on_onboarding_applied,
                model_download_callback=self.model_download_callback,
                hotkey_hint=self._controller_hotkey_hint(),
            )
            if hasattr(self.onboarding_window, "update_audio_level"):
                self.signals.audio_level_changed.connect(self.onboarding_window.update_audio_level)
        self.onboarding_window.show()
        self.onboarding_window.raise_()
        self.onboarding_window.activateWindow()

    def _on_settings_applied(self, config: dict) -> None:
        self.config = config
        presenter = getattr(self, "dictionary_presenter", None)
        if presenter is not None:
            presenter.retire_suggestion()
        if hasattr(self.controller, "apply_config"):
            self.controller.apply_config(config)
        if hasattr(self.tray, "set_model_label"):
            self.tray.set_model_label(self._controller_model_label())
        if hasattr(self.pill, "set_hotkey_hint"):
            self.pill.set_hotkey_hint(str(config.get("hotkeys", {}).get("speech", "F9")).upper())
        self._configure_bar()

    def _on_onboarding_applied(self, config: dict) -> None:
        self._on_settings_applied(config)

    def _controller_history_store(self):
        if hasattr(self.controller, "history_store"):
            store = self.controller.history_store()
            if store is not None:
                return store
        return None

    def _reinsert_history_text(self, text: str, _row=None):
        if hasattr(self.controller, "reinsert_text"):
            return self.controller.reinsert_text(text)
        return False

    def _controller_model_label(self) -> str:
        if hasattr(self.controller, "model_label"):
            return str(self.controller.model_label())
        return "base"

    def _controller_hotkey_hint(self) -> str:
        if hasattr(self.controller, "hotkey_hint"):
            return str(self.controller.hotkey_hint())
        return "F9"

    def _sync_listening_state(self) -> None:
        if hasattr(self.controller, "is_listening"):
            self.tray.set_listening(bool(self.controller.is_listening()))

    def _listening_changed(self, _enabled: bool) -> None:
        self._sync_listening_state()

    def _load_app_config(self) -> dict:
        try:
            return self.config_loader(config_path=self.config_path)
        except TypeError:
            return self.config_loader()
