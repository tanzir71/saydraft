"""Windows-only low-level hook ABI and tagged, balanced menu-mask input."""

import ctypes as c
import os
from ctypes import wintypes as w

from saydraft.input_origin import SAYDRAFT_INPUT_TAG
from saydraft.insert.sendinput import _Input, _KeyboardInput
from .keys import physical_key


class KeyboardPacket(c.Structure):
    _fields_ = [("vkCode", w.DWORD), ("scanCode", w.DWORD), ("flags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", c.c_size_t)]


class MousePacket(c.Structure):
    _fields_ = [("pt", w.POINT), ("mouseData", w.DWORD), ("flags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", c.c_size_t)]


def mask_input(sender):
    inputs = (_Input * 2)()
    for value, flags in zip(inputs, (0, 2)):
        value.type = 1
        value.data.ki = _KeyboardInput(0xE8, 0, flags, 0, SAYDRAFT_INPUT_TAG)
    if sender(2, inputs, c.sizeof(_Input)) != 2:
        # Release only: never repeat a partially accepted press.
        try:
            sender(1, (_Input * 1)(inputs[1]), c.sizeof(_Input))
        except Exception:
            pass
        raise OSError("Menu-mask input unavailable")


class Win32Hooks:
    def __init__(self):
        if os.name != "nt":
            raise OSError("Native hotkeys require Windows")
        self.user = c.WinDLL("user32", use_last_error=True)
        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.proc = c.WINFUNCTYPE(c.c_ssize_t, c.c_int, w.WPARAM, w.LPARAM)
        signatures = {
            "SetWindowsHookExW": (w.HANDLE, [c.c_int, self.proc, w.HMODULE, w.DWORD]),
            "UnhookWindowsHookEx": (w.BOOL, [w.HANDLE]),
            "CallNextHookEx": (c.c_ssize_t, [w.HANDLE, c.c_int, w.WPARAM, w.LPARAM]),
            "PeekMessageW": (w.BOOL, [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]),
            "GetMessageW": (c.c_int, [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]),
            "PostThreadMessageW": (w.BOOL, [w.DWORD, w.UINT, w.WPARAM, w.LPARAM]),
            "SendInput": (w.UINT, [w.UINT, c.POINTER(_Input), c.c_int]),
            "GetAsyncKeyState": (c.c_short, [c.c_int]),
            "GetSystemMetrics": (c.c_int, [c.c_int]),
        }
        for name, (result, arguments) in signatures.items():
            function = getattr(self.user, name)
            function.restype, function.argtypes = result, arguments
        self.kernel.GetCurrentThreadId.restype = w.DWORD
        self.kernel.GetModuleHandleW.restype, self.kernel.GetModuleHandleW.argtypes = w.HMODULE, [w.LPCWSTR]
        self.thread_id, self.handles, self.callbacks = None, [], ()
        self.message = w.MSG()

    def install(self, keyboard, mouse):
        self.thread_id = self.kernel.GetCurrentThreadId()
        self.user.PeekMessageW(c.byref(self.message), None, 0x400, 0x400, 0)
        self.callbacks = self.proc(keyboard), self.proc(mouse)
        for kind, callback in zip((13, 14), self.callbacks):
            handle = self.user.SetWindowsHookExW(kind, callback, self.kernel.GetModuleHandleW(None), 0)
            if not handle:
                raise OSError("Native hook installation unavailable")
            self.handles.append(handle)

    def next_message(self):
        result = self.user.GetMessageW(c.byref(self.message), None, 0, 0)
        if result == -1:
            raise OSError("Native hook message loop unavailable")
        return result != 0

    def pressed_keys(self):
        swapped = bool(self.user.GetSystemMetrics(23))
        return {physical_key(3 - vk if swapped and vk in (1, 2) else vk) for vk in range(1, 255)
                if vk not in (0x10, 0x11, 0x12) and self.user.GetAsyncKeyState(vk) & 0x8000}

    def forward(self, code, message, pointer):
        return self.user.CallNextHookEx(None, code, message, pointer)

    def wake(self):
        if self.thread_id is not None:
            return bool(self.user.PostThreadMessageW(self.thread_id, 0x12, 0, 0))
        return False

    def mask(self):
        mask_input(self.user.SendInput)

    def close(self):
        failed = False
        for handle in reversed(self.handles[:]):
            if self.user.UnhookWindowsHookEx(handle):
                self.handles.remove(handle)
            else:
                failed = True
        if failed:
            raise OSError("Native hook removal unavailable")
