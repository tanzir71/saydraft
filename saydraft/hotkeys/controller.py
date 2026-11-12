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
StartCallback = Callable[[], int | bool | None]
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
    mouse_record_hotkey: str | None = None
    hands_free_hotkey: str | None = None
    paste_last_hotkey: str | None = None

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
            mouse_record_hotkey=str(hotkeys.get("speech_mouse", "")),
            hands_free_hotkey=str(hotkeys.get("hands_free", "")),
            paste_last_hotkey=str(hotkeys.get("paste_last", "")),
        )


@dataclass(frozen=True)
class RecordingSession:
    started_at: float
    stopped_at: float
    locked: bool
    session_id: int | None = None

    @property
    def duration_seconds(self) -> float:
        return self.stopped_at - self.started_at


class HotkeyController:
    """Hold-to-talk, double-tap lock and explicit hands-free recording."""

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
        timer_factory=threading.Timer,
        on_paste=None,
        on_record_start_guarded=None,
    ):
        self.config = config or HotkeyConfig()
        self.on_record_start = on_record_start
        self.on_record_start_guarded = on_record_start_guarded
        self.on_record_stop = on_record_stop
        self.on_record_cancel = on_record_cancel
        self.clock = clock
        self.on_save, self.on_backend_failure = on_save, on_backend_failure
        self._native_factory, self._native = native_factory, None
        self._timer_factory = timer_factory

        self._lock = threading.RLock()
        self._keyboard: Any | None = None
        self._handles: list[Any] = []
        self._pressed_hotkey: str | None = None
        self._pressed_at: float | None = None
        self._recording_started_at: float | None = None
        self._locked = False
        self._listening = False
        self._tap = None
        self._second_tap = False
        self._request = 0
        self._session_id = None
        self.on_paste = on_paste

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
                save=self.on_save, failure=self._native_failed, factory=self._native_factory,
                hands_free_key=self.config.hands_free_hotkey, toggle=self._on_hands_free_press,
                paste_key=self.config.paste_last_hotkey, paste=self.on_paste)
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

            if self.config.hands_free_hotkey:
                self._handles.append(self._keyboard.add_hotkey(
                    self.config.hands_free_hotkey, self._on_hands_free_press,
                    suppress=self.config.suppress, timeout=self.config.timeout))
            if self.config.paste_last_hotkey and self.on_paste is not None:
                self._handles.append(self._keyboard.add_hotkey(
                    self.config.paste_last_hotkey, self.on_paste, trigger_on_release=True,
                    suppress=self.config.suppress, timeout=self.config.timeout))
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
            self._reset_recording_locked()
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
            self._reset_recording_locked()

    def _cancel_tap_locked(self):
        tap, self._tap = self._tap, None
        if tap is not None:
            tap[3].cancel()

    def _reset_recording_locked(self):
        self._cancel_tap_locked()
        self._request += 1
        self._pressed_hotkey = self._pressed_at = self._recording_started_at = None
        self._locked = self._second_tap = False
        self._session_id = None

    def _start_capture(self, request, valid=None):
        def current():
            return (request == self._request and self.is_recording
                and (valid is None or valid()) and request == self._request)

        if not current():
            return
        result = self.on_record_start_guarded(current) if self.on_record_start_guarded is not None else self.on_record_start()
        with self._lock:
            if request != self._request or not self.is_recording:
                return  # Cancel/disable may have completed while context was read.
            if result is False:
                self._reset_recording_locked()
            elif type(result) is int and result > 0:
                self._session_id = result

    def _queue_tap_expiry(self, token):
        with self._lock:
            native = self._native
        if native is None:
            self._expire_tap(token)
        else:
            native.defer(lambda: self._expire_tap(token))

    def _expire_tap(self, token):
        with self._lock:
            if self._tap is None or self._tap[2] is not token or not self._listening:
                return
            session = self._finish_recording_locked(self._tap[1], locked=False)
        if session is not None:
            self.on_record_stop(session)

    def _record_hotkeys(self) -> list[str]:
        hotkeys = [self.config.record_hotkey, self.config.alternate_record_hotkey, self.config.mouse_record_hotkey]
        seen = set()
        normalized = []
        for hotkey in hotkeys:
            value = (hotkey or "").strip()
            if value and value not in seen:
                normalized.append(value)
                seen.add(value)
        return normalized

    def _on_record_press(self, hotkey: str, when=None, *, retarget=False) -> None:
        expired = None
        with self._lock:
            if not self._listening:
                return
            now = self.clock() if when is None else when
            if self._locked:
                self._pressed_hotkey = hotkey
                self._pressed_at = now
                return
            if self.is_recording:
                if self._tap is not None:
                    key, released, _, _ = self._tap
                    if not released <= now <= released + self._tap_window():
                        expired = self._finish_recording_locked(released, locked=False)
                    else:
                        self._second_tap = key == hotkey
                        self._cancel_tap_locked()
                        self._pressed_hotkey, self._pressed_at = hotkey, now
                elif retarget:
                    self._second_tap = self._second_tap and self._pressed_hotkey == hotkey
                    self._pressed_hotkey = hotkey
                if expired is None:
                    return
            self._request += 1
            request = self._request
            self._pressed_hotkey = hotkey
            self._pressed_at = now
            self._recording_started_at = now

        if expired is not None:
            self.on_record_stop(expired)
        self._start_capture(request)

    def request_hands_free(self, *, stop=False, valid=None, finished=None) -> bool:
        """Queue a Bar click on the native action thread, never the GUI thread."""
        with self._lock:
            native = self._native
            if (not self._listening or native is None
                    or (not self.is_recording if stop else self.is_recording)
                    or (stop and not self._locked)):
                return False
            expected = native, self._request, bool(stop), valid

        def action():
            try:
                self._on_hands_free_press(expected=expected)
            finally:
                if finished is not None:
                    finished()

        return bool(native.defer(action))

    def _on_hands_free_press(self, when=None, *, expected=None) -> None:
        session = None
        start = False
        valid = None
        with self._lock:
            if not self._listening:
                return
            if expected is not None:
                native, request, stop, valid = expected
                if (native is not self._native or request != self._request
                        or (not self.is_recording if stop else self.is_recording)
                        or (stop and not self._locked) or (valid is not None and not valid())):
                    return  # A queued click cannot start/stop a newer session.
            now = self.clock() if when is None else when
            if self._locked:
                session = self._finish_recording_locked(now, locked=True)
            else:
                start = not self.is_recording
                if start:
                    self._request += 1
                    request = self._request
                    self._recording_started_at = now
                self._cancel_tap_locked()
                self._second_tap = False
                self._locked = True
                # A superseded PTT chord's eventual release cannot stop the lock.
                self._pressed_hotkey = self._pressed_at = None
        if session is not None:
            self.on_record_stop(session)
        elif start:
            self._start_capture(request, valid)

    def _tap_window(self):
        return max(0, min(2, self.config.tap_lock_ms / 1000.0))

    def _on_record_release(self, hotkey: str, when=None) -> None:
        session: RecordingSession | None = None
        with self._lock:
            if self._pressed_hotkey != hotkey or self._pressed_at is None:
                return
            now = self.clock() if when is None else when
            press_duration = now - self._pressed_at

            if self._locked:
                session = self._finish_recording_locked(now, locked=True)
            elif self._second_tap and 0 <= press_duration < .3:
                self._locked = True
                self._pressed_hotkey = None
                self._pressed_at = None
                self._second_tap = False
            elif 0 <= press_duration < .3 and self._tap_window() > 0:
                token = object()
                delay = max(0, self._tap_window() - max(0, self.clock() - now))
                try:
                    timer = self._timer_factory(delay, lambda: self._queue_tap_expiry(token))
                    timer.daemon = True
                    self._tap = hotkey, now, token, timer
                    self._pressed_hotkey = self._pressed_at = None
                    self._second_tap = False
                    timer.start()
                except Exception:
                    session = self._finish_recording_locked(now, locked=False)
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
            session_id=self._session_id,
        )
        self._reset_recording_locked()
        return session
