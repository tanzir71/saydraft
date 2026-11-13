"""Prepare only a probe-owned provider; keep production UIA deadlines unchanged."""

import os
import time


def prepare_owned_element(reader, handle, report, *, clock=time.monotonic):
    """Bound cold fixture startup separately from timed context/observation reads.

    UIA_E_TIMEOUT is documented at:
    https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-error-codes
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
                if type(hresult) is not int or hresult & 0xFFFFFFFF != 0x80131505:
                    raise
                receipt['timeouts'] += 1
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
