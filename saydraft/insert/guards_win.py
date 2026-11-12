"""Read-only delivery preflight; never elevate or release a user's held keys."""

import ctypes as ct
from ctypes import wintypes as wt


class SidAttributes(ct.Structure):
    _fields_ = [("sid", ct.c_void_p), ("attributes", wt.DWORD)]


def integrity_rid(buffer, length):
    """Read the mandatory-label SID only after proving it lies in this buffer."""
    if not ct.sizeof(SidAttributes) <= length <= ct.sizeof(buffer):
        raise ValueError("Invalid integrity buffer length")
    address = ct.addressof(buffer)
    sid = SidAttributes.from_buffer(buffer).sid
    if not sid or not address <= sid <= address + length - 8:
        raise ValueError("Invalid integrity SID pointer")
    header = ct.string_at(sid, 8)
    count = header[1]
    if (header[0] != 1 or not 1 <= count <= 15 or header[2:] != b"\0\0\0\0\0\x10"
            or sid + 8 + count * 4 > address + length):
        raise ValueError("Invalid mandatory-label SID")
    return int.from_bytes(ct.string_at(sid + 8 + (count - 1) * 4, 4), "little")


class NativeDeliveryApi:
    def __init__(self):
        self.user = ct.WinDLL("user32", use_last_error=True)
        self.kernel = ct.WinDLL("kernel32", use_last_error=True)
        self.security = ct.WinDLL("advapi32", use_last_error=True)
        signatures = (
            (self.user, "GetForegroundWindow", [], wt.HWND),
            (self.user, "GetWindowThreadProcessId", [wt.HWND, ct.POINTER(wt.DWORD)], wt.DWORD),
            (self.user, "GetAsyncKeyState", [ct.c_int], wt.SHORT),
            (self.kernel, "GetCurrentProcess", [], wt.HANDLE),
            (self.kernel, "OpenProcess", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
            (self.kernel, "CloseHandle", [wt.HANDLE], wt.BOOL),
            (self.security, "OpenProcessToken", [wt.HANDLE, wt.DWORD, ct.POINTER(wt.HANDLE)], wt.BOOL),
            (self.security, "GetTokenInformation", [wt.HANDLE, ct.c_int, ct.c_void_p,
                                                   wt.DWORD, ct.POINTER(wt.DWORD)], wt.BOOL))
        for library, name, args, result in signatures:
            function = getattr(library, name)
            function.argtypes, function.restype = args, result

    def foreground(self):
        return self.user.GetForegroundWindow()

    def window_pid(self, window):
        pid = wt.DWORD()
        if not self.user.GetWindowThreadProcessId(window, ct.byref(pid)) or not pid.value:
            raise OSError("Target process is unavailable")
        return pid.value

    def integrity(self, pid=None):
        process = self.kernel.GetCurrentProcess() if pid is None else self.kernel.OpenProcess(0x1000, False, pid)
        if not process:
            raise OSError("Target process cannot be queried")
        token = wt.HANDLE()
        try:
            if not self.security.OpenProcessToken(process, 8, ct.byref(token)):  # TOKEN_QUERY only.
                raise OSError("Process token cannot be queried")
            try:
                needed = wt.DWORD()
                self.security.GetTokenInformation(token, 25, None, 0, ct.byref(needed))
                if not ct.sizeof(SidAttributes) + 12 <= needed.value <= 4096:
                    raise OSError("Integrity label is unavailable")
                buffer = ct.create_string_buffer(needed.value)
                if not self.security.GetTokenInformation(token, 25, buffer, len(buffer), ct.byref(needed)):
                    raise OSError("Integrity label query failed")
                return integrity_rid(buffer, needed.value)
            finally:
                self.kernel.CloseHandle(token)
        finally:
            if pid is not None:
                self.kernel.CloseHandle(process)

    def modifiers_down(self):
        return any(self.user.GetAsyncKeyState(key) & 0x8000
                   for key in (0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C))


class WindowsDeliveryGuard:
    def __init__(self, api=None):
        self.api = api

    def __call__(self, target):
        if type(target) is not int or target <= 0:
            return "unknown_target"
        try:
            if self.api is None:
                self.api = NativeDeliveryApi()
            api = self.api
            if api.foreground() != target:
                return "focus_changed"
            pid = api.window_pid(target)
            if api.integrity(pid) > api.integrity():
                return "target_elevated"
            if api.modifiers_down():
                return "modifier_held"
            if api.foreground() != target or api.window_pid(target) != pid:
                return "focus_changed"
            return ""
        except (OSError, ValueError, TypeError):
            return "integrity_unavailable"
