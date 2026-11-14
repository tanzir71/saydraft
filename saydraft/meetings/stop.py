"""A per-capture manual-reset Windows event, with non-inherited handles."""

import ctypes as c
from ctypes import wintypes as w
import os
import threading
import uuid

_PREFIX = 'Local' + chr(92) + 'SaydraftMeetingStop-'


def valid_event_name(value):
    return (type(value) is str and value.startswith(_PREFIX) and len(value) == len(_PREFIX) + 32
            and all(char in '0123456789abcdef' for char in value[len(_PREFIX):]))


def _kernel():
    if os.name != 'nt':
        raise OSError('Meeting capture ownership requires Windows')
    api = c.WinDLL('kernel32', use_last_error=True, winmode=0x800)
    for name, result, args in (
        ('CreateEventW', w.HANDLE, [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]),
        ('OpenEventW', w.HANDLE, [w.DWORD, w.BOOL, w.LPCWSTR]),
        ('SetEvent', w.BOOL, [w.HANDLE]),
        ('WaitForSingleObject', w.DWORD, [w.HANDLE, w.DWORD]),
        ('CloseHandle', w.BOOL, [w.HANDLE]),
    ):
        function = getattr(api, name)
        function.restype, function.argtypes = result, args
    return api


def _check(value):
    if not value:
        raise c.WinError(c.get_last_error())
    return value


class StopEvent:
    def __init__(self, api, handle, name, *, owner):
        self._api, self._handle, self.name, self._owner = api, handle, name, owner
        self._lock = threading.RLock()

    @classmethod
    def create(cls, name=None):
        name = _PREFIX + uuid.uuid4().hex if name is None else name
        if not valid_event_name(name):
            raise ValueError('Invalid meeting stop event name')
        api = _kernel()
        c.set_last_error(0)
        handle = _check(api.CreateEventW(None, True, False, name))
        if c.get_last_error() == 183:  # Never adopt a colliding object's old state.
            api.CloseHandle(handle)
            raise FileExistsError('Meeting stop event already exists')
        return cls(api, handle, name, owner=True)

    @classmethod
    def open(cls, name):
        if not valid_event_name(name):
            raise ValueError('Invalid meeting stop event name')
        api = _kernel()
        handle = _check(api.OpenEventW(0x100000, False, name))  # SYNCHRONIZE only.
        return cls(api, handle, name, owner=False)

    def is_set(self):
        with self._lock:
            if self._handle is None:
                raise RuntimeError('Meeting stop event is closed')
            result = self._api.WaitForSingleObject(self._handle, 0)
            if result not in (0, 258):
                raise c.WinError(c.get_last_error())
            return result == 0

    def set(self):
        with self._lock:
            if self._handle is None:
                raise RuntimeError('Meeting stop event is closed')
            if not self._owner:
                raise PermissionError('Only the capture owner can request stop')
            _check(self._api.SetEvent(self._handle))

    def close(self):
        with self._lock:
            if self._handle is not None:
                _check(self._api.CloseHandle(self._handle))
                self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
