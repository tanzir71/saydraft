"""Prepare only a probe-owned provider; keep production UIA deadlines unchanged."""

import os
import time
import ctypes as ct
from ctypes import wintypes as wt


def message_waiter(user):
    """Wake the fixture's own window thread for UIA RPC instead of polling join.

    https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-msgwaitformultipleobjectsex
    Zero handles waits only on this thread's queue. INPUTAVAILABLE also wakes
    for messages already seen by PeekMessage, including sent UIA messages.
    """
    native = user.MsgWaitForMultipleObjectsEx
    native.argtypes = [wt.DWORD, ct.POINTER(wt.HANDLE), wt.DWORD, wt.DWORD, wt.DWORD]
    native.restype = wt.DWORD
    def wait():
        # QS_ALLINPUT on supported Windows 10/11; MWMO_INPUTAVAILABLE.
        if native(0, None, 5, 0x1CFF, 0x0004) == 0xFFFFFFFF:
            raise OSError('Owned fixture message wait failed')
    return wait


def prepare_owned_element(reader, handle, report, *, clock=time.monotonic):
    """Bound cold fixture startup separately from timed context/observation reads.

    UIA_E_TIMEOUT is documented at:
    https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-error-codes
    Native acquisition can also return HRESULT_FROM_WIN32(ERROR_TIMEOUT),
    observed as 0x800705b4 on a cold disposable CI provider:
    https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--1300-1699-
    Every failed acquisition remains visible in the fixture setup receipt.
    """
    if reader.window_pid(handle) != os.getpid():
        raise ValueError('UIA fixture preparation requires a window owned by this process')
    receipt = {'attempts': 0, 'timeouts': 0, 'ready': False}
    report.setdefault('provider_setup', []).append(receipt)
    started, last_error = clock(), None
    try:
        for _ in range(32):
            if clock() - started >= 2:
                break
            receipt['attempts'] += 1
            try:
                element = reader.client.ElementFromHandleBuildCache(handle, reader.cache)
            except Exception as error:
                hresult = getattr(error, 'hresult', None)
                if type(hresult) is not int or hresult & 0xFFFFFFFF not in (0x80131505, 0x800705B4):
                    raise
                receipt['timeouts'] += 1
                errors = receipt.setdefault('timeout_hresult_counts', {})
                key = f'{hresult & 0xFFFFFFFF:#010x}'
                errors[key] = errors.get(key, 0) + 1
                last_error = error
                continue
            if clock() - started >= 2:
                raise TimeoutError('Owned UIA fixture preparation exceeded its setup budget')
            if not element:
                raise ValueError('Owned UIA fixture returned no element')
            receipt['ready'] = True
            return element
        if last_error is not None:
            raise last_error
        raise TimeoutError('Owned UIA fixture was not ready within its setup budget')
    finally:
        receipt['seconds'] = clock() - started
