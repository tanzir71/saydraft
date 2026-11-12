"""No OS clipboard access: model ownership, partial failures and user-copy races."""

from contextlib import contextmanager
import os
from types import SimpleNamespace

import pytest

from saydraft.insert.clipboard_handles import MAX_SNAPSHOT_BYTES, ClipboardUnavailable, SnapshotTooLarge, StoredFormat
from saydraft.insert.clipboard_win import DeliveryBlocked, Snapshot, WindowsClipboard
from saydraft.insert._clipboard_win32 import NativeClipboardApi


class Api:
    privacy = (0xC100, 0xC101, 0xC102)

    def __init__(self):
        self.heap, self.clip, self.next_handle, self.serial, self.owner_id = {}, [], 100, 1, 5
        self.windows, self.open_window, self.events = set(), None, []
        self.busy = self.fail_duplicate = self.no_sequence = False
        self.fail_put, self.no_render, self.sizes = set(), set(), {}
        self.close_increment = 0
        for format, data in ((0xC001, b"rich"), (8, b"image"), (13, b"old text")):
            copy = self.memory(format, data)
            self.clip.append((format, copy.handle))
            copy.transfer()
        self.events.clear()

    @contextmanager
    def window(self):
        hwnd = self.next_handle
        self.next_handle += 1
        self.windows.add(hwnd)
        try:
            yield hwnd
        finally:
            self.windows.remove(hwnd)
            if self.owner_id == hwnd:
                self.owner_id = None

    @contextmanager
    def opened(self, hwnd):
        if self.busy:
            raise ClipboardUnavailable("busy")
        assert self.open_window is None
        self.open_window = hwnd
        before = self.serial
        try:
            yield
        finally:
            if self.serial != before:
                self.serial += self.close_increment
            self.open_window = None

    def formats(self):
        return [format for format, handle in self.clip]

    def get(self, format):
        return None if format in self.no_render else dict(self.clip)[format]

    def memory(self, format, data):
        handle, self.next_handle = self.next_handle, self.next_handle + 1
        self.heap[handle] = data
        self.events.append(("alloc", format))
        return StoredFormat(format, handle, len(data), self)

    def duplicate(self, format, handle, *, remaining):
        if self.fail_duplicate:
            raise ClipboardUnavailable("allocation")
        size = self.sizes.get(format, len(self.heap[handle]))
        if size > remaining:
            raise SnapshotTooLarge("limit")
        copy = self.memory(format, self.heap[handle])
        copy.size = size
        return copy

    def free(self, format, handle):
        assert handle in self.heap, "double free"
        del self.heap[handle]

    def empty(self):
        assert self.open_window is not None
        self.events.append(("empty",))
        for format, handle in self.clip:
            del self.heap[handle]
        self.clip.clear()
        self.serial += 1
        self.owner_id = self.open_window

    def put(self, copy):
        if copy.format in self.fail_put:
            raise ClipboardUnavailable("publication")
        self.events.append(("put", copy.format))
        self.clip.append((copy.format, copy.handle))
        self.serial += 1
        copy.transfer()

    def sequence(self):
        return 0 if self.no_sequence else self.serial

    def owner(self):
        return self.owner_id

    def data(self):
        return [(format, self.heap[handle]) for format, handle in self.clip]

    def assert_retired(self):
        assert not self.windows and self.open_window is None
        assert set(self.heap) == {handle for format, handle in self.clip}


def test_snapshot_preserves_all_rendered_formats_order_and_total_size():
    api = Api()
    snapshot = Snapshot.take(api)
    assert [copy.format for copy in snapshot.copies] == [0xC001, 8, 13]
    assert snapshot.size == len(b"richimageold text") and snapshot.skipped == 0
    staged = snapshot.stage(api)
    snapshot.close()
    assert [api.heap[copy.handle] for copy in staged] == [b"rich", b"image", b"old text"]
    for copy in staged:
        copy.close()
    api.assert_retired()


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("close_increment", [0, 3])
def test_transaction_sets_all_privacy_flags_before_unicode_and_restores_exact_original(empty, close_increment):
    api = Api()
    api.close_increment = close_increment
    if empty:
        with api.opened(999):
            api.empty()
        api.events.clear()
    original = api.data()
    clipboard = WindowsClipboard(api_factory=lambda: api)
    with clipboard.temporary_text("public dictation") as lease:
        assert lease.current()
        assert api.data() == [(format, bytes(4)) for format in api.privacy] + [
            (13, "public dictation\0".encode("utf-16-le"))]
        assert [event[1] for event in api.events if event[0] == "put"] == [*api.privacy, 13]
    assert lease.restore_status == "restored" and api.data() == original and clipboard.pending is None
    api.assert_retired()


@pytest.mark.parametrize("text", [None, "text\0truncation"])
def test_invalid_text_cannot_publish_a_silently_truncated_clipboard_value(text):
    api = Api()
    with pytest.raises(ValueError):
        with WindowsClipboard(api_factory=lambda: api).temporary_text(text):
            pytest.fail("invalid text yielded")
    assert not api.events
    api.assert_retired()


@pytest.mark.parametrize("reason", ["focus_changed", "target_elevated", "modifier_held"])
def test_publication_guard_refusal_changes_no_clipboard_data(reason):
    api = Api()
    clipboard = WindowsClipboard(api_factory=lambda: api)
    with pytest.raises(DeliveryBlocked) as error:
        with clipboard.temporary_text("fixture", guard=lambda: reason):
            pytest.fail("guarded transaction yielded")
    assert error.value.reason == reason and not any(event[0] == "empty" for event in api.events)
    api.assert_retired()


@pytest.mark.parametrize("failure", ["opaque", "oversize", "all_unrendered", "allocation"])
def test_uncapturable_clipboard_remains_intact_without_publishing_text(failure):
    api = Api()
    if failure == "opaque":
        api.clip[0] = (0x200, api.clip[0][1])
    elif failure == "oversize":
        api.sizes = {0xC001: MAX_SNAPSHOT_BYTES, 8: 1}
    elif failure == "all_unrendered":
        api.no_render = set(api.formats())
    else:
        api.fail_duplicate = True
    original = api.data()
    with pytest.raises(ClipboardUnavailable):
        with WindowsClipboard(api_factory=lambda: api).temporary_text("fixture"):
            pytest.fail("uncapturable clipboard yielded")
    assert api.data() == original and not any(event[0] == "empty" for event in api.events)
    api.assert_retired()


def test_one_failed_render_is_counted_and_other_formats_are_preserved():
    api = Api()
    api.no_render.add(0xC001)
    original = api.data()[1:]
    with WindowsClipboard(api_factory=lambda: api).temporary_text("fixture") as lease:
        assert lease.skipped == 1
    assert api.data() == original
    api.assert_retired()


@pytest.mark.parametrize("busy_restore", [False, True])
@pytest.mark.parametrize("close_increment", [0, 3])
def test_new_user_copy_wins_over_restoration_and_invalidates_lease(busy_restore, close_increment):
    api = Api()
    api.close_increment = close_increment
    clipboard = WindowsClipboard(api_factory=lambda: api)
    with clipboard.temporary_text("fixture") as lease:
        with api.opened(999):
            api.empty()
            api.put(api.memory(13, b"new user copy"))
        assert not lease.current()
        api.busy = busy_restore
    assert lease.restore_status == ("pending" if busy_restore else "replaced")
    api.busy = False
    assert clipboard.recover() and api.data() == [(13, b"new user copy")]
    api.assert_retired()


@pytest.mark.parametrize("failure", ["busy", "allocation", "partial_publication"])
@pytest.mark.parametrize("close_increment", [0, 3])
def test_failed_restore_retains_one_complete_original_and_recovery_restores_it(failure, close_increment):
    api = Api()
    api.close_increment = close_increment
    original = api.data()
    clipboard = WindowsClipboard(api_factory=lambda: api)
    with clipboard.temporary_text("fixture") as lease:
        if failure == "busy":
            api.busy = True
        elif failure == "allocation":
            api.fail_duplicate = True
        else:
            api.fail_put.add(13)
    assert lease.restore_status == "pending" and clipboard.pending is not None
    retained = clipboard.pending
    with pytest.raises(ClipboardUnavailable):
        with clipboard.temporary_text("next fixture"):
            pytest.fail("pending restoration was overwritten")
    assert clipboard.pending is retained
    api.busy = api.fail_duplicate = False
    api.fail_put.clear()
    assert clipboard.recover() and api.data() == original and clipboard.pending is None
    api.assert_retired()


def test_new_user_copy_supersedes_pending_recovery_without_overwriting_it():
    api = Api()
    clipboard = WindowsClipboard(api_factory=lambda: api)
    with clipboard.temporary_text("fixture"):
        api.busy = True
    api.busy = False
    with api.opened(999):
        api.empty()
        api.put(api.memory(13, b"new user copy"))
    assert clipboard.recover() and api.data() == [(13, b"new user copy")]
    api.assert_retired()


def test_body_failure_still_restores_and_partial_temp_publication_rolls_back():
    api = Api()
    original = api.data()
    clipboard = WindowsClipboard(api_factory=lambda: api)
    with pytest.raises(RuntimeError):
        with clipboard.temporary_text("fixture"):
            raise RuntimeError("paste failed")
    assert api.data() == original
    api.fail_put.add(api.privacy[1])
    with pytest.raises(ClipboardUnavailable):
        with clipboard.temporary_text("fixture"):
            pytest.fail("partial publication yielded")
    assert api.data() == original
    api.assert_retired()


def test_close_failure_after_successful_restore_does_not_retain_already_freed_snapshot():
    api = Api()
    original, opened = api.data(), api.opened
    @contextmanager
    def failing_close(hwnd):
        with opened(hwnd):
            yield
        if api.data() == original:
            raise ClipboardUnavailable("close failed")
    api.opened = failing_close
    clipboard = WindowsClipboard(api_factory=lambda: api)
    with clipboard.temporary_text("fixture") as lease:
        pass
    assert lease.restore_status == "cleanup_failed" and clipboard.pending is None
    assert api.data() == original
    api.assert_retired()


def test_unknown_sequence_keeps_original_in_memory_instead_of_claiming_replacement():
    api = Api()
    clipboard = WindowsClipboard(api_factory=lambda: api)
    with clipboard.temporary_text("fixture") as lease:
        api.no_sequence = True
    assert not lease.current() and lease.restore_status == "pending" and clipboard.pending is not None


def test_native_open_retry_is_bounded_and_close_runs_after_body_failure():
    api = NativeClipboardApi.__new__(NativeClipboardApi)
    state = SimpleNamespace(now=0, calls=0, closed=0)
    def open_clipboard(hwnd):
        state.calls += 1
        return False
    def close():
        state.closed += 1
        return True
    api.user = SimpleNamespace(OpenClipboard=open_clipboard, CloseClipboard=close)
    with pytest.raises(ClipboardUnavailable, match="busy"):
        with api.opened(123, clock=lambda: state.now, sleep=lambda delay: setattr(state, "now", state.now + delay)):
            pytest.fail("busy clipboard opened")
    assert state.calls <= 37 and state.closed == 0
    api.user.OpenClipboard = lambda hwnd: True
    with pytest.raises(RuntimeError):
        with api.opened(123):
            raise RuntimeError("body failed")
    assert state.closed == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows message-only clipboard owner ABI")
def test_native_owner_window_and_privacy_registration_retire_without_clipboard_access():
    import ctypes as ct
    from ctypes import wintypes as wt
    api = NativeClipboardApi()
    api.user.IsWindow.argtypes, api.user.IsWindow.restype = [wt.HWND], wt.BOOL
    assert len(set(api.privacy)) == 3 and all(0xC000 <= format <= 0xFFFF for format in api.privacy)
    with api.window() as hwnd:
        assert api.user.IsWindow(hwnd)
        assert ct.sizeof(wt.HWND) == ct.sizeof(ct.c_void_p)
    assert not api.user.IsWindow(hwnd)
