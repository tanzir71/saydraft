"""Advisory Ctrl+Win clash detection; no command lines or process control."""

import ctypes as ct
import sys
from ctypes import wintypes as wt

from .chords import Chord


class ProcessEntry(ct.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ct.c_size_t), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", wt.LONG), ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260)]


def wispr_running(*, kernel=None):
    """Return True/False, or None when the process snapshot cannot be checked."""
    if sys.platform != "win32" and kernel is None:
        return None
    kernel = kernel or ct.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wt.HANDLE
    for name in ("Process32FirstW", "Process32NextW"):
        function = getattr(kernel, name)
        function.argtypes, function.restype = [wt.HANDLE, ct.POINTER(ProcessEntry)], wt.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [wt.HANDLE], wt.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS only; not inheritable.
    if snapshot in (None, ct.c_void_p(-1).value):
        return None
    try:
        entry = ProcessEntry(dwSize=ct.sizeof(ProcessEntry))
        present = kernel.Process32FirstW(snapshot, ct.byref(entry))
        for _ in range(65536):
            if not present:
                return False if ct.get_last_error() == 18 else None  # ERROR_NO_MORE_FILES
            if entry.szExeFile.casefold() == "wispr flow.exe":
                return True
            present = kernel.Process32NextW(snapshot, ct.byref(entry))
        return None
    finally:
        kernel.CloseHandle(snapshot)


def shortcut_warning(hotkeys, *, detector=wispr_running):
    """Other apps' custom bindings are unknown; report a possible default clash."""
    default = Chord.parse("ctrl+win")
    for name in ("speech", "speech_alternative", "speech_mouse", "hands_free", "paste_last", "scratchpad", "view_diff", "save", "cancel"):
        try:
            chord = Chord.parse(hotkeys.get(name, ""))
        except ValueError:
            continue  # The shared compiler reports invalid bindings separately.
        if any(default.held(state) for state in chord.possibilities()):
            if detector() is True:
                return ("Wispr Flow is running and may also use Ctrl+Win. "
                        "Rebind a shortcut in Settings or quit Wispr Flow.")
            break
    return ""
