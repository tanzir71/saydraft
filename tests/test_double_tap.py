"""Bounded gesture decisions and generation-safe deferred release; no OS input."""

import threading

import pytest

from saydraft.core.session import DictationSession, SessionInput as Input, SessionState as State
from saydraft.hotkeys import HotkeyConfig, HotkeyController
from tests.test_hotkeys import FakeClock, FakeKeyboard
from tests.test_session_worker import Timer, make_worker


def rig(*, timer_factory=None, interval=300):
    clock, keyboard, timers, starts, stops, cancels = FakeClock(), FakeKeyboard(), [], [], [], []
    def factory(seconds, callback):
        timer = (timer_factory or Timer)(seconds, callback)
        timers.append(timer)
        return timer
    controller = HotkeyController(HotkeyConfig(record_hotkey="f9", alternate_record_hotkey="f8", tap_lock_ms=interval),
        on_record_start=lambda: starts.append(True), on_record_stop=stops.append,
        on_record_cancel=lambda: cancels.append(True), clock=clock.now, timer_factory=factory)
    controller.start(keyboard)
    def edge(key, down, when):
        clock.value = when
        (keyboard.press if down else keyboard.release)(key)
    return controller, edge, clock, timers, starts, stops, cancels


def test_explicit_zero_interval_disables_double_tap_without_delaying_ptt_release():
    controller, edge, _, timers, _, stops, _ = rig(interval=0)
    edge("f9", True, 0)
    edge("f9", False, .1)
    assert not timers and len(stops) == 1 and stops[0].stopped_at == .1 and not controller.is_recording
    controller.stop()


def test_single_tap_expires_once_at_its_physical_release_time():
    controller, edge, clock, timers, starts, stops, _ = rig()
    edge("f9", True, 0)
    edge("f9", False, .1)
    assert not controller.is_locked and not stops and timers[0].seconds == pytest.approx(.3)
    clock.value = .4
    timers[0].callback()
    timers[0].callback()
    assert starts == [True] and len(stops) == 1 and stops[0].stopped_at == .1
    assert not stops[0].locked and not controller.is_recording and controller.stop()


@pytest.mark.parametrize("gap", [.05, .29, .3])
def test_second_short_tap_locks_same_capture_and_stale_expiry_cannot_unlock(gap):
    controller, edge, _, timers, starts, stops, _ = rig()
    edge("f9", True, 0)
    edge("f9", False, .1)
    edge("f9", True, .1 + gap)
    timers[0].callback()
    edge("f9", False, .2 + gap)
    timers[0].callback()
    assert controller.is_locked and starts == [True] and not stops and timers[0].cancelled
    edge("f9", True, 2)
    edge("f9", False, 2.1)
    assert len(stops) == 1 and stops[0].locked and controller.stop()


@pytest.mark.parametrize("key,duration", [("f8", .1), ("f9", .5)])
def test_different_shortcut_or_second_hold_does_not_become_a_double_tap(key, duration):
    controller, edge, clock, timers, _, stops, _ = rig()
    edge("f9", True, 0)
    edge("f9", False, .1)
    edge(key, True, .2)
    edge(key, False, .2 + duration)
    assert not controller.is_locked
    clock.value = 1
    for timer in timers:
        timer.callback()
    assert len(stops) == 1 and not stops[0].locked and controller.stop()


def test_starved_expiry_cannot_turn_a_late_press_into_a_double_tap():
    controller, edge, _, timers, starts, stops, _ = rig()
    edge("f9", True, 0)
    edge("f9", False, .1)
    edge("f9", True, .41)
    timers[0].callback()
    edge("f9", False, 1)
    assert starts == [True, True] and [row.stopped_at for row in stops] == [.1, 1]
    assert all(not row.locked for row in stops) and controller.stop()


@pytest.mark.parametrize("action", ["cancel", "discard", "disable", "toggle", "force"])
def test_cancel_disable_or_mode_change_retires_a_pending_decision(action):
    controller, edge, _, timers, _, stops, cancels = rig()
    edge("f9", True, 0)
    edge("f9", False, .1)
    if action == "cancel":
        edge("esc", True, .2)
    elif action == "discard":
        controller.discard_active_recording()
    elif action == "disable":
        controller.stop()
    elif action == "toggle":
        controller._on_hands_free_press(.2)
    else:
        controller.force_stop()
    count = len(stops)
    timers[0].callback()
    assert timers[0].cancelled and len(stops) == count
    assert bool(cancels) == (action == "cancel")
    assert controller.is_locked == (action == "toggle")
    controller.stop()


@pytest.mark.parametrize("fail_at", ["construct", "start"])
def test_scheduler_failure_stops_at_release_instead_of_leaving_the_microphone_open(fail_at):
    class Broken(Timer):
        def __init__(self, *args):
            if fail_at == "construct":
                raise RuntimeError("scheduler unavailable")
            super().__init__(*args)
        def start(self):
            raise RuntimeError("thread unavailable")
    controller, edge, _, _, _, stops, _ = rig(timer_factory=Broken)
    edge("f9", True, 0)
    edge("f9", False, .1)
    assert len(stops) == 1 and stops[0].stopped_at == .1 and not controller.is_recording
    controller.stop()


@pytest.mark.parametrize("arm_when", ["before_release", "after_release", "after_expiry"])
def test_single_tap_during_microphone_arming_never_reaches_asr_even_if_expiry_is_late(arm_when):
    worker, clock, executor, events, _, _ = make_worker(queued=True)
    worker.services.asr.transcribe = lambda audio: pytest.fail("Short tap reached ASR")
    controller = worker.hotkeys._controller
    controller.clock = lambda: clock.now
    worker.hotkeys.start()
    controller._on_record_press("f9", 0)
    if arm_when == "before_release":
        executor.drain()
    clock.now = .1
    controller._on_record_release("f9", .1)
    timer = controller._tap[3]
    clock.now = .4
    if arm_when == "after_release":
        executor.drain()
    clock.now = .8
    timer.callback()
    executor.drain()
    assert not events and worker.session.state == State.CANCELLED
    assert worker.services.recorder.started == int(arm_when != "after_expiry")
    worker.shutdown()


def test_double_tap_while_arming_keeps_one_capture_then_persists_before_delivery():
    worker, clock, executor, events, _, _ = make_worker(queued=True)
    controller = worker.hotkeys._controller
    controller.clock = lambda: clock.now
    worker.hotkeys.start()
    controller._on_record_press("f9", 0)
    controller._on_record_release("f9", .1)
    timer = controller._tap[3]
    controller._on_record_press("f9", .2)
    controller._on_record_release("f9", .25)
    timer.callback()
    assert controller.is_locked and not events and worker.services.recorder.started == 0
    clock.now = .5
    executor.drain()
    assert worker.services.recorder.started == 1
    controller._on_record_press("f9", 1)
    clock.now = 1.6
    controller._on_record_release("f9", 1.6)
    executor.drain()
    assert [event[0] for event in events] == ["history", "insert"]
    assert events[0][1].duration_seconds == pytest.approx(1.1)
    assert worker.services.recorder.stopped == 1
    worker.shutdown()


@pytest.mark.parametrize("during_capture", [False, True])
def test_a_stop_already_outside_the_gesture_lock_cannot_stop_or_abort_a_later_session(during_capture):
    worker, clock, _, events, _, _ = make_worker()
    controller, pending = worker.hotkeys._controller, []
    controller.clock = lambda: clock.now
    original_stop = worker.hotkeys.stop_session
    worker.hotkeys.stop_session = pending.append
    worker.hotkeys.start()
    controller._on_record_press("f9", 0)
    controller._on_record_release("f9", .1)
    controller._tap[3].callback()
    assert len(pending) == 1 and pending[0].session_id == worker.session.session_id
    worker.cancel()
    clock.now = 2
    if during_capture:
        entered, release, result = threading.Event(), threading.Event(), []
        original_capture = worker.services.context.capture
        def capture():
            entered.set()
            assert release.wait(2)
            return original_capture()
        worker.services.context.capture = capture
        thread = threading.Thread(target=lambda: result.append(worker.start_recording()))
        thread.start()
        try:
            assert entered.wait(2)
            original_stop(pending[0])
        finally:
            release.set()
            thread.join(2)
        assert result == [True] and not thread.is_alive()
    else:
        assert worker.start_recording()
        original_stop(pending[0])
    assert worker.session.state == State.LISTENING and worker.services.recorder.stopped == 1 and not events
    worker.cancel()
    worker.shutdown()


@pytest.mark.parametrize("released,duration", [(.499, .499), (6, 5), (-1, 0)])
def test_fsm_uses_physical_release_without_rewinding_transition_timestamps(released, duration):
    clock = FakeClock()
    session = DictationSession(clock=clock.now)
    session.dispatch(Input.START)
    session.dispatch(Input.ARMED)
    clock.value = 5
    result = session.dispatch(Input.RELEASE, recording_stopped_at=released)
    assert result.timestamp == 5 and result.recording_seconds == pytest.approx(duration)
    assert (result.state == State.CANCELLED) == (duration < .5)


def test_native_expiry_waits_behind_second_tap_already_captured_during_a_slow_start():
    from saydraft.hotkeys._win32_hooks import KeyboardPacket
    from saydraft.hotkeys.llhook import LowLevelHooks
    from tests.test_native_hooks import API

    api, clock = API(), FakeClock()
    entered, release, drained = threading.Event(), threading.Event(), threading.Event()
    starts, stops, owners = [], [], []
    def start():
        starts.append(True)
        entered.set()
        assert release.wait(2)
    class Immediate(Timer):
        def start(self):
            self.started = True
            self.callback()  # Zero remaining time must enqueue, never overtake captured keys.
    def factory(bindings, **kwargs):
        owner = LowLevelHooks(bindings, **kwargs, api_factory=lambda: api, clock=clock.now)
        owners.append(owner)
        return owner
    controller = HotkeyController(HotkeyConfig(record_hotkey="f9", alternate_record_hotkey=None),
        on_record_start=start, on_record_stop=stops.append, clock=clock.now,
        timer_factory=Immediate, native_factory=factory)
    controller.start()
    try:
        api.emit("keyboard", 0x100, KeyboardPacket(0x78))
        assert entered.wait(2)
        for when, message in ((.1, 0x101), (.2, 0x100), (.25, 0x101)):
            clock.value = when
            api.emit("keyboard", message, KeyboardPacket(0x78))
        clock.value = 10  # Context preparation outlasted the entire physical double tap.
        release.set()
        assert owners[0].post_action(lambda: owners[0].post_action(drained.set))
        assert drained.wait(2)
        assert controller.is_locked and starts == [True] and not stops
    finally:
        release.set()
        assert controller.stop()
    assert not owners[0].post_action(lambda: pytest.fail("Retired dispatcher ran work"))


def test_release_returns_to_dispatcher_while_settings_holds_the_session_mutex():
    worker, clock, executor, events, _, _ = make_worker(queued=True)
    assert worker.start_recording()
    executor.drain()
    clock.now = 1
    finished = threading.Event()
    with worker._lock:
        thread = threading.Thread(target=lambda: (worker.stop_recording(released_at=1), finished.set()))
        thread.start()
        assert finished.wait(1)
    thread.join(1)
    assert not thread.is_alive() and worker.session.state == State.LISTENING
    executor.drain()
    assert [event[0] for event in events] == ["history", "insert"]
    assert worker.services.recorder.stopped == 1
    worker.shutdown()
