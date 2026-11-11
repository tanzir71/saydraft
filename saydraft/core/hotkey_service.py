"""Hotkey lifetime and event-driven recovery of a terminated backend thread."""

from __future__ import annotations

import logging
import threading
import weakref

from saydraft.hotkeys import HotkeyConfig, HotkeyController

logger = logging.getLogger(__name__)


class HotkeyService:
    def __init__(self, config, *, start, stop, cancel, save, notify, keyboard_module=None):
        self.config = config
        self.start_recording = start
        self.stop_recording = stop
        self.cancel_recording = cancel
        self.save = save
        self.notify = notify
        self.keyboard = keyboard_module
        self.enabled = False
        self._save_handle = None
        self._monitor = None
        self._controller = self._make_controller()

    def _make_controller(self):
        return HotkeyController(HotkeyConfig.from_app_config(self.config),
                                on_record_start=self.start_recording,
                                on_record_stop=lambda session: self.stop_recording(),
                                on_record_cancel=self.cancel_recording)

    def start(self):
        if self.enabled:
            return
        if self.keyboard is None:
            import keyboard
            self.keyboard = keyboard
        try:
            self._controller.start(self.keyboard)
            self._save_handle = self.keyboard.add_hotkey(self.config["hotkeys"]["save"], self.save)
        except Exception:
            self._controller.stop()
            raise
        self.enabled = True
        listener = getattr(self.keyboard, "_listener", None)
        thread = getattr(listener, "listening_thread", None) or getattr(listener, "thread", None)
        if thread is not None and self._monitor is None:
            # Wait for termination, rather than waking periodically while idle.
            reference = weakref.ref(self)

            def monitor(backend_thread):
                backend_thread.join()
                service = reference()
                if service is not None and service.enabled:
                    service.restart_if_dead()

            self._monitor = threading.Thread(target=monitor, args=(thread,), daemon=True)
            self._monitor.start()

    def stop(self):
        self.enabled = False
        self._controller.stop()
        if self._save_handle is not None:
            try:
                self.keyboard.remove_hotkey(self._save_handle)
            except (KeyError, ValueError):
                logger.debug("Save hotkey was already removed")
            self._save_handle = None

    def configure(self, config):
        enabled = self.enabled
        self.stop()
        self.config = config
        self._controller = self._make_controller()
        if enabled:
            self.start()

    def restart_if_dead(self) -> bool:
        if not self.enabled or not self._controller.restart_if_dead():
            return False
        if self._save_handle is not None:
            self.keyboard.remove_hotkey(self._save_handle)
        self._save_handle = self.keyboard.add_hotkey(self.config["hotkeys"]["save"], self.save)
        self.notify("Saydraft restarted hotkeys after a listener error.")
        return True
