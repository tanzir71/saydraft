"""Explicit selected-text policy against synthetic ranges; no desktop access."""

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from saydraft.context.selection import SELECTION_LIMIT, SelectionSnapshot, SelectionTracker
from tests.test_focused_edit import Reader


class Range:
    def __init__(self, reader, start, end):
        self.reader, self.start, self.end = reader, start, end
        reader.range_count += 1
        self.serial = reader.range_count
        self.creator = threading.get_ident()

    def __del__(self):
        self.reader.released.append((self.serial, threading.get_ident()))
        if self.serial == 1:
            self.reader.anchor_released.set()


class SelectionReader(Reader):
    def __init__(self, text="Public selection"):
        self.document, self.start, self.end = text, 0, len(text)
        self.pid, self.runtime, self.password_value = 42, (1, 2, 3), False
        self.focused, self.read_only, self.supported = True, False, True
        self.reads, self.released, self.range_count = [], [], 0
        self.anchor_released = threading.Event()
        self.closed = []
        self.on_read = lambda: None

    def window_pid(self, window):
        assert window == 123
        return self.pid

    def runtime_id(self, element):
        return self.runtime

    def password(self, element):
        return self.password_value

    def same_focus(self, element):
        return self.focused

    def text_context(self, *args):
        pytest.fail("Selection capture must not read caret or document context")

    def selection_range(self, element, current):
        return Range(self, self.start, self.end) if self.supported and current() else None

    def selection_text(self, selected, limit, current):
        assert limit == SELECTION_LIMIT and threading.get_ident() == selected.creator
        self.reads.append((selected.start, selected.end, limit, threading.get_ident()))
        text = self.document[selected.start:selected.end][:limit + 1]
        self.on_read()
        return text

    def same_selection(self, left, right):
        return (left.start, left.end) == (right.start, right.end)

    def selection_read_only(self, element):
        return self.read_only

    def close(self):
        self.closed.append(threading.get_ident())


def test_only_selected_text_is_read_and_exact_range_is_rechecked():
    reader = SelectionReader("private prefix PUBLIC private suffix")
    reader.start, reader.end = 15, 21
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    assert snapshot.status == "ready" and snapshot.text == "PUBLIC"
    assert snapshot.identity.runtime_id == (1, 2, 3) and snapshot.read_only is False
    assert tracker.verify(snapshot) == "" and len(reader.reads) == 3
    assert all((start, end) == (15, 21) for start, end, *_ in reader.reads)
    tracker.clear()
    assert reader.anchor_released.is_set() and tracker.verify(snapshot) == "selection_expired"


def test_identical_text_at_another_position_cannot_authorize_replacement():
    reader = SelectionReader("same x same")
    reader.start, reader.end = 0, 4
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    reader.start, reader.end = 7, 11
    assert reader.document[reader.start:reader.end] == snapshot.text
    assert tracker.verify(snapshot) == "selection_changed" and tracker.expires_at is None


def test_same_range_with_changed_text_cannot_authorize_replacement():
    reader = SelectionReader("alpha")
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    reader.document = "omega"
    assert tracker.verify(snapshot) == "selection_changed"


@pytest.mark.parametrize("kind,units,status", [("ascii", 8192, "ready"), ("ascii", 8193, "selection_too_long"),
    ("emoji", 8192, "ready"), ("emoji", 8194, "selection_too_long"), ("invalid", 2, "field_unavailable"),
    ("cut-surrogate", 8193, "selection_too_long")])
def test_complete_utf16_selection_or_no_text_is_returned(kind, units, status):
    text = "x" * units if kind == "ascii" else "😀" * (units // 2) if kind == "emoji" else "A\ud83d"
    if kind == "cut-surrogate":
        text = "😀" * 4096 + "\ud83d"
    reader = SelectionReader(text)
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    assert snapshot.status == status
    assert snapshot.text == (text if status == "ready" else "")
    assert (tracker.expires_at is not None) == (status == "ready")
    tracker.clear()


@pytest.mark.parametrize("password", [True, None, 0, "false"])
def test_password_or_unknown_state_never_reads_selection(password):
    reader = SelectionReader()
    reader.password_value = password
    snapshot = SelectionTracker(reader).begin(123, 42)
    assert snapshot.status == ("password_field" if password is True else "unavailable")
    assert snapshot.text == "" and not reader.reads and not reader.range_count


@pytest.mark.parametrize("change,reason", [("password", "password_field"), ("focus", "focus_changed"),
    ("runtime", "focus_changed"), ("pid", "focus_changed"), ("text", "selection_changed"), ("range", "selection_changed")])
def test_changes_during_capture_discard_partial_text(change, reason):
    reader = SelectionReader("selection")
    def mutate():
        if change == "password":
            reader.password_value = True
        elif change == "focus":
            reader.focused = False
        elif change == "runtime":
            reader.runtime = (9,)
        elif change == "pid":
            reader.pid = 99
        elif change == "text":
            reader.document = "different"
        else:
            reader.start += 1
        reader.on_read = lambda: None
    reader.on_read = mutate
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    assert snapshot.status == reason and not snapshot.text and tracker.expires_at is None


def test_range_changed_during_the_second_read_is_checked_again_before_publication():
    reader = SelectionReader("selection")
    def mutate():
        if len(reader.reads) == 2:
            reader.start += 1
    reader.on_read = mutate
    tracker = SelectionTracker(reader)
    assert tracker.begin(123, 42).status == "selection_changed"
    assert tracker.expires_at is None


def test_read_only_selection_can_be_read_but_not_authorize_a_write():
    reader = SelectionReader()
    reader.read_only = True
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    assert snapshot.status == "ready" and snapshot.read_only is True
    assert tracker.verify(snapshot, for_write=False) == ""
    assert tracker.verify(snapshot) == "read_only" and tracker.expires_at is None


def test_read_only_lease_cannot_be_upgraded_or_forged_into_a_replacement():
    reader = SelectionReader()
    reader.read_only = True
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    reader.read_only = False
    assert tracker.verify(replace(snapshot, read_only=False)) == 'read_only'
    assert tracker.expires_at is None


@pytest.mark.parametrize("change,reason", [("password_value", "password_field"), ("focused", "focus_changed"),
    ("runtime", "focus_changed"), ("pid", "focus_changed"), ("read_only", "read_only")])
def test_fresh_field_identity_and_sensitive_state_are_required_before_a_write(change, reason):
    reader = SelectionReader()
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    setattr(reader, change, {"password_value": True, "focused": False, "runtime": (9,), "pid": 99, "read_only": True}[change])
    assert tracker.verify(snapshot) == reason and tracker.expires_at is None


def test_empty_unsupported_expired_and_forged_snapshots_never_authorize_a_write():
    reader = SelectionReader("")
    tracker = SelectionTracker(reader)
    assert tracker.begin(123, 42).status == "empty"
    reader.supported = False
    assert tracker.begin(123, 42).status == "unsupported"
    reader.supported, reader.document, reader.end = True, "Public", 6
    clock = [0]
    tracker.clock = lambda: clock[0]
    snapshot = tracker.begin(123, 42, lease_seconds=2)
    assert tracker.verify(replace(snapshot, text="different")) == "selection_expired"
    assert tracker.verify(snapshot) == ""  # A bad DTO does not invalidate the genuine lease.
    clock[0] = 2
    assert tracker.verify(snapshot) == "selection_expired" and tracker.expires_at is None


@pytest.mark.parametrize("window,pid,lease", [(0, 42, 1), (True, 42, 1), (123, 0, 1),
    (123, True, 1), (123, 42, 0), (123, 42, float("nan")), (123, 42, 3661)])
def test_invalid_request_never_reads_a_field(window, pid, lease):
    reader = SelectionReader()
    reader.focused_element = lambda: pytest.fail("Invalid selection request read a field")
    assert SelectionTracker(reader).begin(window, pid, lease_seconds=lease) == SelectionSnapshot()


def test_range_operations_refuse_a_different_thread_and_errors_never_log_text(caplog):
    reader = SelectionReader()
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    with ThreadPoolExecutor(max_workers=1) as other:
        with pytest.raises(RuntimeError, match="MTA owner"):
            other.submit(tracker.verify, snapshot).result()
    def failed(*args):
        raise OSError("Private provider details must not be logged")
    reader.selection_text = failed
    assert tracker.verify(snapshot) == "field_unavailable" and not caplog.records
