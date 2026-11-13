"""Shortcut learning uses synthetic identifiers and a fake native transport only."""

import itertools
import threading
import time
from types import SimpleNamespace

import pytest

from saydraft.core.shortcut_capture import ShortcutCapture
from saydraft.hotkeys.capture import ChordCapture, OwnedWindowGuard
from saydraft.hotkeys.chords import Transition
from saydraft.hotkeys.llhook import LowLevelHooks
from saydraft.hotkeys._win32_hooks import KeyboardPacket
from saydraft.input_origin import SAYDRAFT_INPUT_TAG
from tests.test_native_hooks import API


@pytest.mark.parametrize("press,release", list(itertools.product(
    itertools.permutations(("left_ctrl", "right_win")), repeat=2)))
def test_modifier_chord_is_suppressed_and_published_only_after_every_release(press, release):
    capture = ChordCapture(valid=lambda: True)
    capture.seed(())
    events, masks = [], []
    for key, down in [(key, True) for key in press] + [(key, False) for key in release]:
        decision = capture.feed(key, down)
        assert decision.suppress
        events.extend(decision.transitions)
        masks.append(decision.menu_mask)
        if capture._blocked:
            assert not events
    assert [(event.name, event.phase) for event in events] == [("ctrl+win", "captured")]
    assert sum(masks) == 1 and not capture._keys
    assert not capture.reset().menu_mask


def test_extended_chord_does_not_commit_its_modifier_prefix_and_ignores_repeat_and_own_input():
    capture = ChordCapture(valid=lambda: True)
    capture.seed(())
    for key in ("left_ctrl", "left_win", "f8", "f8"):
        assert not capture.feed(key, True).transitions
    assert not capture.feed("vk_e8", True, ignore=True).suppress
    assert not capture.feed("vk_e8", False, ignore=True).transitions
    events = []
    for key in ("left_win", "f8", "left_ctrl"):
        events.extend(capture.feed(key, False).transitions)
    assert [(event.name, event.phase) for event in events] == [("ctrl+win+f8", "captured")]


@pytest.mark.parametrize("key", ["f9", "xbutton1", "xbutton2", "a", "num3"])
def test_single_key_or_side_mouse_button_can_be_learned(key):
    capture = ChordCapture(valid=lambda: True)
    capture.seed(())
    assert capture.feed(key, True).suppress
    event, = capture.feed(key, False).transitions
    assert (event.name, event.phase) == (key, "captured")


def test_keys_held_before_arming_are_forwarded_until_all_are_released_including_click_buttons():
    capture = ChordCapture(valid=lambda: True)
    capture.seed(("left_ctrl", "left_mouse", "left_win"))
    for key in ("left_ctrl", "left_mouse", "left_win"):
        result = capture.feed(key, False)
        assert not result.suppress and not result.transitions
    capture.feed("f9", True)
    assert capture.feed("f9", False).transitions[0].name == "f9"


@pytest.mark.parametrize("reason", ["focus", "timeout", "escape", "click", "invalid"])
def test_cancellation_and_invalid_sequences_clear_candidates_and_balance_remaining_ups(reason):
    allowed, clock = [True], [0.0]
    capture = ChordCapture(valid=lambda: allowed[0], clock=lambda: clock[0])
    capture.seed(())
    capture.feed("left_win", True)
    if reason == "focus":
        allowed[0] = False
        result = capture.feed("a", True)
        assert not result.suppress
    elif reason == "timeout":
        clock[0] = 10
        result = capture.feed("a", True)
    elif reason == "escape":
        result = capture.feed("esc", True)
        assert result.suppress
    elif reason == "click":
        result = capture.feed("left_mouse", True)
        assert not result.suppress
    else:
        capture.feed("a", True)
        result = capture.feed("b", True)
    assert result.transitions[0].phase == {"timeout": "expired", "invalid": "invalid"}.get(reason, "cancelled")
    assert not capture._keys
    released = capture.feed("left_win", False)
    assert released.suppress and released.menu_mask and not released.transitions
    capture.reset()
    assert not capture._blocked


def test_temporary_capture_uses_real_off_thread_dispatch_and_mask_ownership_with_a_fake_api():
    api, events, done = API(), [], threading.Event()
    capture = ChordCapture(valid=lambda: True)
    owner = LowLevelHooks((), matcher=capture, api_factory=lambda: api,
        on_action=lambda event, when: (events.append((event, threading.get_ident())), done.set()))
    owner.start()
    try:
        for message, code in ((0x100, 0xA2), (0x100, 0x5B), (0x100, 0x77),
                              (0x101, 0x77), (0x101, 0xA2), (0x101, 0x5B)):
            assert api.emit("keyboard", message, KeyboardPacket(code)) == 1
        assert done.wait(1)
        assert events[0][0].name == "ctrl+win+f8" and events[0][1] != api.thread_id
        assert api.trace.count("mask") == 1
        assert api.emit("keyboard", 0x100, KeyboardPacket(0xE8, dwExtraInfo=SAYDRAFT_INPUT_TAG)) == 17
    finally:
        assert owner.close() and api.closed


class Timer:
    def __init__(self, seconds, action):
        self.seconds, self.action, self.cancelled = seconds, action, False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def service():
    owners, timers, events, retired = [], [], [], []

    class Owner:
        def __init__(self, _bindings, **kwargs):
            self.options = kwargs
            self.status = {"reason": None}
            self.completion_thread = None
            self.started = threading.Event()
            self.closed = False
            owners.append(self)

        def start(self):
            self.started.set()

        def close(self):
            self.closed = True
            return True

    def timer(seconds, action):
        value = Timer(seconds, action)
        timers.append(value)
        return value

    capture = ShortcutCapture(emit=lambda *args: events.append(args), hooks_factory=Owner,
        guard_factory=lambda window: lambda: window == 123,
        timer_factory=timer, finished=lambda: retired.append(True))
    try:
        yield SimpleNamespace(capture=capture, owners=owners, timers=timers, events=events, retired=retired, factory=Owner)
    finally:
        capture.close()


def wait_for(predicate):
    until = time.monotonic() + 3
    while time.monotonic() < until:
        if predicate():
            return
        threading.Event().wait(.002)
    raise AssertionError("Owned shortcut lease did not settle")


def test_capture_lifetime_publishes_only_after_observed_cleanup_and_rejects_overlap(service):
    s = service
    generation = s.capture.start(123, lambda: True)
    wait_for(lambda: bool(s.timers))
    assert generation == 1 and s.capture.active
    assert s.capture.start(123, lambda: True) == 0
    owner = s.owners[0]
    owner.options["on_action"](Transition("ctrl+win", "captured"), 0)
    wait_for(lambda: bool(s.retired))
    assert owner.closed and not s.capture.active and s.timers[0].cancelled
    assert s.events[-1] == ("shortcut_capture_status", 1, "captured", "ctrl+win")


def test_capture_expiry_and_stale_cancel_do_not_affect_a_successor(service):
    s = service
    first = s.capture.start(123, lambda: True)
    wait_for(lambda: len(s.timers) == 1)
    assert 0 < s.timers[0].seconds <= 10
    s.timers[0].action()
    wait_for(lambda: not s.capture.active)
    assert s.events[-1][2:] == ("expired", "")
    second = s.capture.start(123, lambda: True)
    wait_for(lambda: len(s.timers) == 2)
    assert second > first and not s.capture.cancel(first)
    assert s.capture.active
    s.capture.cancel(second)
    wait_for(lambda: not s.capture.active)


def test_capture_completion_during_startup_is_not_overwritten_by_a_late_capturing_status(service):
    s = service
    original = s.factory.start

    def start(owner):
        original(owner)
        owner.options["on_action"](Transition("f9", "captured"), 0)

    s.factory.start = start
    s.capture.start(123, lambda: True)
    wait_for(lambda: bool(s.retired))
    assert s.events[-1][2:] == ("captured", "f9")
    assert not any(event[2] == "capturing" for event in s.events)


def test_focus_revocation_during_native_teardown_cannot_publish_a_learned_chord(service):
    s = service
    entered, release, valid = threading.Event(), threading.Event(), threading.Event()
    valid.set()
    s.capture.start(123, valid.is_set)
    wait_for(lambda: bool(s.timers))
    owner = s.owners[0]

    def close():
        entered.set()
        assert release.wait(3)
        owner.closed = True
        return True

    owner.close = close
    try:
        owner.options["on_action"](Transition("f9", "captured"), 0)
        assert entered.wait(1)
        valid.clear()
        assert s.capture.cancel(1) and s.capture.active
        assert not s.retired
        release.set()
        wait_for(lambda: bool(s.retired))
        assert s.events[-1][2:] == ("cancelled", "")
    finally:
        release.set()


def test_start_failure_and_invalid_window_never_expose_backend_details(service):
    s = service
    assert s.capture.start(0, lambda: True) == 0

    def fail(_window):
        raise OSError("private fixture information")

    s.capture.guard_factory = fail
    s.capture.start(123, lambda: True)
    wait_for(lambda: bool(s.retired))
    assert s.events[-1][2:] == ("failed", "") and not s.owners
    assert "private" not in str(s.events)


def test_owned_window_guard_checks_pointer_width_foreground_and_owner_on_every_use():
    window, state = 2**40 + 5, {"foreground": 2**40 + 5, "pid": 123}

    class Function:
        def __init__(self, action):
            self.action = action

        def __call__(self, *args):
            return self.action(*args)

    def process(_window, output):
        output._obj.value = state["pid"]
        return 42

    user = SimpleNamespace(GetForegroundWindow=Function(lambda: state["foreground"]),
        GetWindowThreadProcessId=Function(process))
    guard = OwnedWindowGuard(window, user=user, process_id=123)
    assert guard()
    state["foreground"] = None
    assert not guard()
    state["foreground"], state["pid"] = window, 456
    assert not guard()
    with pytest.raises(OSError):
        OwnedWindowGuard(window, user=user, process_id=123)


@pytest.mark.parametrize("failure", ["no_observable_thread", "cleanup_exception"])
def test_unobserved_native_retirement_retains_admission_and_never_publishes_a_chord(service, failure):
    s = service
    s.capture.start(123, lambda: True)
    wait_for(lambda: bool(s.timers))

    def close():
        if failure == "cleanup_exception":
            raise OSError("private native details")
        return False

    s.owners[0].close = close
    s.owners[0].options["on_action"](Transition("f8", "captured"), 0)
    wait_for(lambda: s.events[-1][2] == "cleanup_failed")
    assert s.capture.active and not s.retired
    assert s.capture.start(123, lambda: True) == 0
    assert s.events[-1][3] == "" and "private" not in str(s.events)
    # This synthetic owner has no native thread; the test intentionally retains
    # its failed reservation, just as production must until exit is observable.


def test_controller_shortcut_bridge_rejects_missing_core_and_preserves_generation_and_guard():
    from saydraft.app import WorkerController

    controller = WorkerController(None)
    assert controller.start_shortcut_capture(123, lambda: True) == 0
    assert not controller.cancel_shortcut_capture(1)
    events, valid = [], lambda: True
    controller.core = SimpleNamespace(
        start_shortcut_capture=lambda window, guard: events.append((window, guard)) or 42,
        cancel_shortcut_capture=lambda generation: events.append(generation) or True)
    assert controller.start_shortcut_capture(123, valid) == 42
    assert controller.cancel_shortcut_capture(42) and events == [(123, valid), 42]
