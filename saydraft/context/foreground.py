"""Read bounded foreground identity without sending messages to our GUI."""

import ctypes as ct
import ntpath
import sys
from ctypes import wintypes as wt

from saydraft.core.interfaces import TargetContext
from .app_groups import app_group, browser_site


class NativeForegroundApi:
    def __init__(self):
        self.user = ct.WinDLL("user32", use_last_error=True)
        self.kernel = ct.WinDLL("kernel32", use_last_error=True)
        signatures = (
            (self.user, "GetForegroundWindow", [], wt.HWND),
            (self.user, "GetWindowThreadProcessId", [wt.HWND, ct.POINTER(wt.DWORD)], wt.DWORD),
            (self.user, "GetWindowTextW", [wt.HWND, wt.LPWSTR, ct.c_int], ct.c_int),
            (self.kernel, "GetCurrentProcessId", [], wt.DWORD),
            (self.kernel, "OpenProcess", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
            (self.kernel, "QueryFullProcessImageNameW",
             [wt.HANDLE, wt.DWORD, wt.LPWSTR, ct.POINTER(wt.DWORD)], wt.BOOL),
            (self.kernel, "CloseHandle", [wt.HANDLE], wt.BOOL))
        for library, name, args, result in signatures:
            function = getattr(library, name)
            function.argtypes, function.restype = args, result

    def foreground(self):
        return self.user.GetForegroundWindow()

    def window_pid(self, window):
        pid = wt.DWORD()
        if not self.user.GetWindowThreadProcessId(window, ct.byref(pid)) or not pid.value:
            raise OSError("Foreground process unavailable")
        return pid.value

    def title(self, window, pid):
        # GetWindowText sends WM_GETTEXT to same-process windows, which could
        # wait for our GUI while it is waiting for the worker's session lock.
        if pid == self.kernel.GetCurrentProcessId():
            return ""
        buffer = ct.create_unicode_buffer(4097)
        self.user.GetWindowTextW(window, buffer, len(buffer))
        return buffer.value

    def executable(self, pid):
        process = self.kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION only.
        if not process:
            raise OSError("Foreground image unavailable")
        try:
            buffer = ct.create_unicode_buffer(32768)
            length = wt.DWORD(len(buffer))
            if (not self.kernel.QueryFullProcessImageNameW(process, 0, buffer, ct.byref(length))
                    or not 0 < length.value < len(buffer)):
                raise OSError("Foreground image unavailable")
            return ntpath.basename(buffer.value).casefold()
        finally:
            if not self.kernel.CloseHandle(process):
                raise OSError("Foreground process handle could not close")


class ForegroundContextProvider:
    def __init__(self, *, api=None, profiles=()):
        self.api, self.profiles = api, profiles

    def _native(self):
        if self.api is None and sys.platform == "win32":
            self.api = NativeForegroundApi()
        return self.api

    def focus(self):
        """Delivery checks need only HWND, never title, image or future UIA calls."""
        api = self._native()
        return (api.foreground() or None) if api is not None else None

    def capture(self):
        api = self._native()
        if api is None:
            return TargetContext()
        try:
            window = api.foreground()
            if not window:
                return TargetContext()
            pid = api.window_pid(window)
            title = api.title(window, pid)
            try:
                exe = api.executable(pid)
            except OSError:
                exe = ""  # A protected process may still have a usable HWND/title.
            if api.foreground() != window or api.window_pid(window) != pid:
                return TargetContext()
            site = browser_site(exe, title)
            return TargetContext(focus=int(window), app_title=title or None, app_exe=exe,
                                 app_group=app_group(exe, site, self.profiles), app_site=site)
        except OSError:
            return TargetContext()
