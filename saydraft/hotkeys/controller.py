"""Recording gesture controller, independent of the native input transport."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

Clock = Callable[[], float]
StartCallback = Callable[[], None]
StopCallback = Callable[["RecordingSession"], None]


@dataclass(frozen=True)
class HotkeyConfig:
    record_hotkey: str = "f9"
    alternate_record_hotkey: str | None = "ctrl+win"
    cancel_hotkey: str = "esc"
    tap_lock_ms: int = 300
    suppress: bool = True
    timeout: float = 1.0
    save_hotkey: str = "f10"

    @classmethod
    def from_app_config(cls, config: dict[str, Any]) -> "HotkeyConfig":
        hotkeys = config.get("hotkeys", {}) if isinstance(config, dict) else {}
        return cls(
            record_hotkey=str(hotkeys.get("speech", cls.record_hotkey)),
            alternate_record_hotkey=str(
                hotkeys.get("speech_alternative", cls.alternate_record_hotkey)
            ),
            cancel_hotkey=str(hotkeys.get("cancel", cls.cancel_hotkey)),
            tap_lock_ms=int(hotkeys.get("tap_lock_ms", cls.tap_lock_ms)),
            save_hotkey=str(hotkeys.get("save", cls.save_hotkey)),
        )


@dataclass(frozen=True)
class RecordingSession:
    started_at: float
    stopped_at: float
    locked: bool

    @property
    def duration_seconds(self) -> float:
        return self.stopped_at - self.started_at


class HotkeyController:
    """State machine for hold-to-talk plus short-tap lock mode."""

    def __init__(
        self,
        config: HotkeyConfig | None = None,
        *,
        on_record_start: StartCallback,
        on_record_stop: StopCallback,
        on_record_cancel: StartCallback | None = None,
        clock: Clock = time.monotonic,
        on_save=None,
        on_backend_failure=None,
        native_factory=None,
    ):
        self.config = config or HotkeyConfig()
        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop
        self.on_record_cancel = on_record_cancel
        self.clock = clock
        self.on_save, self.on_backend_failure = on_save, on_backend_failure
        self._native_factory, self._native = native_factory, None

        self._lock = threading.RLock()
        self._keyboard: Any | None = None
        self._handles: list[Any] = []
        self._pressed_hotkey: str | None = None
        self._pressed_at: float | None = None
        self._recording_started_at: float | None = None
        self._locked = False
        self._listening = False

    @property
    def is_listening(self) -> bool:
        return self._listening

    @property
    def is_recording(self) -> bool:
        return self._recording_started_at is not None

    @property
    def is_locked(self) -> bool:
        return self._locked

    def is_backend_alive(self) -> bool:
        with self._lock:
            if self._listening and self._native is not None:
                return self._native.alive
            if not self._listening or self._keyboard is None:
                return False
            keyboard_module = self._keyboard

        listener = getattr(keyboard_module, "_listener", None)
        if listener is None:
            return True
        thread = getattr(listener, "thread", None)
        if thread is not None and hasattr(thread, "is_alive"):
            try:
                return bool(thread.is_alive())
            except Exception:
                logger.debug("Could not inspect keyboard listener thread", exc_info=True)
        if hasattr(listener, "is_alive"):
            try:
                return bool(listener.is_alive())
            except Exception:
                logger.debug("Could not inspect keyboard listener", exc_info=True)
        if hasattr(listener, "listening"):
            return bool(getattr(listener, "listening"))
        return True

    def restart_if_dead(self) -> bool:
        with self._lock:
            if not self._listening:
                return False
            keyboard_module = self._keyboard

        if self.is_backend_alive():
            return False

        logger.warning("Keyboard listener appears dead; restarting hotkeys")
        if not self.stop():
            return False
        self.start(keyboard_module)
        return True

    @property
    def completion_thread(self):
        if self._native is not None:
            return self._native.completion_thread
        listener = getattr(self._keyboard, "_listener", None)
        return getattr(listener, "listening_thread", None) or getattr(listener, "thread", None)

    def _native_failed(self, reason):
        self.discard_active_recording()
        try:
            if self.on_record_cancel is not None:
                self.on_record_cancel()
        finally:
            if self.on_backend_failure is not None:
                self.on_backend_failure(reason)

    def _start_native(self):
        from .recording import RecordingHooks
        with self._lock:
            if self._listening:
                return
            previous = self._native
        if previous is not None and not previous.close():
            raise OSError("Previous native hotkey actions are still stopping")
        with self._lock:
            if self._listening:
                return
            if self._native is not previous:
                raise OSError("Native hotkey ownership changed")
            self._native = None
            self._native = RecordingHooks(self._record_hotkeys(), cancel_key=self.config.cancel_hotkey,
                save_key=self.config.save_hotkey, suppress=self.config.suppress,
                press=self._on_record_press, release=self._on_record_release, cancel=self._on_cancel_press,
                save=self.on_save, failure=self._native_failed, factory=self._native_factory)
            self._listening = True
        try:
            self._native.start()
        except Exception:
            self.stop()
            raise

    def start(self, keyboard_module: Any | None = None) -> None:
        if keyboard_module is None:
            return self._start_native()
        with self._lock:
            if self._listening:
                return
            self._keyboard = keyboard_module  # Explicit injected test/integration transport only.
            self._handles = []

            for hotkey in self._record_hotkeys():
                self._handles.append(
                    self._keyboard.add_hotkey(
                        hotkey,
                        lambda hotkey=hotkey: self._on_record_press(hotkey),
                        suppress=self.config.suppress,
                        timeout=self.config.timeout,
                    )
                )
                self._handles.append(
                    self._keyboard.add_hotkey(
                        hotkey,
                        lambda hotkey=hotkey: self._on_record_release(hotkey),
                        suppress=self.config.suppress,
                        timeout=self.config.timeout,
                        trigger_on_release=True,
                    )
                )

            if self.config.cancel_hotkey:
                self._handles.append(
                    self._keyboard.add_hotkey(
                        self.config.cancel_hotkey,
                        self._on_cancel_press,
                        suppress=False,
                        timeout=self.config.timeout,
                    )
                )
            self._listening = True

    def stop(self) -> bool:
        with self._lock:
            handles = list(self._handles)
            keyboard_module = self._keyboard
            self._handles.clear()
            self._keyboard = None
            self._listening = False
            self._pressed_hotkey = None
            self._pressed_at = None
            self._locked = False
            self._recording_started_at = None
            native = self._native

        if keyboard_module is not None:
            for handle in handles:
                try:
                    keyboard_module.remove_hotkey(handle)
                except Exception:
                    logger.debug("Could not remove hotkey handle %r", handle, exc_info=True)
        stopped = native is None or native.close()
        if stopped:
            with self._lock:
                if self._native is native:
                    self._native = None
        return stopped

    def force_stop(self) -> RecordingSession | None:
        """Stop the active recording from an external timeout or UI control."""
        session: RecordingSession | None = None
        with self._lock:
            if self.is_recording:
                session = self._finish_recording_locked(self.clock(), locked=self._locked)

        if session is not None:
            self.on_record_stop(session)
        return session

    def discard_active_recording(self) -> None:
        """Reset backend key state after cancellation or a failed microphone start."""
        with self._lock:
            self._pressed_hotkey = None
            self._pressed_at = None
            self._recording_started_at = None
            self._locked = False

    def _record_hotkeys(self) -> list[str]:
        hotkeys = [self.config.record_hotkey, self.config.alternate_record_hotkey]
        seen = set()
        normalized = []
        for hotkey in hotkeys:
            value = (hotkey or "").strip()
            if value and value not in seen:
                normalized.append(value)
                seen.add(value)
        return normalized

    def _on_record_press(self, hotkey: str, when=None, *, retarget=False) -> None:
        with self._lock:
            if not self._listening:
                return
            if self._locked:
                self._pressed_hotkey = hotkey
                self._pressed_at = self.clock() if when is None else when
                return
            if self.is_recording:
                if retarget:
                    self._pressed_hotkey = hotkey
                return
            now = self.clock() if when is None else when
            self._pressed_hotkey = hotkey
            self._pressed_at = now
            self._recording_started_at = now

        if self.on_record_start() is False:
            self.discard_active_recording()

    def _on_record_release(self, hotkey: str, when=None) -> None:
        session: RecordingSession | None = None
        with self._lock:
            if self._pressed_hotkey != hotkey or self._pressed_at is None:
                return
            now = self.clock() if when is None else when
            press_duration = now - self._pressed_at
            tap_threshold = self.config.tap_lock_ms / 1000.0

            if self._locked:
                session = self._finish_recording_locked(now, locked=True)
            elif press_duration < tap_threshold:
                self._locked = True
                self._pressed_hotkey = None
                self._pressed_at = None
            else:
                session = self._finish_recording_locked(now, locked=False)

        if session is not None:
            self.on_record_stop(session)

    def _on_cancel_press(self, when=None) -> None:
        session: RecordingSession | None = None
        with self._lock:
            if self.is_recording:
                session = self._finish_recording_locked(self.clock() if when is None else when, locked=self._locked)

        if self.on_record_cancel is not None:
            self.on_record_cancel()
        elif session is not None:
            self.on_record_stop(session)

    def _finish_recording_locked(self, stopped_at: float, *, locked: bool) -> RecordingSession | None:
        if self._recording_started_at is None:
            return None
        session = RecordingSession(
            started_at=self._recording_started_at,
            stopped_at=stopped_at,
            locked=locked,
        )
        self._pressed_hotkey = None
        self._pressed_at = None
        self._recording_started_at = None
        self._locked = False
        return session


