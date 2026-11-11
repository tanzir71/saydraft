import pytest

from saydraft.core.session import (
    ACTIVE_STATES, TERMINAL_STATES, DictationSession, SessionInput as Input, SessionState as State,
)


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


PATHS = {
    State.IDLE: [],
    State.ARMING: [Input.START],
    State.LISTENING: [Input.START, Input.ARMED],
    State.FINALIZING: [Input.START, Input.ARMED, Input.RELEASE],
    State.CLEANING: [Input.START, Input.ARMED, Input.RELEASE, Input.TRANSCRIBED],
    State.INSERTING: [Input.START, Input.ARMED, Input.RELEASE, Input.TRANSCRIBED, Input.CLEANED],
}
PATHS.update({state: [*PATHS[State.INSERTING], trigger] for state, trigger in (
    (State.DONE, Input.INSERTED), (State.NOT_INSERTED, Input.NOT_INSERTED),
    (State.ERROR, Input.FAIL), (State.CANCELLED, Input.CANCEL),
)})


def at_state(state):
    clock = Clock()
    session = DictationSession(clock=clock)
    for trigger in PATHS[state]:
        clock.now += 1
        session.dispatch(trigger)
    assert session.state == state
    return session, clock


@pytest.mark.parametrize("state", list(State))
def test_cancel_at_every_state(state):
    session, clock = at_state(state)
    previous_events = len(session.events)
    clock.now += 1
    event = session.dispatch(Input.CANCEL)
    if state in ACTIVE_STATES:
        assert event.previous == state
        assert event.state == State.CANCELLED
        assert event.reason == "cancelled"
        assert len(session.events) == previous_events + 1
    else:
        assert event is None
        assert session.state == state
        assert len(session.events) == previous_events


@pytest.mark.parametrize("state", list(State))
def test_hotkey_bounce_never_restarts_active_work(state):
    session, _clock = at_state(state)
    generation = session.session_id
    event = session.dispatch(Input.START)
    if state in ACTIVE_STATES:
        assert event is None
        assert session.session_id == generation
        assert session.state == state
    else:
        assert event.state == State.ARMING
        assert session.session_id == generation + 1


@pytest.mark.parametrize("state", list(State))
def test_failure_only_terminates_active_sessions(state):
    session, _clock = at_state(state)
    event = session.dispatch(Input.FAIL, reason="microphone unavailable")
    if state in ACTIVE_STATES:
        assert event.state == State.ERROR
        assert event.reason == "microphone unavailable"
    else:
        assert event is None


@pytest.mark.parametrize("state", list(State))
def test_reset_cannot_erase_inflight_work(state):
    session, _clock = at_state(state)
    event = session.dispatch(Input.RESET)
    if state in TERMINAL_STATES:
        assert event.state == State.IDLE
    else:
        assert event is None
        assert session.state == state


@pytest.mark.parametrize("duration,expected", [(0, State.CANCELLED), (0.499, State.CANCELLED),
                                              (0.5, State.FINALIZING), (1200, State.FINALIZING)])
def test_recording_threshold_counts_from_capture_start(duration, expected):
    clock = Clock()
    session = DictationSession(clock=clock)
    session.dispatch(Input.START)
    clock.now = 50  # Slow microphone arming must not count as captured speech.
    session.dispatch(Input.ARMED)
    clock.now += duration
    event = session.dispatch(Input.RELEASE)
    assert event.state == expected
    assert event.recording_seconds == pytest.approx(duration)
    if expected == State.CANCELLED:
        assert event.reason == "too_short"


def test_release_before_armed_does_not_start_transcription():
    session, _clock = at_state(State.ARMING)
    assert session.dispatch(Input.RELEASE).reason == "released_before_capture"
    assert session.dispatch(Input.ARMED) is None


def test_late_worker_result_cannot_advance_a_new_session():
    session, clock = at_state(State.CLEANING)
    old_id = session.session_id
    session.dispatch(Input.CANCEL)
    clock.now += 1
    session.dispatch(Input.START)
    for trigger in (Input.ARMED, Input.CLEANED, Input.FAIL, Input.CANCEL):
        assert session.dispatch(trigger, session_id=old_id) is None
    assert session.state == State.ARMING


def test_event_sequence_is_contiguous_and_contains_every_transition():
    session, clock = at_state(State.INSERTING)
    clock.now += 1
    session.dispatch(Input.NOT_INSERTED, reason="focus_changed")
    events = session.events
    assert [event.state for event in events] == [
        State.ARMING, State.LISTENING, State.FINALIZING, State.CLEANING, State.INSERTING, State.NOT_INSERTED,
    ]
    assert all(right.previous == left.state for left, right in zip(events, events[1:]))
    assert all(event.session_id == 1 for event in events)
    assert events[-1].reason == "focus_changed"
    assert events[-1].elapsed_seconds == 5
    assert events[-1].recording_seconds == 1


def test_empty_transcription_ends_without_insertion():
    session, _clock = at_state(State.FINALIZING)
    assert session.dispatch(Input.NO_SPEECH).reason == "no_speech"
    assert session.state == State.CANCELLED


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan")])
def test_invalid_minimum_duration_is_rejected(value):
    with pytest.raises(ValueError):
        DictationSession(minimum_recording_seconds=value)


def test_clock_regression_does_not_mutate_state():
    session, clock = at_state(State.ARMING)
    clock.now = 0
    with pytest.raises(ValueError, match="monotonic"):
        session.dispatch(Input.ARMED)
    assert session.state == State.ARMING


@pytest.mark.parametrize("trigger", [Input.TRANSCRIBED, Input.CLEANED, Input.INSERTED, Input.NOT_INSERTED])
def test_out_of_order_worker_events_are_ignored(trigger):
    session, _clock = at_state(State.LISTENING)
    assert session.dispatch(trigger) is None
    assert session.state == State.LISTENING
