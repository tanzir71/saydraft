"""Single-instance process guard for Saydraft."""

from __future__ import annotations

import json
import hashlib
import os
import time
from pathlib import Path
from typing import Any


LOCK_FILE_NAME = "saydraft.lock"
SECOND_LAUNCH_FILE_NAME = "second-launch.json"


def default_lock_path(local_appdata: str | os.PathLike[str] | None = None) -> Path:
    base = Path(local_appdata) if local_appdata is not None else _default_local_appdata()
    return base / "Saydraft" / LOCK_FILE_NAME


class SingleInstanceLock:
    """Atomic lockfile that prevents multiple tray instances."""

    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path) if path is not None else default_lock_path()
        self._acquired = False
        self._mutex = None

    @property
    def acquired(self) -> bool:
        return self._acquired

    def acquire(self) -> bool:
        if self._acquired:
            return True
        if os.name == "nt" and not self._acquire_mutex():
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._remove_if_stale():
                    continue
                self._release_mutex()
                return False

            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._lock_payload(), f)
                f.write("\n")
            self._acquired = True
            return True

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            if self._lock_pid() == os.getpid():
                self.path.unlink(missing_ok=True)
        finally:
            self._acquired = False
            self._release_mutex()

    def _acquire_mutex(self) -> bool:
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        name = "Local\\Tanzir.Saydraft." + hashlib.sha256(
            str(self.path.resolve()).casefold().encode("utf-8")
        ).hexdigest()
        handle = kernel.CreateMutexW(None, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._mutex = handle
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            self._release_mutex()
            return False
        return True

    def _release_mutex(self) -> None:
        if self._mutex is not None:
            import ctypes
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(self._mutex)
            self._mutex = None

    def notify_existing_instance(self, message: str) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        notification_path = self.path.parent / SECOND_LAUNCH_FILE_NAME
        payload = {
            "message": message,
            "pid": os.getpid(),
            "created_at": time.time(),
            "lock_path": str(self.path),
        }
        notification_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return notification_path

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.release()

    def _remove_if_stale(self) -> bool:
        pid = self._lock_pid()
        if pid is not None and _pid_is_running(pid):
            return False
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False

    def _lock_pid(self) -> int | None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        pid = raw.get("pid")
        return pid if isinstance(pid, int) else None

    @staticmethod
    def _lock_payload() -> dict[str, Any]:
        return {"pid": os.getpid(), "created_at": time.time()}


def consume_existing_instance_notification(
    lock_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    """Read and delete a pending second-launch notification request."""

    path = Path(lock_path) if lock_path is not None else default_lock_path()
    notification_path = path.parent / SECOND_LAUNCH_FILE_NAME
    try:
        raw = json.loads(notification_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        notification_path.unlink(missing_ok=True)
    except OSError:
        pass
    return raw if isinstance(raw, dict) else None


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not evidence of death.
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _default_local_appdata() -> Path:
    configured = os.environ.get("LOCALAPPDATA")
    if configured:
        return Path(configured)
    return Path.home() / "AppData" / "Local"
