"""Create a hidden process inside a kill-on-close Job Object from its first instruction.

Windows 10 JOB_LIST closes the create-then-assign orphan window. HANDLE_LIST
inherits only NUL for standard I/O, never the job handle or unrelated app handles.
"""

from __future__ import annotations

import ctypes as c
import math
import os
import subprocess
import threading
from ctypes import wintypes as w
from pathlib import Path


class _Security(c.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", c.c_void_p), ("inherit", w.BOOL)]


class _Startup(c.Structure):
    _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR), ("title", w.LPWSTR)] + [
        (name, w.DWORD) for name in ("x", "y", "width", "height", "chars_x", "chars_y", "fill", "flags")
    ] + [("show", w.WORD), ("reserved_size", w.WORD), ("reserved_bytes", c.c_void_p),
         ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]


class _StartupEx(c.Structure):
    _fields_ = [("startup", _Startup), ("attributes", c.c_void_p)]


class _ProcessInfo(c.Structure):
    _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]


class _BasicLimits(c.Structure):
    _fields_ = [("process_time", c.c_int64), ("job_time", c.c_int64), ("flags", w.DWORD),
        ("working_min", c.c_size_t), ("working_max", c.c_size_t), ("processes", w.DWORD),
        ("affinity", c.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]


class _JobLimits(c.Structure):
    _fields_ = [("basic", _BasicLimits), ("io", c.c_uint64 * 6)] + [
        (name, c.c_size_t) for name in ("process_memory", "job_memory", "peak_process_memory", "peak_job_memory")]


def _kernel():
    if os.name != "nt":
        raise OSError("Local sidecar process ownership requires Windows 10 or newer")
    kernel = c.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": (w.HANDLE, [c.c_void_p, w.LPCWSTR]),
        "SetInformationJobObject": (w.BOOL, [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]),
        "TerminateJobObject": (w.BOOL, [w.HANDLE, w.UINT]),
        "CreateFileW": (w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, c.POINTER(_Security), w.DWORD, w.DWORD, w.HANDLE]),
        "InitializeProcThreadAttributeList": (w.BOOL, [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)]),
        "UpdateProcThreadAttribute": (w.BOOL, [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t,
                                               c.c_void_p, c.POINTER(c.c_size_t)]),
        "DeleteProcThreadAttributeList": (None, [c.c_void_p]),
        "CreateProcessW": (w.BOOL, [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD,
                                     c.c_void_p, w.LPCWSTR, c.POINTER(_StartupEx), c.POINTER(_ProcessInfo)]),
        "WaitForSingleObject": (w.DWORD, [w.HANDLE, w.DWORD]),
        "GetExitCodeProcess": (w.BOOL, [w.HANDLE, c.POINTER(w.DWORD)]),
        "CloseHandle": (w.BOOL, [w.HANDLE]),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(kernel, name)
        function.restype, function.argtypes = result, arguments
    return kernel


def _check(value):
    if not value:
        raise c.WinError(c.get_last_error())
    return value


def _environment(values):
    seen = set()
    for key, value in values.items():
        if (not isinstance(key, str) or not key or "=" in key or "\0" in key
                or not isinstance(value, str) or "\0" in value or key.casefold() in seen):
            raise ValueError("Child environment must contain unique valid names and strings")
        seen.add(key.casefold())
    return c.create_unicode_buffer("\0".join(f"{key}={values[key]}" for key in sorted(values, key=str.casefold)) + "\0\0")


class WindowsJobProcess:
    def __init__(self, argv, *, env, cwd=None):
        self._lock = threading.RLock()
        self._job = self._process = None
        self._api = _kernel()
        if not argv or any(not isinstance(value, str) or "\0" in value for value in argv):
            raise ValueError("Process arguments must be nonempty strings without NUL")
        executable = Path(argv[0])
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("Executable must be an existing absolute file")
        working = Path(cwd) if cwd is not None else executable.parent
        if not working.is_absolute() or not working.is_dir():
            raise ValueError("Working directory must be an existing absolute directory")
        environment = _environment(env)  # No implicit inheritance of environment variables.
        info, attributes, null = _ProcessInfo(), None, None
        try:
            self._job = _check(self._api.CreateJobObjectW(None, None))
            limits = _JobLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; breakaway stays disabled.
            _check(self._api.SetInformationJobObject(self._job, 9, c.byref(limits), c.sizeof(limits)))
            security = _Security(c.sizeof(_Security), None, True)
            null = self._api.CreateFileW("NUL", 0xC0000000, 3, c.byref(security), 3, 0x80, None)
            if null in (None, c.c_void_p(-1).value):
                raise c.WinError(c.get_last_error())
            size = c.c_size_t()
            self._api.InitializeProcThreadAttributeList(None, 2, 0, c.byref(size))
            if not size.value:
                raise c.WinError(c.get_last_error())
            buffer = c.create_string_buffer(size.value)
            _check(self._api.InitializeProcThreadAttributeList(buffer, 2, 0, c.byref(size)))
            attributes = c.cast(buffer, c.c_void_p)
            handles, jobs = (w.HANDLE * 1)(null), (w.HANDLE * 1)(self._job)
            for attribute, values in ((0x20002, handles), (0x2000D, jobs)):
                _check(self._api.UpdateProcThreadAttribute(attributes, 0, attribute, c.byref(values),
                                                          c.sizeof(values), None, None))
            startup = _StartupEx()
            startup.startup.cb = c.sizeof(startup)
            startup.startup.flags = 0x101  # STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW (SW_HIDE).
            startup.startup.stdin = startup.startup.stdout = startup.startup.stderr = null
            startup.attributes = attributes
            command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
            _check(self._api.CreateProcessW(str(executable), command, None, None, True,
                0x08000000 | 0x00080000 | 0x00000400, environment, str(working), c.byref(startup), c.byref(info)))
            self._process, self.pid = info.process, int(info.pid)
        except BaseException:
            unadopted = info.process if self._process is None else None
            self.close()  # Closing the job also covers errors after successful process creation.
            if unadopted:
                self._api.CloseHandle(unadopted)
            raise
        finally:
            if info.thread:
                self._api.CloseHandle(info.thread)
            if attributes:
                self._api.DeleteProcThreadAttributeList(attributes)
            if null not in (None, c.c_void_p(-1).value):
                self._api.CloseHandle(null)

    def _wait(self, milliseconds):
        if self._process is None:
            raise RuntimeError("Process handle is closed")
        result = self._api.WaitForSingleObject(self._process, milliseconds)
        if result == 258:  # WAIT_TIMEOUT
            return None
        if result != 0:
            raise c.WinError(c.get_last_error())
        code = w.DWORD()
        _check(self._api.GetExitCodeProcess(self._process, c.byref(code)))
        return int(code.value)  # Even exit code 259 is valid once the handle is signalled.

    def poll(self):
        with self._lock:
            return self._wait(0)

    def wait(self, timeout=1):
        if not math.isfinite(timeout) or not 0 <= timeout < 0xFFFFFFFE / 1000:
            raise ValueError("Wait timeout must be finite and nonnegative")
        with self._lock:
            code = self._wait(math.ceil(timeout * 1000))
            if code is None:
                raise TimeoutError("Local process did not exit before the deadline")
            return code

    def terminate(self):
        with self._lock:
            if self._job is not None:
                _check(self._api.TerminateJobObject(self._job, 1))

    def close(self):
        with self._lock:
            if self._job is not None:
                _check(self._api.CloseHandle(self._job))
                self._job = None
            if self._process is not None:
                _check(self._api.CloseHandle(self._process))
                self._process = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass  # Kernel handle closure on owner exit remains the final safeguard.
