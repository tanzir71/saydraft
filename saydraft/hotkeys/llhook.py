"""Owned native hook/message thread with bounded off-thread action dispatch."""

import ctypes as c
import math
import queue
import threading
import time

from saydraft.input_origin import SAYDRAFT_INPUT_TAG
from ._win32_hooks import KeyboardPacket, MousePacket, Win32Hooks
from .chords import ChordMatcher
from .keys import physical_key


class LowLevelHooks:
    def __init__(self, bindings, *, on_action, on_failure=lambda reason: None,
                 api_factory=Win32Hooks, clock=time.monotonic, capacity=64, thread_factory=threading.Thread):
        if type(capacity) is not int or not 2 <= capacity <= 256:
            raise ValueError("Hotkey action queue capacity must be between 2 and 256")
        self.matcher, self._on_action, self._on_failure = ChordMatcher(bindings), on_action, on_failure
        self._api_factory, self._clock, self._thread_factory = api_factory, clock, thread_factory
        self._queue = queue.Queue(capacity)
        self._lock = threading.RLock()
        self._stop, self._ready, self._pump_done = threading.Event(), threading.Event(), threading.Event()
        self._api = self._pump_thread = self._worker = self._reason = None
        self._started = False

    @property
    def completion_thread(self):
        """Finishes after native cleanup and the failure callback, for supervision."""
        return self._worker

    @property
    def status(self):
        with self._lock:
            pump = bool(self._pump_thread and self._pump_thread.is_alive())
            worker = bool(self._worker and self._worker.is_alive())
            return {"state": "failed" if self._reason else "stopping" if self._stop.is_set() and (pump or worker)
                else "closed" if self._stop.is_set() else "running" if self._ready.is_set() and pump and worker
                else "starting" if self._started else "new", "reason": self._reason,
                "pump_alive": pump, "worker_alive": worker}

    def start(self, timeout=2):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError("Hook startup wait must be finite and at most 30 seconds")
        with self._lock:
            if self._stop.is_set():
                raise RuntimeError("A stopped hook owner cannot be restarted")
            owner = not self._started
            if owner:
                self._started = True
                try:
                    self._worker = self._thread_factory(target=self._dispatch, name="Saydraft-hotkey-actions", daemon=True)
                    self._pump_thread = self._thread_factory(target=self._pump, name="Saydraft-native-hooks", daemon=True)
                except Exception:
                    self._fail("thread_start_failed")
                    self._pump_done.set()
                    self._ready.set()
                    raise
        if owner:
            try:
                self._worker.start()
                self._pump_thread.start()
            except Exception:
                self._fail("thread_start_failed")
                if self._pump_thread.ident is None:
                    self._pump_done.set()
                self.close()
                raise
        if not self._ready.wait(timeout) or self.status["state"] != "running":
            self._fail("startup_failed")
            self.close()
            raise OSError("Native hotkeys did not start")
        return True

    def _fail(self, reason):
        with self._lock:
            self._reason = self._reason or reason
        self._stop.set()
        if self._api is not None:
            try:
                self._api.wake()
            except Exception:
                pass

    def _stop_dispatch(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass  # A waiting consumer can already wake and observe _stop.

    def close(self, timeout=1):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 <= timeout <= 30:
            raise ValueError("Hook shutdown wait must be finite and at most 30 seconds")
        self._stop.set()
        if self._api is not None:
            try:
                self._api.wake()
            except Exception:
                pass
        self._stop_dispatch()
        until = time.monotonic() + timeout
        for thread in (self._pump_thread, self._worker):
            if thread is not None and thread is not threading.current_thread() and thread.ident is not None:
                thread.join(max(0, until - time.monotonic()))
        return not any(self.status[key] for key in ("pump_alive", "worker_alive"))

    def _pump(self):
        try:
            self._api = self._api_factory()
            if not self._stop.is_set():
                self._api.install(self._keyboard, self._mouse)
                self.matcher.seed(self._api.pressed_keys())
            self._ready.set()
            while not self._stop.is_set() and self._api.next_message():
                pass
            if not self._stop.is_set():
                self._fail("message_loop_stopped")
        except Exception:
            self._fail("native_hook_failed")
        finally:
            self._stop.set()
            if self._api is not None:
                try:
                    if self.matcher.reset().menu_mask:
                        self._api.mask()
                except Exception:
                    self._fail("mask_unavailable")
                try:
                    self._api.close()
                except Exception:
                    self._fail("unhook_failed")
            self._ready.set()
            self._pump_done.set()
            self._stop_dispatch()

    def _dispatch(self):
        try:
            while True:
                row = self._queue.get()
                if row is None or self._stop.is_set():
                    return
                transitions, when = row
                for transition in transitions:
                    if self._stop.is_set():
                        return
                    self._on_action(transition, when)
        except Exception:
            self._fail("action_failed")
        finally:
            self._pump_done.wait()  # Include removal failures before reporting outside the hook thread.
            if self._reason is not None:
                try:
                    self._on_failure(self._reason)
                except Exception:
                    pass

    def _event(self, key, down, origin):
        when = self._clock()
        decision = self.matcher.feed(key, down, ignore=origin == SAYDRAFT_INPUT_TAG)
        if decision.menu_mask:
            try:
                self._api.mask()
            except Exception:
                self._fail("mask_unavailable")
                return False
        if decision.transitions:
            try:
                self._queue.put_nowait((decision.transitions, when))
            except queue.Full:
                self._fail("action_queue_full")
                return False
        return decision.suppress

    def _keyboard(self, code, message, pointer):
        if code == 0 and self._ready.is_set() and not self._stop.is_set() and message in (0x100, 0x101, 0x104, 0x105) and pointer:
            try:
                value = c.cast(pointer, c.POINTER(KeyboardPacket)).contents
                key = physical_key(value.vkCode, scan=value.scanCode, extended=bool(value.flags & 1))
                if self._event(key, message in (0x100, 0x104), value.dwExtraInfo):
                    return 1
            except Exception:
                self._fail("keyboard_callback_failed")
        return self._forward(code, message, pointer)

    def _mouse(self, code, message, pointer):
        if code == 0 and self._ready.is_set() and not self._stop.is_set() and message in (0x201, 0x202, 0x204, 0x205, 0x207, 0x208, 0x20B, 0x20C) and pointer:
            try:
                value = c.cast(pointer, c.POINTER(MousePacket)).contents
                vk = {0x201: 1, 0x202: 1, 0x204: 2, 0x205: 2, 0x207: 4, 0x208: 4}.get(message)
                if vk is None:
                    button = value.mouseData >> 16
                    vk = {1: 5, 2: 6}.get(button)
                if self._event(physical_key(vk), message in (0x201, 0x204, 0x207, 0x20B), value.dwExtraInfo):
                    return 1
            except Exception:
                self._fail("mouse_callback_failed")
        return self._forward(code, message, pointer)

    def _forward(self, code, message, pointer):
        try:
            return self._api.forward(code, message, pointer)
        except Exception:
            self._fail("forward_failed")
            return 0
