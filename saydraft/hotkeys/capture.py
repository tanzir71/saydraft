"""Bounded shortcut learning; retains key identifiers only for one explicit attempt."""

import ctypes as c
import math
import os
import time
from ctypes import wintypes as w

from .chords import Chord, Decision, Transition
from .keys import MODIFIERS, normalize_key

MAX_CAPTURE_SECONDS = 10
_MOUSE_CONTROLS = frozenset(("left_mouse", "right_mouse", "middle_mouse"))
_MENU_KEYS = MODIFIERS["win"] | MODIFIERS["alt"]


class OwnedWindowGuard:
    """Read only the specified window's owner and current foreground handle."""

    def __init__(self, window, *, user=None, process_id=None):
        if type(window) is not int or not 0 < window < 2 ** (c.sizeof(c.c_void_p) * 8):
            raise ValueError("Shortcut learning requires an owned window")
        self.window = window
        self.process_id = os.getpid() if process_id is None else process_id
        self.user = user or c.WinDLL("user32.dll", winmode=0x800, use_last_error=True)
        self.user.GetForegroundWindow.argtypes, self.user.GetForegroundWindow.restype = [], w.HWND
        self.user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        self.user.GetWindowThreadProcessId.restype = w.DWORD
        if not self._owned():
            raise OSError("Shortcut learning requires an owned window")

    def _owned(self):
        process = w.DWORD()
        return bool(self.user.GetWindowThreadProcessId(self.window, c.byref(process))
                    and process.value == self.process_id)

    def __call__(self):
        return self.user.GetForegroundWindow() == self.window and self._owned()


class ChordCapture:
    """Matcher protocol for a temporary hook placed ahead of normal hotkeys."""

    def __init__(self, *, valid, clock=time.monotonic, seconds=MAX_CAPTURE_SECONDS):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= MAX_CAPTURE_SECONDS:
            raise ValueError("Shortcut learning must end within ten seconds")
        self.valid, self.clock = valid, clock
        self.deadline = clock() + seconds
        self._waiting, self._blocked, self._keys = set(), set(), set()
        self.done = False

    def seed(self, keys):
        keys = frozenset(keys)
        if len(keys) > 254 or any(key in MODIFIERS or normalize_key(key) != key for key in keys):
            raise ValueError("Expected bounded physical key state")
        self._waiting = set(keys)

    def _finish(self, phase, chord=""):
        self.done = True
        self._keys.clear()
        return (Transition(chord, phase),)

    def feed(self, key, down, *, ignore=False):
        if ignore or key is None:
            return Decision()
        if type(down) is not bool or not isinstance(key, str) or key in MODIFIERS or normalize_key(key) != key:
            raise ValueError("Expected a canonical physical key event")
        suppressed = key in self._blocked
        mask = not down and suppressed and key in _MENU_KEYS
        if not down:
            self._blocked.discard(key)
        if self.done:
            return Decision(suppress=suppressed, menu_mask=mask)
        if self.clock() >= self.deadline:
            return Decision(self._finish("expired"), suppressed, mask)
        try:
            allowed = bool(self.valid())
        except Exception:
            allowed = False
        if not allowed:
            return Decision(self._finish("cancelled"), suppressed, mask)
        if self._waiting:
            if down:
                self._waiting.add(key)
            else:
                self._waiting.discard(key)
            return Decision(menu_mask=not down and key in _MENU_KEYS)
        if key in _MOUSE_CONTROLS:
            # The setup's Cancel button and focus changes must still work.
            return Decision(self._finish("cancelled") if down else ())
        if down:
            self._blocked.add(key)
            suppressed = True
            if key == "esc":
                return Decision(self._finish("cancelled"), suppressed, mask)
            generic = next((name for name, sides in MODIFIERS.items() if key in sides), key)
            self._keys.add(generic)
            if len(self._keys) > 8 or len(self._keys - MODIFIERS.keys()) > 1:
                return Decision(self._finish("invalid"), suppressed, mask)
        elif suppressed and not self._blocked:
            order = ("ctrl", "win", "alt", "shift")
            chord = "+".join([key for key in order if key in self._keys] + sorted(self._keys - set(order)))
            try:
                Chord.parse(chord)
            except ValueError:
                return Decision(self._finish("invalid"), suppressed, mask)
            return Decision(self._finish("captured", chord), suppressed, mask)
        return Decision(suppress=suppressed, menu_mask=mask)

    def reset(self):
        mask = bool(self._blocked & _MENU_KEYS)
        self._waiting.clear()
        self._blocked.clear()
        self._keys.clear()
        self.done = True
        return Decision(menu_mask=mask)
