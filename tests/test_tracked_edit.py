from dataclasses import replace
from types import SimpleNamespace as NS
from concurrent.futures import ThreadPoolExecutor

import pytest

from saydraft.context.tracked_edit import FieldIdentity, ObservedEdit, TrackedEditReader
from saydraft.dictionary.alignment import suggest_correction

KEY = FieldIdentity(123, 456, (42, 7))
UNAVAILABLE = ObservedEdit("", "")


class Reader:
    def __init__(self):
        self.element = object()
        self.is_password, self.focus = False, True
        self.pid, self.runtime, self.window = KEY.process_id, KEY.runtime_id, KEY.window
        self.parts, self.text, self.reads = ("Before 🙂 ", "OLD", " after."), "", 0
        self.during_read = lambda: None

    def focused_element(self):
        return self.element

    def refresh_element(self, element, window, runtime_id, current):
        assert element is self.element and window == KEY.window and runtime_id == KEY.runtime_id
        return element if current() else None

    def window_pid(self, window):
        return self.pid

    def current_runtime_id(self, element):
        assert element is self.element
        return self.runtime

    runtime_id = current_runtime_id

    def belongs(self, element, window):
        assert element is self.element
        return self.window == window

    def fresh_password(self, element):
        assert element is self.element
        return self.is_password

    password = fresh_password

    def keyboard_focus(self, element):
        assert element is self.element
        return self.focus

    keyboard_focus_snapshot = keyboard_focus

    def insertion_edges(self, element, limit, current):
        assert element is self.element and current()
        self.reads += 1
        return None if self.parts is None else (self.parts[0], self.parts[2])

    def document_text(self, element, limit, current):
        assert element is self.element and current()
        self.reads += 1
        self.during_read()
        return self.text


def setup():
    reader, clock = Reader(), NS(now=0)
    observer = TrackedEditReader(reader, clock=lambda: clock.now)
    return reader, clock, observer


def inserted(reader, observer):
    ticket = observer.begin(KEY, "Kubernetis")
    assert ticket is not None
    reader.text = "Before 🙂 Kubernetis after."
    assert observer.confirm(ticket)
    def forbidden():
        pytest.fail("The newly focused field must never be queried")
    reader.focused_element = forbidden
    return ticket


@pytest.mark.parametrize("finish", ["focus_left", "timer"])
def test_read_only_original_field_after_verified_paste_and_single_edit(finish):
    reader, clock, observer = setup()
    ticket = inserted(reader, observer)
    reads = reader.reads
    assert observer.check(ticket) is None and reader.reads == reads
    reader.text = "Before 🙂 Kubernetes after."
    if finish == "focus_left":
        reader.focus = False
    else:
        clock.now = 15
    result = observer.check(ticket)
    assert result == ObservedEdit("Kubernetis", "Kubernetes")
    assert suggest_correction(result.original, result.current, "en").term == "Kubernetes"
    assert observer.expires_at is None and observer.check(ticket) == UNAVAILABLE
    assert reader.reads == reads + 1


@pytest.mark.parametrize("field,value", [("is_password", True), ("is_password", None),
    ("pid", 999), ("runtime", (42, 8)), ("window", 999), ("focus", None)])
def test_changed_sensitive_or_unknown_state_retires_before_content_read(field, value):
    reader, clock, observer = setup()
    ticket = inserted(reader, observer)
    reads = reader.reads
    setattr(reader, field, value)
    clock.now = 15
    assert observer.check(ticket) == UNAVAILABLE
    assert reader.reads == reads and observer.expires_at is None


@pytest.mark.parametrize("text", ["Changed 🙂 Kubernetes after.", "Before 🙂 Kubernetes changed.",
    "Before 🙂 Kubernetes after. extra", "Before 🙂 ", "Before 🙂 " + "x" * 4097 + " after.", "x" * 8193])
def test_edits_outside_insertion_or_limits_do_not_guess_a_span(text):
    reader, clock, observer = setup()
    ticket = inserted(reader, observer)
    reader.text, clock.now = text, 15
    assert observer.check(ticket) == UNAVAILABLE and observer.expires_at is None


@pytest.mark.parametrize("change", ["password", "runtime", "cancel", "unicode", "exception"])
def test_provider_change_or_failure_during_final_read_discards_partial_text(change):
    reader, clock, observer = setup()
    ticket = inserted(reader, observer)
    request = NS(current=True)
    def mutate():
        if change == "password":
            reader.is_password = True
        elif change == "runtime":
            reader.runtime = (99,)
        elif change == "cancel":
            request.current = False
        elif change == "unicode":
            reader.text = "\ud800"
        else:
            raise RuntimeError("sensitive provider error")
    reader.during_read, clock.now = mutate, 15
    assert observer.check(ticket, current=lambda: request.current) == UNAVAILABLE
    assert observer.expires_at is None


@pytest.mark.parametrize("key", [replace(KEY, window=True), replace(KEY, process_id=0),
    replace(KEY, runtime_id=()), replace(KEY, runtime_id=(True,)), replace(KEY, runtime_id=(2**31,))])
def test_invalid_identity_never_reads(key):
    reader, _, observer = setup()
    assert observer.begin(key, "Kubernetis") is None and reader.reads == 0


def test_password_unfocused_and_unverifiable_caret_never_arm():
    reader, _, observer = setup()
    reader.is_password = True
    assert observer.begin(KEY, "Kubernetis") is None and reader.reads == 0
    reader.is_password, reader.focus = False, False
    assert observer.begin(KEY, "Kubernetis") is None and reader.reads == 0
    reader.focus, reader.parts = True, None
    assert observer.begin(KEY, "Kubernetis") is None


def test_failed_delivery_stale_tickets_timeout_and_explicit_cancel_release_scope():
    reader, clock, observer = setup()
    old = observer.begin(KEY, "Kubernetis")
    assert not observer.confirm(old)  # No matching insertion actually appeared.
    ticket = inserted(reader, observer)
    observer.clear(old)
    assert observer.check(ticket) is None and not observer.confirm(old)
    clock.now = 16
    observer.expire()
    assert observer.expires_at is None and observer.check(ticket) == UNAVAILABLE
    reader.focused_element = lambda: reader.element
    ticket = observer.begin(KEY, "Kubernetis")
    observer.clear(ticket)
    assert observer.expires_at is None


def test_new_insertion_retires_old_scope_and_no_com_crosses_threads():
    reader, _, observer = setup()
    ticket = inserted(reader, observer)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(RuntimeError, match="MTA owner"):
            pool.submit(observer.clear).result()
    assert observer.check(ticket) is None
    assert observer.begin(KEY, "") is None and observer.expires_at is None
