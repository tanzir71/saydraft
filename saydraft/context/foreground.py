"""Read bounded foreground identity without sending messages to our GUI."""

import ctypes as ct
import ntpath
import sys
import threading
from ctypes import wintypes as wt

from saydraft.core.interfaces import TargetContext
from .app_groups import app_group, browser_site
from .focused_edit import FocusedEdit


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
    def __init__(self, *, api=None, profiles=(), uia=None, use_uia=False):
        self.api, self.profiles = api, profiles
        self._uia, self._use_uia, self._closed = uia, use_uia or uia is not None, False
        self._uia_lock = threading.Lock()

    def prepare(self):
        with self._uia_lock:
            if self._use_uia and self._uia is None and not self._closed:
                from .uia_worker import BoundedUIA
                self._uia = BoundedUIA()

    def set_profiles(self, profiles):
        self.profiles = profiles

    def close(self):
        with self._uia_lock:
            self._closed = True
            uia = self._uia
        return uia.close() if uia is not None else True

    def _field(self, window, *, include_text=True):
        if self._closed:
            return FocusedEdit()
        if not self._use_uia:
            return FocusedEdit(status="not_requested")
        try:
            self.prepare()
            return self._uia.query(int(window), include_text=include_text)
        except Exception:
            return FocusedEdit()

    def _native(self):
        if self.api is None and sys.platform == "win32":
            self.api = NativeForegroundApi()
        return self.api

    def focus(self):
        """Delivery checks need only HWND, never title, image or future UIA calls."""
        if self._closed:
            return None
        api = self._native()
        return (api.foreground() or None) if api is not None else None

    def capture(self):
        if self._closed:
            return TargetContext()
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
            field = self._field(window)
            if api.foreground() != window or api.window_pid(window) != pid:
                return TargetContext()
            site = browser_site(exe, title)
            return TargetContext(focus=int(window), app_title=title or None, app_exe=exe,
                app_group=app_group(exe, site, self.profiles), app_site=site, process_id=pid,
                is_password=field.is_password, before_caret=field.before_caret, selection=field.selection,
                uia_status=field.status, control_type=field.control_type, field_id=field.runtime_id,
                selection_truncated=field.selection_truncated)
        except OSError:
            return TargetContext()

    def verify(self, target):
        """Fresh metadata-only check for the captured field, with no caret/selection read."""
        if self._closed:
            return "field_unavailable"
        if target.is_password:
            return "password_field"
        if target.uia_status == "not_requested" and not self._use_uia:
            return ""
        if target.uia_status != "ok" or not target.field_id:
            return "focus_changed" if target.uia_status == "changed" else "field_unavailable"
        try:
            api = self._native()
            if api.foreground() != target.focus or api.window_pid(target.focus) != target.process_id:
                return "focus_changed"
            field = self._field(target.focus, include_text=False)
            if field.is_password:
                return "password_field"
            if field.status != "ok":
                return "focus_changed" if field.status == "changed" else "field_unavailable"
            if (field.runtime_id != target.field_id or api.foreground() != target.focus
                    or api.window_pid(target.focus) != target.process_id):
                return "focus_changed"
            return ""
        except Exception:
            return "field_unavailable"
