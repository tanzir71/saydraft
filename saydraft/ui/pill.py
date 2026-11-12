"""Saydraft Bar compatibility entry point."""

from __future__ import annotations

import ctypes  # noqa: F401 - compatibility for integrations instrumenting native access.

from PySide6 import QtCore, QtGui  # noqa: F401

from .bar_widget import LevelMeter, PillState, PreviewStrip, SaydraftPill  # noqa: F401


def focused_window_center() -> QtCore.QPoint | None:
    """Return the selected screen center in Qt logical coordinates.

    Native HWND rectangle centers are physical pixels and must not be passed
    directly to Qt's screenAt() on mixed-DPI Windows desktops.
    """
    from .bar_placement import focused_screen, native_desktop_enabled
    if not native_desktop_enabled():
        return None
    screen = focused_screen()
    return screen.geometry().center() if screen is not None else None
