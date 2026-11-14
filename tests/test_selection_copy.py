"""Memory clipboard only: explicit copy admission, complete restore and races."""

from contextlib import contextmanager
import threading

import pytest

from saydraft.insert.clipboard_handles import MAX_SNAPSHOT_BYTES
from saydraft.insert.clipboard_win import Snapshot, WindowsClipboard
from tests.test_clipboard_transactions import Api


class CopyApi(Api):
    def __init__(self):
        super().__init__()
        self.pids = {77: 700, 88: 800}
        self.reads = 0
        self.after_read = self.after_close = None

    def window_pid(self, hwnd):
        if hwnd not in self.pids:
            raise OSError('Unknown owner')
        return self.pids[hwnd]

    def get(self, format):
        return None if format in self.no_render else dict(self.clip).get(format)

    def unicode_text(self, handle, *, limit):
        assert limit == 8192
        self.reads += 1
        text = self.heap[handle].decode('utf-16-le').removesuffix('\0')
        if self.after_read:
            self.after_read()
        return text

    @contextmanager
    def opened(self, hwnd):
        with super().opened(hwnd):
            yield
        if self.after_close:
            self.after_close(hwnd)

    def copy(self, text='Selected public text', *, hwnd=77, format=13):
        with self.opened(hwnd or 77):
            self.empty()
            self.put(self.memory(format, (text + '\0').encode('utf-16-le')))
        if hwnd is None:
            self.owner_id = None


class Clock:
    def __init__(self):
        self.now, self.tick = 0, None

    def __call__(self):
        return self.now

    def sleep(self, delay):
        assert 0 <= delay <= .01
        self.now += delay
        if self.tick:
            self.tick()


def setup():
    api, clock = CopyApi(), Clock()
    return api, WindowsClipboard(api_factory=lambda: api), clock


def capture(clipboard, clock, send_copy, **options):
    return clipboard.capture_selection(process_id=700, guard=options.pop('guard', lambda: ''),
        send_copy=send_copy, clock=clock, sleep=clock.sleep, **options)


@pytest.mark.parametrize('empty', [False, True])
@pytest.mark.parametrize('text', ['Selected public text', 'line one\nline two', '\u09ac\u09be\u0982\u09b2\u09be \u0627\u0644\u0639\u0631\u0628\u064a\u0629 \U0001f600', 'x' * 8192],
                         ids=['plain', 'lines', 'unicode', 'limit'])
def test_one_copy_returns_complete_text_after_exact_all_format_restore(empty, text):
    api, clipboard, clock = setup()
    if empty:
        with api.opened(5):
            api.empty()
    before, calls = api.data(), []
    def copy():
        calls.append('ctrl+c')
        assert api.open_window is None  # Target can open the clipboard.
        api.copy(text)
    result = capture(clipboard, clock, copy)
    assert (result.reason, result.text, result.restore_status) == ('ok', text, 'restored')
    assert calls == ['ctrl+c'] and api.reads == 1 and api.data() == before
    assert clipboard.pending is None
    api.assert_retired()


@pytest.mark.parametrize('failure', ['partial_unrendered', 'opaque', 'oversize', 'allocation', 'busy', 'no_sequence'])
def test_incomplete_or_inaccessible_snapshot_never_sends_copy(failure):
    api, clipboard, clock = setup()
    if failure == 'partial_unrendered':
        api.no_render.add(8)
    elif failure == 'opaque':
        api.clip[0] = (0x200, api.clip[0][1])
    elif failure == 'oversize':
        api.sizes[8] = MAX_SNAPSHOT_BYTES
    elif failure == 'allocation':
        api.fail_duplicate = True
    elif failure == 'busy':
        api.busy = True
    else:
        api.no_sequence = True
    original = api.data()
    def forbidden():
        pytest.fail('Unsafe copy attempted')
    result = capture(clipboard, clock, forbidden)
    assert result.reason != 'ok' and not result.text and api.data() == original
    assert not any(e[0] == 'empty' for e in api.events)
    api.assert_retired()


@pytest.mark.parametrize('reason', ['modifier_held', 'password_field', 'focus_changed', 'target_elevated', 'cancelled'])
@pytest.mark.parametrize('phase', ['initial', 'after_snapshot'])
def test_guard_refusals_never_send_copy(reason, phase):
    api, clipboard, clock = setup()
    blocked = phase == 'initial'
    get = api.get
    def snapshot(format):
        nonlocal blocked
        blocked = True
        return get(format)
    api.get = snapshot
    result = capture(clipboard, clock, lambda: pytest.fail('Refused copy'),
                     guard=lambda: reason if blocked else '')
    assert result.reason == reason and not result.text and not api.reads
    assert not any(e[0] == 'empty' for e in api.events)
    api.assert_retired()


@pytest.mark.parametrize('guard', [lambda: None, lambda: True, lambda: 42])
def test_guard_requires_an_explicit_string_result(guard):
    api, clipboard, clock = setup()
    assert capture(clipboard, clock, lambda: pytest.fail('Invalid guard'), guard=guard).reason == 'field_unavailable'
    assert not api.events
    api.assert_retired()


def test_guard_exception_never_exposes_exception_or_clipboard_text():
    api, clipboard, clock = setup()
    def guard():
        raise RuntimeError('Private provider details')
    result = capture(clipboard, clock, lambda: pytest.fail('Invalid guard'), guard=guard)
    assert result.reason == 'field_unavailable' and not result.text
    api.assert_retired()


def test_unchanged_clipboard_is_never_returned_as_a_selection_even_if_target_already_owns_it():
    api, clipboard, clock = setup()
    api.owner_id = 77
    original, calls = api.data(), []
    result = capture(clipboard, clock, lambda: calls.append('ctrl+c'))
    assert result.reason == 'copy_timeout' and not result.text and clock.now == pytest.approx(.75)
    assert calls == ['ctrl+c'] and not api.reads and api.data() == original
    api.assert_retired()


@pytest.mark.parametrize('hwnd', [88, 99, None])
def test_foreign_or_unknown_clipboard_owner_is_preserved_without_reading(hwnd):
    api, clipboard, clock = setup()
    def copy():
        api.copy('New unrelated copy', hwnd=hwnd)
    result = capture(clipboard, clock, copy)
    assert result.reason == 'clipboard_changed' and not result.text and not api.reads
    assert api.data() == [(13, 'New unrelated copy\0'.encode('utf-16-le'))]
    assert clipboard.pending is None
    api.assert_retired()


@pytest.mark.parametrize('reason', ['cancelled', 'password_field', 'focus_changed', 'modifier_held'])
def test_refusal_after_input_restores_original_but_never_reads_the_new_text(reason):
    api, clipboard, clock = setup()
    original, copied = api.data(), False
    def copy():
        nonlocal copied
        api.copy()
        copied = True
    result = capture(clipboard, clock, copy, guard=lambda: reason if copied else '')
    assert result.reason == reason and not result.text and not api.reads
    assert result.restore_status == 'restored' and api.data() == original
    api.assert_retired()


def test_cancelled_wait_still_observes_already_sent_copy_to_restore_it():
    api, clipboard, clock = setup()
    original, active, copied, calls = api.data(), True, False, []
    def tick():
        nonlocal active, copied
        active = False
        if clock.now >= .03 and not copied:
            api.copy()
            copied = True
    clock.tick = tick
    result = capture(clipboard, clock, lambda: calls.append('ctrl+c'), current=lambda: active)
    assert copied and result.reason == 'cancelled' and result.restore_status == 'restored'
    assert calls == ['ctrl+c'] and not api.reads and api.data() == original
    api.assert_retired()


@pytest.mark.parametrize('copied', [False, True])
def test_failed_input_is_not_retried_and_any_observed_copy_is_restored(copied):
    api, clipboard, clock = setup()
    original, calls = api.data(), []
    def copy():
        calls.append('ctrl+c')
        if copied:
            api.copy()
        raise OSError('Partial input')
    result = capture(clipboard, clock, copy)
    assert result.reason == 'copy_failed' and not result.text and calls == ['ctrl+c']
    assert api.data() == original and not api.reads
    assert result.restore_status == ('restored' if copied else 'unchanged')
    api.assert_retired()


@pytest.mark.parametrize('text,expected', [('', 'empty'), ('x' * 8193, 'selection_too_long'),
    ('\U0001f600' * 4097, 'selection_too_long'), ('a\0b', 'selection_invalid'), ('\ud800', 'selection_unavailable')],
    ids=['empty', 'over-limit', 'utf16-over-limit', 'nul', 'surrogate'])
def test_invalid_or_incomplete_text_is_never_truncated_or_returned(text, expected):
    api, clipboard, clock = setup()
    original = api.data()
    if text == '\ud800':
        def read(handle, *, limit):
            return text
        api.unicode_text = read
        copied = 'fixture'
    else:
        copied = text
    result = capture(clipboard, clock, lambda: api.copy(copied))
    assert result.reason == expected and not result.text and result.restore_status == 'restored'
    assert api.data() == original
    api.assert_retired()


def test_missing_unicode_copy_does_not_fall_back_to_stale_original_text():
    api, clipboard, clock = setup()
    original = api.data()
    result = capture(clipboard, clock, lambda: api.copy('RTF only', format=0xC001))
    assert result.reason == 'selection_unavailable' and not result.text
    assert api.data() == original and result.restore_status == 'restored'
    api.assert_retired()


@pytest.mark.parametrize('failure', ['get', 'read'])
def test_native_read_failure_still_restores_all_original_formats(failure):
    api, clipboard, clock = setup()
    original = api.data()
    def failed(*args, **kwargs):
        raise OSError('Read failed')
    def copy():
        api.copy()
        if failure == 'get':
            api.get = failed
        else:
            api.unicode_text = failed
    result = capture(clipboard, clock, copy)
    assert result.reason == 'selection_unavailable' and result.restore_status == 'restored'
    assert not result.text and api.data() == original
    api.assert_retired()


def test_delayed_render_sequence_change_is_adopted_only_inside_open_clipboard():
    api, clipboard, clock = setup()
    original = api.data()
    def rendered():
        assert api.open_window is not None
        api.serial += 1
    api.after_read = rendered
    result = capture(clipboard, clock, api.copy)
    assert result.reason == 'ok' and api.data() == original
    api.assert_retired()


def test_rendering_that_changes_sequence_then_fails_still_restores_original():
    api, clipboard, clock = setup()
    original = api.data()
    def failed(handle, *, limit):
        assert api.open_window is not None
        api.serial += 1
        raise OSError('Delayed rendering failed after an update')
    api.unicode_text = failed
    result = capture(clipboard, clock, api.copy)
    assert result.reason == 'selection_unavailable' and result.restore_status == 'restored'
    assert not result.text and api.data() == original
    api.assert_retired()


@pytest.mark.parametrize('hwnd', [77, 88])
def test_new_copy_before_restore_is_preserved_even_from_the_same_process(hwnd):
    api, clipboard, clock = setup()
    read, raced = False, False
    def after_read():
        nonlocal read
        read = True
    def guard():
        nonlocal raced
        if read and api.open_window is None and not raced:
            raced = True
            api.copy('New user copy', hwnd=hwnd)
        return ''
    api.after_read = after_read
    result = capture(clipboard, clock, api.copy, guard=guard)
    assert raced and result.reason == 'clipboard_changed' and not result.text
    assert result.restore_status == 'replaced' and api.data() == [(13, 'New user copy\0'.encode('utf-16-le'))]
    assert clipboard.pending is None
    api.assert_retired()


@pytest.mark.parametrize('failure', ['busy', 'allocation', 'partial_restore'])
def test_failed_restore_retains_complete_original_for_shared_recovery(failure):
    api, clipboard, clock = setup()
    original = api.data()
    def fail():
        if failure == 'busy':
            api.busy = True
        elif failure == 'allocation':
            api.fail_duplicate = True
        else:
            api.fail_put.add(8)
    api.after_read = fail
    result = capture(clipboard, clock, api.copy)
    assert result.reason == 'clipboard_restore_pending' and not result.text
    assert result.restore_status == 'pending' and clipboard.pending is not None
    api.busy = api.fail_duplicate = False
    api.fail_put.clear()
    assert clipboard.recover() and clipboard.pending is None and api.data() == original
    api.assert_retired()


def test_a_copy_racing_busy_recovery_supersedes_the_original_without_overwrite():
    api, clipboard, clock = setup()
    api.after_read = lambda: setattr(api, 'busy', True)
    result = capture(clipboard, clock, api.copy)
    assert result.restore_status == 'pending'
    api.busy = False
    api.copy('Fresh user text', hwnd=88)
    assert clipboard.recover() and clipboard.pending is None
    assert api.data() == [(13, 'Fresh user text\0'.encode('utf-16-le'))]
    api.assert_retired()


def test_copy_observed_while_clipboard_is_busy_keeps_original_even_without_reading():
    api, clipboard, clock = setup()
    original = api.data()
    def copy():
        api.copy()
        api.busy = True
    result = capture(clipboard, clock, copy)
    assert result.reason == 'clipboard_restore_pending' and result.restore_status == 'pending'
    assert not result.text and not api.reads and clipboard.pending is not None
    api.busy = False
    assert clipboard.recover() and api.data() == original and clipboard.pending is None
    api.assert_retired()


def test_existing_pending_restore_is_never_implicitly_retired_or_recovered_by_a_copy_request():
    api, clipboard, clock = setup()
    pending = clipboard.pending = Snapshot.take(api)
    clipboard.pending_sequence = api.sequence()
    original = api.data()
    result = capture(clipboard, clock, lambda: pytest.fail('Pending restore'))
    assert result.reason == 'clipboard_restore_pending' and clipboard.pending is pending
    assert api.data() == original and not api.reads
    assert clipboard.recover()
    api.assert_retired()


def test_snapshot_close_race_refuses_input_and_preserves_the_fresh_copy():
    api, clipboard, clock = setup()
    once = False
    def close(hwnd):
        nonlocal once
        if not once:
            once = True
            api.copy('Racing snapshot copy', hwnd=88)
    api.after_close = close
    result = capture(clipboard, clock, lambda: pytest.fail('Snapshot race'))
    assert result.reason == 'clipboard_changed' and not result.text
    assert api.data() == [(13, 'Racing snapshot copy\0'.encode('utf-16-le'))]
    api.assert_retired()


def test_other_clipboard_owner_refuses_immediately_without_waiting_or_input():
    api, clipboard, clock = setup()
    held, release = threading.Event(), threading.Event()
    def transaction():
        with clipboard._lock:
            held.set()
            assert release.wait(3)
    thread = threading.Thread(target=transaction)
    thread.start()
    try:
        assert held.wait(1)
        result = capture(clipboard, clock, lambda: pytest.fail('Busy owner'))
        assert result.reason == 'clipboard_unavailable' and not api.events
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive()
    api.assert_retired()


@pytest.mark.parametrize('field,value', [('process_id', True), ('process_id', 0), ('process_id', -1),
    ('process_id', 2**32), ('timeout', True), ('timeout', float('nan')), ('timeout', float('inf')),
    ('timeout', .01), ('timeout', 3), ('guard', None), ('send_copy', None), ('current', None)])
def test_invalid_requests_fail_before_accessing_clipboard(field, value):
    calls = []
    clipboard = WindowsClipboard(api_factory=lambda: calls.append('opened'))
    request = dict(process_id=700, guard=lambda: '', send_copy=lambda: pytest.fail('Invalid input'))
    request[field] = value
    with pytest.raises(ValueError):
        clipboard.capture_selection(**request)
    assert not calls
