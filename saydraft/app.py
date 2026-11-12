"""Qt application shell for Saydraft."""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace
from typing import Callable, Sequence

from .config import load_config
from .crash_guard import install_crash_guard
from .model_download import download_asr_model
from .ui.history_window import HistoryWindow
from .ui.onboarding import OnboardingWizard
from .ui.pill import SaydraftPill
from .ui.settings_window import SettingsWindow
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

    return SaydraftWorkerSignals()


class WorkerController:
    """Connect Qt signals to the injected, UI-independent session worker."""

    def __init__(self, signals):
        self.signals = signals
        self.core = None

    def _emit(self, name, *args):
        getattr(self.signals, name).emit(*args)

    def start(self):
        from .core.container import create_services
        from .core.worker import SessionWorker

        config = load_config()
        services = create_services(
            config, level_callback=self.signals.audio_level_changed.emit,
            notify=self.signals.notification_requested.emit,
        )
        self.core = SessionWorker(services, emit=self._emit)
        if config["app"]["auto_start_listening"]:
            self.start_listening()

    def stop(self):
        if self.core is not None:
            self.core.shutdown()
            self.core = None

    def start_listening(self):
        if self.core is not None:
            self.core.hotkeys.start()

    def stop_listening(self):
        if self.core is not None:
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

    def history_store(self):
        return self.core.services.history if self.core else None

    def retry_history_audio(self, row):
        return bool(self.core and self.core.retry_history(row))

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
        onboarding_window_factory: Callable[..., object] | None = None,
        config_loader: Callable[..., dict] | None = None,
        config_path=None,
        model_download_callback: Callable[[str, Callable[[int], None]], None] | None = None,
        crash_guard_installer: Callable[..., object] | None = None,
    ):
        self.argv = list(sys.argv if argv is None else argv)
        self.qt_modules = qt_modules
        self.controller_factory = controller_factory or WorkerController
        self.tray_factory = tray_factory or SaydraftTray
        self.pill_factory = pill_factory or SaydraftPill
        self.settings_window_factory = settings_window_factory or SettingsWindow
        self.history_window_factory = history_window_factory or HistoryWindow
        self.onboarding_window_factory = onboarding_window_factory or OnboardingWizard
        self.config_loader = config_loader or load_config
        self.config_path = config_path
        self.model_download_callback = model_download_callback or download_asr_model
        self.crash_guard_installer = crash_guard_installer or install_crash_guard
        self.qt_app = None
        self.signals = None
        self.controller = None
        self.tray = None
        self.pill = None
        self.settings_window = None
        self.history_window = None
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

        self.qt_app = application
        self.config = self._load_app_config()
        self.signals = create_worker_signals(qt_modules.QtCore)
        self.controller = self.controller_factory(self.signals)
        self.tray = self.tray_factory(
            qt_modules=qt_modules,
            callbacks=TrayCallbacks(
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
        self.signals.recording_started.connect(self.pill.show_recording)
        self.signals.audio_level_changed.connect(self.pill.update_level)
        self.signals.processing_started.connect(
            lambda: self.tray.set_state(TrayState.PROCESSING)
        )
        self.signals.processing_started.connect(self.pill.show_processing)
        self.signals.processing_finished.connect(
            lambda _text: self.tray.set_state(TrayState.IDLE)
        )
        self.signals.processing_finished.connect(lambda _text: self.pill.finish_success())
        self.signals.notification_requested.connect(self._log_notification)
        self.signals.notification_requested.connect(self.tray.show_notification)
        self.signals.error.connect(self._log_error)
        self.signals.error.connect(self._set_error_state)
        self.signals.error.connect(self.pill.show_error)
        self.signals.history_updated.connect(self._refresh_history)
        self.signals.history_retry_finished.connect(self._finish_history_retry)
        self.signals.hardware_benchmark_finished.connect(self._finish_hardware_benchmark)
        self.signals.preview_text_changed.connect(self._show_preview)
        self.signals.preview_unavailable.connect(self._preview_unavailable)

        self.crash_guard = self.crash_guard_installer(
            notify=self.signals.notification_requested.emit
        )
        self.controller.start()
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
        if self.history_window is None:
            self.history_window = self.history_window_factory(
                qt_modules=self.qt_modules,
                store=self._controller_history_store(),
                clipboard=self.controller.clipboard() if hasattr(self.controller, "clipboard") else None,
                reinsert_callback=self._reinsert_history_text,
                retry_callback=self._retry_history_audio,
            )
        self.history_window.refresh()
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    def _refresh_history(self, row_id):
        if self.history_window is not None:
            self.history_window.refresh()
        if hasattr(self.tray, "set_model_label"):
            self.tray.set_model_label(self._controller_model_label())

    def _retry_history_audio(self, row):
        callback = getattr(self.controller, "retry_history_audio", None)
        return bool(callback and callback(row))

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

    def _show_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = self.settings_window_factory(
                qt_modules=self.qt_modules,
                config_path=self.config_path,
                on_config_applied=self._on_settings_applied,
                model_download_callback=self.model_download_callback,
                hardware_benchmark_callback=self._benchmark_hardware,
                style_preview_callback=getattr(self.controller, "preview_style", None),
                style_glossary_provider=getattr(self.controller, "style_glossary", None),
            )
            page = getattr(self.settings_window, "styles_page", None)
            if page is not None:
                qt = self.qt_modules or _load_qt_modules()
                self.signals.style_preview_finished.connect(page.accept_result, qt.QtCore.Qt.QueuedConnection)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

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

    def _load_app_config(self) -> dict:
        try:
            return self.config_loader(config_path=self.config_path)
        except TypeError:
            return self.config_loader()
