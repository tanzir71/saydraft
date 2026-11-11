"""Deterministic dictation lifecycle; no audio, Qt, threads or OS calls.

Workers tag completions with ``session_id`` so a cancelled job cannot advance a
new recording. The controller consumes returned transition events to do I/O.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class SessionState(StrEnum):
    IDLE = "idle"
    ARMING = "arming"
    LISTENING = "listening"
    FINALIZING = "finalizing"
    CLEANING = "cleaning"
    INSERTING = "inserting"
    DONE = "done"
    NOT_INSERTED = "not_inserted"
    ERROR = "error"
    CANCELLED = "cancelled"


class SessionInput(StrEnum):
    START = "start"
    ARMED = "armed"
    RELEASE = "release"
    TRANSCRIBED = "transcribed"
    NO_SPEECH = "no_speech"
    CLEANED = "cleaned"
    INSERTED = "inserted"
    NOT_INSERTED = "not_inserted"
    FAIL = "fail"
    CANCEL = "cancel"
    RESET = "reset"


ACTIVE_STATES = frozenset({SessionState.ARMING, SessionState.LISTENING,
                           SessionState.FINALIZING, SessionState.CLEANING, SessionState.INSERTING})
TERMINAL_STATES = frozenset({SessionState.DONE, SessionState.NOT_INSERTED,
                             SessionState.ERROR, SessionState.CANCELLED})
_TRANSITIONS = {
    (SessionState.ARMING, SessionInput.ARMED): SessionState.LISTENING,
    (SessionState.FINALIZING, SessionInput.TRANSCRIBED): SessionState.CLEANING,
    (SessionState.FINALIZING, SessionInput.NO_SPEECH): SessionState.CANCELLED,
    (SessionState.CLEANING, SessionInput.CLEANED): SessionState.INSERTING,
    (SessionState.INSERTING, SessionInput.INSERTED): SessionState.DONE,
    (SessionState.INSERTING, SessionInput.NOT_INSERTED): SessionState.NOT_INSERTED,
}


@dataclass(frozen=True)
class SessionEvent:
    session_id: int
    previous: SessionState
    state: SessionState
    trigger: SessionInput
    timestamp: float
    elapsed_seconds: float
    recording_seconds: float | None
    reason: str


class DictationSession:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 minimum_recording_seconds: float = 0.5):
        if not math.isfinite(minimum_recording_seconds) or minimum_recording_seconds < 0:
            raise ValueError("minimum recording duration must be finite and nonnegative")
        self.clock = clock
        self.minimum_recording_seconds = float(minimum_recording_seconds)
        self.state = SessionState.IDLE
        self.session_id = 0
        self._started_at: float | None = None
        self._listening_at: float | None = None
        self._last_timestamp: float | None = None
        self._recording_seconds: float | None = None
        self._events: list[SessionEvent] = []

    @property
    def events(self) -> tuple[SessionEvent, ...]:
        return tuple(self._events)

    @property
    def active(self) -> bool:
        return self.state in ACTIVE_STATES

    def dispatch(self, trigger: SessionInput | str, *, session_id: int | None = None,
                 reason: str = "") -> SessionEvent | None:
        """Return one immutable event per transition; ignore bounce/stale events.

        The recording clock starts when capture is armed, not on key-down. Every
        release shorter than 0.5 s cancels; exactly 0.5 s is eligible for ASR.
        """
        trigger = SessionInput(trigger)
        if session_id is not None and session_id != self.session_id:
            return None
        destination = _TRANSITIONS.get((self.state, trigger))
        if trigger == SessionInput.START:
            if self.active:
                return None
            destination = SessionState.ARMING
        elif trigger == SessionInput.CANCEL and self.active:
            destination = SessionState.CANCELLED
            reason = reason or "cancelled"
        elif trigger == SessionInput.FAIL and self.active:
            destination = SessionState.ERROR
            reason = reason or "worker_error"
        elif trigger == SessionInput.RESET and self.state in TERMINAL_STATES:
            destination = SessionState.IDLE
        elif trigger == SessionInput.RELEASE:
            if self.state == SessionState.ARMING:
                destination = SessionState.CANCELLED
                reason = reason or "released_before_capture"
            elif self.state == SessionState.LISTENING:
                destination = SessionState.FINALIZING
        if destination is None:
            return None

        now = float(self.clock())
        if not math.isfinite(now):
            raise ValueError("clock must return a finite timestamp")
        if self._last_timestamp is not None and now < self._last_timestamp:
            raise ValueError("clock must be monotonic")
        if trigger == SessionInput.START:
            self.session_id += 1
            self._started_at = now
            self._listening_at = None
            self._recording_seconds = None
        if destination == SessionState.LISTENING:
            self._listening_at = now
        if self.state == SessionState.LISTENING:
            self._recording_seconds = now - self._listening_at
            if trigger == SessionInput.RELEASE and self._recording_seconds < self.minimum_recording_seconds:
                destination = SessionState.CANCELLED
                reason = reason or "too_short"
        if trigger == SessionInput.NO_SPEECH:
            reason = reason or "no_speech"
        event = SessionEvent(
            session_id=self.session_id, previous=self.state, state=destination,
            trigger=trigger, timestamp=now,
            elapsed_seconds=now - self._started_at if self._started_at is not None else 0.0,
            recording_seconds=self._recording_seconds, reason=reason,
        )
        self.state = destination
        self._last_timestamp = now
        self._events.append(event)
        if trigger == SessionInput.RESET:
            self._started_at = None
            self._listening_at = None
            self._recording_seconds = None
        return event
