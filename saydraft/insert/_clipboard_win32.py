"""Explicit clipboard ABI; eager data only, with a transient message-only owner."""

import ctypes as ct
import time
from contextlib import contextmanager
from ctypes import wintypes as wt

from .clipboard_handles import ClipboardHandles, ClipboardUnavailable

PRIVACY_FORMATS = ("ExcludeClipboardContentFromMonitorProcessing", "CanIncludeInClipboardHistory",
                   "CanUploadToCloudClipboard")


class NativeClipboardApi(ClipboardHandles):
    def __init__(self):
        super().__init__()
        self.user = ct.WinDLL("user32", use_last_error=True)
        signatures = (
            ("OpenClipboard", [wt.HWND], wt.BOOL), ("CloseClipboard", [], wt.BOOL),
            ("EmptyClipboard", [], wt.BOOL), ("EnumClipboardFormats", [wt.UINT], wt.UINT),
            ("GetClipboardData", [wt.UINT], wt.HANDLE),
            ("SetClipboardData", [wt.UINT, wt.HANDLE], wt.HANDLE),
            ("GetClipboardSequenceNumber", [], wt.DWORD), ("GetClipboardOwner", [], wt.HWND),
            ("GetWindowThreadProcessId", [wt.HWND, ct.POINTER(wt.DWORD)], wt.DWORD),
            ("RegisterClipboardFormatW", [wt.LPCWSTR], wt.UINT),
            ("DestroyWindow", [wt.HWND], wt.BOOL),
            ("CreateWindowExW", [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ct.c_int, ct.c_int,
                ct.c_int, ct.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, ct.c_void_p], wt.HWND))
        for name, args, result in signatures:
            function = getattr(self.user, name)
            function.argtypes, function.restype = args, result
        self.privacy = tuple(self.user.RegisterClipboardFormatW(name) for name in PRIVACY_FORMATS)
        if not all(self.privacy):
            raise ClipboardUnavailable("Clipboard privacy formats are unavailable")

    @contextmanager
    def window(self):
        hwnd = self.user.CreateWindowExW(0, "STATIC", "Saydraft clipboard", 0, 0, 0, 0, 0,
                                        ct.c_void_p(-3), None, None, None)  # HWND_MESSAGE.
        if not hwnd:
            raise ClipboardUnavailable("Clipboard owner window is unavailable")
        try:
            yield hwnd
        finally:
            if not self.user.DestroyWindow(hwnd):
                raise ClipboardUnavailable("Clipboard owner window did not retire")

    @contextmanager
    def opened(self, hwnd, *, clock=time.monotonic, sleep=time.sleep):
        deadline = clock() + .35
        while not self.user.OpenClipboard(hwnd):
            if clock() >= deadline:
                raise ClipboardUnavailable("Clipboard is busy")
            sleep(.01)
        try:
            yield
        finally:
            if not self.user.CloseClipboard():
                raise ClipboardUnavailable("Clipboard did not close")

    def formats(self):
        current, seen = 0, set()
        for _ in range(4097):
            ct.set_last_error(0)
            current = self.user.EnumClipboardFormats(current)
            if not current:
                if ct.get_last_error():
                    raise ClipboardUnavailable("Clipboard enumeration failed")
                return
            if current in seen or len(seen) == 4096:
                raise ClipboardUnavailable("Clipboard format table exceeds its limit")
            seen.add(current)
            yield current

    def get(self, format):
        return self.user.GetClipboardData(format)

    def empty(self):
        if not self.user.EmptyClipboard():
            raise ClipboardUnavailable("Clipboard could not be emptied")

    def put(self, copy):
        if not copy.handle or not self.user.SetClipboardData(copy.format, copy.handle):
            raise ClipboardUnavailable("Clipboard format publication failed")
        copy.transfer()

    def sequence(self):
        return self.user.GetClipboardSequenceNumber()

    def owner(self):
        return self.user.GetClipboardOwner()

    def window_pid(self, hwnd):
        pid = wt.DWORD()
        if not hwnd or not self.user.GetWindowThreadProcessId(hwnd, ct.byref(pid)) or not pid.value:
            raise OSError("Clipboard owner process is unavailable")
        return pid.value
