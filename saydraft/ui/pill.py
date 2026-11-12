"""Saydraft Bar compatibility entry point and foreground placement helpers."""

from __future__ import annotations

import ctypes
import sys

from PySide6 import QtCore, QtGui

from .bar_widget import LevelMeter, PillState, PreviewStrip, SaydraftPill  # noqa: F401


def focused_window_center() -> QtCore.QPoint | None:
    if (QtGui.QGuiApplication.instance() is not None
            and QtGui.QGuiApplication.platformName() in ("offscreen", "minimal")):
        return None
    if sys.platform != "win32":
        return QtGui.QCursor.pos()

    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        rect = wintypes_RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return QtGui.QCursor.pos()
        return QtCore.QPoint(
            int((rect.left + rect.right) / 2),
            int((rect.top + rect.bottom) / 2),
        )
    except Exception:
        return QtGui.QCursor.pos()


class wintypes_RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]
