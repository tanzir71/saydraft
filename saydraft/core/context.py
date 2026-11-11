"""Initial Windows foreground adapter; UI Automation enrichment follows P5.3."""

from __future__ import annotations

import sys

from .interfaces import TargetContext


class ForegroundContextProvider:
    def capture(self) -> TargetContext:
        if sys.platform != "win32":
            return TargetContext()
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        window = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(window)
        text = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(window, text, len(text))
        return TargetContext(focus=int(window) if window else None, app_title=text.value or None)
