"""Create a hidden process inside a kill-on-close Job Object from its first instruction.

Windows 10 JOB_LIST closes the create-then-assign orphan window. HANDLE_LIST
inherits only NUL for inference I/O. Short metadata probes may opt into a bounded
output pipe. Explicit streaming consumers receive small chunks without retained
output; their stderr stays NUL. No mode inherits the job or unrelated handles.
"""

from __future__ import annotations

import ctypes as c
import math
import os
import subprocess
import threading
import time
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


class _Accounting(c.Structure):
    _fields_ = [(name, c.c_int64) for name in ('user', 'kernel', 'period_user', 'period_kernel')] + [
        (name, w.DWORD) for name in ('page_faults', 'total_processes', 'active_processes', 'terminated_processes')]


def _kernel():
    if os.name != "nt":
        raise OSError("Local sidecar process ownership requires Windows 10 or newer")
    kernel = c.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": (w.HANDLE, [c.c_void_p, w.LPCWSTR]),
        "SetInformationJobObject": (w.BOOL, [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]),
        "TerminateJobObject": (w.BOOL, [w.HANDLE, w.UINT]),
        "CreateFileW": (w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, c.POINTER(_Security), w.DWORD, w.DWORD, w.HANDLE]),
        "CreatePipe": (w.BOOL, [c.POINTER(w.HANDLE), c.POINTER(w.HANDLE), c.POINTER(_Security), w.DWORD]),
        "SetHandleInformation": (w.BOOL, [w.HANDLE, w.DWORD, w.DWORD]),
        "ReadFile": (w.BOOL, [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]),
        "InitializeProcThreadAttributeList": (w.BOOL, [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)]),
        "UpdateProcThreadAttribute": (w.BOOL, [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t,
                                               c.c_void_p, c.POINTER(c.c_size_t)]),
        "DeleteProcThreadAttributeList": (None, [c.c_void_p]),
        "CreateProcessW": (w.BOOL, [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD,
                                     c.c_void_p, w.LPCWSTR, c.POINTER(_StartupEx), c.POINTER(_ProcessInfo)]),
        "WaitForSingleObject": (w.DWORD, [w.HANDLE, w.DWORD]),
        "GetExitCodeProcess": (w.BOOL, [w.HANDLE, c.POINTER(w.DWORD)]),
        "QueryInformationJobObject": (w.BOOL, [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]),
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
    def __init__(self, argv, *, env, cwd=None, capture_output=False, max_output_bytes=65536, on_output=None):
        self._lock = threading.RLock()
        self._job = self._process = None
        self._reader = self._read_handle = None
        self._read_ready, self._read_abort = threading.Event(), False
        self._output, self._output_error, self._output_done = bytearray(), None, threading.Event()
        if type(capture_output) is not bool or type(max_output_bytes) is not int or not 1 <= max_output_bytes <= 1024**2:
            raise ValueError("Native output capture requires a bounded byte limit")
        if on_output is not None and (not callable(on_output) or capture_output):
            raise ValueError('Streaming output needs a callable consumer and cannot retain metadata output')
        self._capture, self._output_limit = capture_output, max_output_bytes
        self._on_output = on_output
        has_output = capture_output or on_output is not None
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
        info, attributes, null, write_pipe = _ProcessInfo(), None, None, None
        try:
            self._job = _check(self._api.CreateJobObjectW(None, None))
            limits = _JobLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; breakaway stays disabled.
            _check(self._api.SetInformationJobObject(self._job, 9, c.byref(limits), c.sizeof(limits)))
            security = _Security(c.sizeof(_Security), None, True)
            null = self._api.CreateFileW("NUL", 0xC0000000, 3, c.byref(security), 3, 0x80, None)
            if null in (None, c.c_void_p(-1).value):
                raise c.WinError(c.get_last_error())
            if has_output:
                read, write = w.HANDLE(), w.HANDLE()
                _check(self._api.CreatePipe(c.byref(read), c.byref(write), c.byref(security), 0))
                self._read_handle, write_pipe = read.value, write.value
                _check(self._api.SetHandleInformation(self._read_handle, 1, 0))  # Read end never inherited.
            size = c.c_size_t()
            self._api.InitializeProcThreadAttributeList(None, 2, 0, c.byref(size))
            if not size.value:
                raise c.WinError(c.get_last_error())
            buffer = c.create_string_buffer(size.value)
            _check(self._api.InitializeProcThreadAttributeList(buffer, 2, 0, c.byref(size)))
            attributes = c.cast(buffer, c.c_void_p)
            handles = (w.HANDLE * (2 if has_output else 1))(*([null, write_pipe] if has_output else [null]))
            jobs = (w.HANDLE * 1)(self._job)
            for attribute, values in ((0x20002, handles), (0x2000D, jobs)):
                _check(self._api.UpdateProcThreadAttribute(attributes, 0, attribute, c.byref(values),
                                                          c.sizeof(values), None, None))
            startup = _StartupEx()
            startup.startup.cb = c.sizeof(startup)
            startup.startup.flags = 0x101  # STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW (SW_HIDE).
            startup.startup.stdin = startup.startup.stdout = startup.startup.stderr = null
            if capture_output:
                startup.startup.stdout = startup.startup.stderr = write_pipe
            elif on_output is not None:
                startup.startup.stdout = write_pipe  # Binary transport never mixes in stderr.
            startup.attributes = attributes
            command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
            _check(self._api.CreateProcessW(str(executable), command, None, None, True,
                0x08000000 | 0x00080000 | 0x00000400, environment, str(working), c.byref(startup), c.byref(info)))
            self._process, self.pid = info.process, int(info.pid)
            if has_output:
                reader = threading.Thread(target=self._read_output, name="Saydraft-native-output", daemon=True)
                reader.start()
                self._reader = reader
                self._read_ready.set()  # Transfer read-handle ownership only after thread startup succeeds.
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
            if write_pipe:
                self._api.CloseHandle(write_pipe)

    def _read_output(self):
        self._read_ready.wait()
        if self._read_abort:
            self._output_done.set()
            return
        handle = self._read_handle
        try:
            buffer, count = c.create_string_buffer(4096), w.DWORD()
            while self._api.ReadFile(handle, buffer, len(buffer), c.byref(count), None):
                if not count.value:
                    break
                if self._on_output is not None:
                    # Consumers must be bounded and nonblocking, raising on
                    # backpressure. This adapter retains no recording buffer.
                    self._on_output(buffer.raw[:count.value])
                elif len(self._output) + count.value > self._output_limit:
                    self._output_error = "Native metadata output exceeded its bound"
                    self.terminate()
                    return
                else:
                    self._output.extend(buffer.raw[:count.value])
            else:
                if c.get_last_error() != 109:  # ERROR_BROKEN_PIPE is normal EOF.
                    self._output_error = "Native metadata pipe failed"
                    if self._on_output is not None:
                        self.terminate()
        except Exception:
            self._output_error = "Native output stream failed" if self._on_output is not None else "Native metadata capture failed"
            if self._on_output is not None:
                self.terminate()
        finally:
            self._api.CloseHandle(handle)
            self._read_handle = None
            self._output_done.set()

    def read_output(self, timeout=1):
        if not self._capture:
            raise RuntimeError("Native output capture is disabled")
        self.finish_output(timeout)
        return bytes(self._output)

    def finish_output(self, timeout=1):
        """Observe drained EOF, including consumer failure, outside the GUI thread."""
        if not self._capture and self._on_output is None:
            raise RuntimeError('Native output capture is disabled')
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Output wait must be finite and nonnegative")
        if not self._output_done.wait(timeout):
            raise TimeoutError("Native metadata output did not finish")
        if self._output_error:
            raise OSError(self._output_error)

    @property
    def output_finished(self):
        return self._output_done.is_set()

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

    def poll_tree(self):
        """Return the main exit code only after every owned descendant exits."""
        with self._lock:
            if self._job is None:
                raise RuntimeError('Process job handle is closed')
            info = _Accounting()
            _check(self._api.QueryInformationJobObject(self._job, 1, c.byref(info), c.sizeof(info), None))
            return self._wait(0) if info.active_processes == 0 else None

    def wait_tree(self, timeout=1):
        if not math.isfinite(timeout) or not 0 <= timeout < 0xFFFFFFFE / 1000:
            raise ValueError('Wait timeout must be finite and nonnegative')
        deadline = time.monotonic() + timeout
        while True:
            code = self.poll_tree()
            if code is not None:
                return code
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Owned process tree has not exited')
            time.sleep(min(.01, remaining))

    def wait(self, timeout=1):
        if not math.isfinite(timeout) or not 0 <= timeout < 0xFFFFFFFE / 1000:
            raise ValueError("Wait timeout must be finite and nonnegative")
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                code = self._wait(0)
            if code is not None:
                return code
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Local process did not exit before the deadline")
            time.sleep(min(.01, remaining))  # Let output-limit/close threads terminate the job.

    def terminate(self):
        with self._lock:
            if self._job is not None:
                _check(self._api.TerminateJobObject(self._job, 1))

    def close(self):
        with self._lock:
            owns_read_handle = not self._read_ready.is_set()
            if owns_read_handle:
                self._read_abort = True
                self._read_ready.set()
            if self._job is not None:
                _check(self._api.CloseHandle(self._job))
                self._job = None
            if self._process is not None:
                _check(self._api.CloseHandle(self._process))
                self._process = None
            if owns_read_handle and self._read_handle is not None:
                self._api.CloseHandle(self._read_handle)
                self._read_handle = None
        if self._reader is not None and self._reader is not threading.current_thread():
            self._reader.join(1)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass  # Kernel handle closure on owner exit remains the final safeguard.
