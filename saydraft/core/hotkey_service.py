"""Hotkey lifetime and event-driven recovery of a terminated backend thread."""

from __future__ import annotations

import logging
import threading
import weakref

from saydraft.hotkeys import HotkeyConfig, HotkeyController
from saydraft.hotkeys.wispr import shortcut_warning

logger = logging.getLogger(__name__)


class HotkeyService:
    def __init__(self, config, *, start, stop, cancel, save, notify, keyboard_module=None,
                 stop_timed=None, native_factory=None, stop_session=None, timer_factory=threading.Timer, paste=None):
        self.config = config
        self.start_recording = start
        self.stop_recording = stop
        self.cancel_recording = cancel
        self.save = save
        self.notify = notify
        self.keyboard = keyboard_module
        self.stop_timed, self.native_factory = stop_timed, native_factory
        self.stop_session, self.timer_factory = stop_session, timer_factory
        self.paste = paste
        self._lock, self._restarts = threading.RLock(), 0
        self._failure_reason = None
        self.enabled = False
        self._save_handle = None
        self._monitor = None
        self._monitor_controller = None
        self._monitored_thread = None
        self._controller = self._make_controller()

    def _make_controller(self):
        return HotkeyController(HotkeyConfig.from_app_config(self.config),
                                on_record_start=self.start_recording,
                                on_record_stop=lambda session: (self.stop_session(session) if self.stop_session is not None
                                    else self.stop_timed(session.stopped_at) if self.stop_timed is not None
                                    else self.stop_recording()),
                                on_record_cancel=self.cancel_recording, on_save=self.save,
                                on_backend_failure=self._native_failed, native_factory=self.native_factory,
                                timer_factory=self.timer_factory, on_paste=self.paste)

    def _native_failed(self, reason):
        self._failure_reason = reason  # Notification/recovery waits for the completion thread.

    def start(self):
        with self._lock:
            if self.enabled:
                return
            try:
                self._controller.start(self.keyboard)
                if self.keyboard is not None:
                    self._save_handle = self.keyboard.add_hotkey(self.config["hotkeys"]["save"], self.save)
            except Exception:
                self._controller.stop()
                raise
            self.enabled, self._restarts, self._failure_reason = True, 0, None
            self._attach_monitor()
            if self.keyboard is None:
                warning = shortcut_warning(self.config.get("hotkeys", {}))
                if warning:
                    self.notify(warning)

    def _attach_monitor(self):
        thread, watched = self._controller.completion_thread, self._controller
        if thread is not None and (self._monitor is None or self._monitor_controller is not watched
                                   or self._monitored_thread is not thread):
            # Wait for termination, rather than waking periodically while idle.
            reference = weakref.ref(self)

            def monitor(backend_thread):
                backend_thread.join()
                service = reference()
                if service is not None:
                    with service._lock:
                        if service._monitor is threading.current_thread():
                            service._monitor = None
                        if (service.enabled and service._controller is watched
                                and watched.completion_thread is backend_thread):
                            service.restart_if_dead()

            self._monitor = threading.Thread(target=monitor, args=(thread,), daemon=True)
            self._monitor_controller = watched
            self._monitored_thread = thread
            self._monitor.start()

    def stop(self):
        with self._lock:
            was_enabled = self.enabled
            self.enabled = False
            stopped = self._controller.stop()
            if self._save_handle is not None:
                try:
                    self.keyboard.remove_hotkey(self._save_handle)
                except (KeyError, ValueError):
                    logger.debug("Save hotkey was already removed")
                self._save_handle = None
            if was_enabled:
                self.cancel_recording()
            return stopped

    def configure(self, config):
        with self._lock:
            enabled = self.enabled
            if not self.stop():
                raise OSError("Previous hotkey actions are still stopping")
            self.config = config
            self._controller = self._make_controller()
            if enabled:
                self.start()

    def restart_if_dead(self) -> bool:
        with self._lock:
            if not self.enabled or self._controller.is_backend_alive():
                return False
            if self.keyboard is None and (self._restarts >= 1 or self._failure_reason == "mask_unavailable"):
                self.stop()
                self.notify("Native hotkeys stopped. Re-enable listening from the tray to try again.")
                return False
            self._restarts += 1
            try:
                if self.keyboard is not None:
                    self.cancel_recording()
                if not self._controller.restart_if_dead():
                    return False
                if self.keyboard is not None:
                    if self._save_handle is not None:
                        self.keyboard.remove_hotkey(self._save_handle)
                    self._save_handle = self.keyboard.add_hotkey(self.config["hotkeys"]["save"], self.save)
            except Exception:
                self.stop()
                self.notify("Native hotkeys unavailable. Check shortcuts in Settings and re-enable listening.")
                return False
            self.notify("Saydraft restarted hotkeys after a listener error.")
            self._attach_monitor()
            return True
