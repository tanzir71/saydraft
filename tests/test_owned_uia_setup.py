"""Owned-provider setup reports timeout attempts without altering app deadlines."""

import os
from types import SimpleNamespace

import pytest

from tools.owned_uia import message_waiter, prepare_owned_element


class NativeFailure(Exception):
    def __init__(self, hresult):
        self.hresult = hresult


def fixture_reader(action, pid=None):
    return SimpleNamespace(window_pid=lambda window: os.getpid() if pid is None else pid,
        client=SimpleNamespace(ElementFromHandleBuildCache=action, ConnectionTimeout=100, TransactionTimeout=100), cache=object())


@pytest.mark.parametrize('hresult', [-2146233083, -2147023436, 0x80131505, 0x800705B4])
def test_cold_provider_timeouts_are_retained_as_setup_and_never_change_runtime_limits(hresult):
    ticks, attempts, result, report = [0.0], [], object(), {}
    def acquire(handle, cache):
        attempts.append(handle)
        ticks[0] += .1
        if len(attempts) < 3:
            raise NativeFailure(hresult)
        return result
    reader = fixture_reader(acquire)
    assert prepare_owned_element(reader, 17, report, clock=lambda: ticks[0]) is result
    assert report['provider_setup'][0] == {'attempts': 3, 'timeouts': 2, 'ready': True, 'seconds': ticks[0],
        'timeout_hresult_counts': {f'{hresult & 0xFFFFFFFF:#010x}': 2}}
    assert reader.client.ConnectionTimeout == reader.client.TransactionTimeout == 100


def test_setup_never_reads_a_window_owned_by_another_process():
    reader = fixture_reader(lambda *args: pytest.fail('Foreign window must not be acquired'), pid=os.getpid() + 1)
    with pytest.raises(ValueError, match='owned by this process'):
        prepare_owned_element(reader, 17, {})


def test_non_timeout_errors_are_not_retried_or_hidden():
    report = {}
    def unavailable(*args):
        raise NativeFailure(-2147220991)
    with pytest.raises(NativeFailure) as error:
        prepare_owned_element(fixture_reader(unavailable), 17, report)
    assert error.value.hresult == -2147220991
    assert report['provider_setup'][0]['attempts'] == 1
    assert not report['provider_setup'][0]['ready']


@pytest.mark.parametrize('hresult', [-2146233083, -2147023436])
def test_setup_stops_at_its_own_budget_and_preserves_last_native_error(hresult):
    report, ticks = {}, [0.0]
    def timeout(*args):
        ticks[0] += .5
        raise NativeFailure(hresult)
    with pytest.raises(NativeFailure) as error:
        prepare_owned_element(fixture_reader(timeout), 17, report, clock=lambda: ticks[0])
    assert error.value.hresult == hresult
    assert report['provider_setup'][0] == {'attempts': 4, 'timeouts': 4, 'ready': False, 'seconds': 2.0,
        'timeout_hresult_counts': {f'{hresult & 0xFFFFFFFF:#010x}': 4}}


def test_window_message_wait_wakes_for_sent_and_already_seen_messages_without_foreign_handles():
    calls = []
    class NativeWait:
        def __call__(self, *args):
            calls.append(args)
            return 0
    native = NativeWait()
    wait = message_waiter(SimpleNamespace(MsgWaitForMultipleObjectsEx=native))
    wait()
    count, handles, timeout, mask, flags = calls[0]
    assert count == 0 and handles is None and timeout == 5
    assert mask & 0x0040 and mask & 0x0008  # Sent UIA and posted fixture messages.
    assert flags & 0x0004  # Existing unread messages may still require dispatch.
    assert len(native.argtypes) == 5


def test_failed_window_message_wait_is_not_misreported_as_fixture_progress():
    class NativeWait:
        def __call__(self, *args):
            return 0xFFFFFFFF
    wait = message_waiter(SimpleNamespace(MsgWaitForMultipleObjectsEx=NativeWait()))
    with pytest.raises(OSError, match='message wait failed'):
        wait()
