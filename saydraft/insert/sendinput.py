"""Batched Unicode SendInput for fields that block clipboard paste."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _KeyboardInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput), ("ki", _KeyboardInput), ("hi", _HardwareInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("data", _InputUnion)]


def unicode_events(text: str) -> list[_Input]:
    encoded = text.encode("utf-16-le")
    events = []
    for index in range(0, len(encoded), 2):
        unit = int.from_bytes(encoded[index:index + 2], "little")
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            event = _Input()
            event.type = 1  # INPUT_KEYBOARD
            event.data.ki = _KeyboardInput(0, unit, flags, 0, 0)
            events.append(event)
    return events


def type_unicode(text: str, *, sender=None) -> None:
    events = unicode_events(text)
    if not events:
        return
    if sender is None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        sender = user32.SendInput
    # Keep every key-down/up pair in the same batch, including surrogate units.
    for offset in range(0, len(events), 256):
        batch = events[offset:offset + 256]
        inputs = (_Input * len(batch))(*batch)
        accepted = sender(len(inputs), inputs, ctypes.sizeof(_Input))
        if accepted != len(inputs):
            raise OSError(f"Windows accepted only {accepted} of {len(inputs)} text input events")
