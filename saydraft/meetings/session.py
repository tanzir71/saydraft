"""Continuously drain one explicitly admitted meeting capture on a worker.

Stop/cancel callers set Python events only. Native start, signal, EOF and Job
exit observation stay on this worker. An unconfirmed stop retains the capture
owner and keeps the session running; it never becomes a stopped result.
"""

from dataclasses import dataclass, replace
import math
import time

from .process import CaptureOutcome, CaptureProcess
from .request import CaptureRequest
from .timeline import MeetingAudio, MeetingAudioBuffer


@dataclass(frozen=True)
class CollectedMeeting:
    outcome: CaptureOutcome
    audio: MeetingAudio | None
    cancelled: bool
    pending_audio: MeetingAudioBuffer | None = None


class MeetingCaptureSession:
    def __init__(self, request, *, capture_factory=CaptureProcess, clock=time.monotonic,
                 wait=time.sleep, on_status=lambda phase: None, stop_grace=2., startup_seconds=15.):
        if (type(request) is not CaptureRequest or not callable(capture_factory)
                or not callable(clock) or not callable(wait) or not callable(on_status)
                or type(stop_grace) not in (int, float) or not math.isfinite(stop_grace) or not 0 < stop_grace <= 10
                or type(startup_seconds) not in (int, float) or not math.isfinite(startup_seconds)
                or not 0 < startup_seconds <= 60):
            raise ValueError('Invalid meeting capture session')
        self.request, self.capture_factory = request, capture_factory
        self.clock, self.wait, self.on_status = clock, wait, on_status
        self.stop_grace, self.startup_seconds = stop_grace, startup_seconds
        self.owner = None
        self.buffer = None
        self._used = False
        self._phase = None

    def _status(self, phase):
        if phase != self._phase:
            self._phase = phase
            try:
                self.on_status(phase)
            except Exception:
                pass  # A missing GUI receiver cannot release a native capture.

    def run(self, *, indicator_ready=False, stopping=lambda: False, cancelled=lambda: False):
        if self._used:
            raise RuntimeError('A meeting capture session can run only once')
        if indicator_ready is not True or self.request.consent is not True:
            raise PermissionError('Confirm consent and present the meeting indicator before capture')
        if not callable(stopping) or not callable(cancelled):
            raise ValueError('Invalid meeting stop control')
        self._used = True
        self.request.to_json()
        buffer = MeetingAudioBuffer(max_seconds=self.request.max_seconds)
        self.buffer = buffer
        discarded, failure, stop_at, ready = False, None, None, False
        started_at = self.clock()

        def intents():
            nonlocal discarded, failure
            try:
                discarded = discarded or bool(cancelled())
                return discarded or bool(stopping())
            except Exception:
                discarded, failure = True, 'control_failed'
                return True

        def drain():
            nonlocal ready, failure, discarded
            events = self.owner.take(limit=64)
            for event in events:
                # Continue draining transport after cancel, without retaining PCM.
                if discarded:
                    continue
                try:
                    buffer.consume(event)
                    if event.kind == 'ready':
                        ready = True
                        if stop_at is None:
                            self._status('recording')
                except Exception:
                    failure = failure or 'collection_failed'
            return len(events)

        self._status('preparing')
        if intents():
            buffer.discard()
            self.buffer = None
            self._status('stopped')
            return CollectedMeeting(CaptureOutcome(True, False, 'cancelled'), None, discarded)
        outcome = None
        try:
            self.owner = self.capture_factory(self.request)
            if intents():
                buffer.discard()
                self.buffer = None
                self.owner = None  # Constructor has not started native capture.
                self._status('stopped')
                return CollectedMeeting(CaptureOutcome(True, False, 'cancelled'), None, discarded)
            self.owner.start(indicator_ready=True)
        except Exception:
            failure = 'start_failed'
            if self.owner is None or not self.owner.active:
                outcome = CaptureOutcome(True, False, failure)
        while outcome is None or not outcome.stopped:
            requested = intents()
            if discarded:
                buffer.discard()
            try:
                drain()
            except Exception:
                failure = failure or 'transport_failed'
            try:
                observed = self.owner.poll()
                if observed is not None:
                    if type(observed) is not CaptureOutcome:
                        raise ValueError('Invalid meeting exit observation')
                    outcome = observed
            except Exception:
                failure = failure or 'exit_observation_failed'
            if outcome is not None and outcome.stopped:
                break
            now = self.clock()
            if not ready and now - started_at >= self.startup_seconds:
                failure = failure or 'startup_timeout'
            if now - started_at >= self.request.max_seconds + self.startup_seconds:
                failure = failure or 'capture_timeout'
            if stop_at is None and (requested or failure):
                stop_at = now
                self._status('stopping')
                try:
                    self.owner.request_stop()
                except Exception:
                    failure = failure or 'stop_signal_failed'
            if stop_at is not None and now - stop_at >= self.stop_grace:
                try:
                    observed = self.owner.stop(timeout=0)
                    if type(observed) is not CaptureOutcome:
                        raise ValueError('Invalid meeting stop observation')
                    outcome = observed
                except Exception:
                    failure = failure or 'stop_observation_failed'
                if outcome is not None and outcome.stopped:
                    break
                self._status('stop_unconfirmed')
                stop_at = self.clock()  # Bound retries while retaining the owner.
            self.wait(.02)

        # Full native tree exit and pipe EOF are confirmed. Drain the trailing
        # queue now that no producer can add another packet or final END.
        if self.owner is not None:
            try:
                while drain():
                    pass
            except Exception:
                failure = failure or 'transport_failed'
            self.owner = None
        intents()  # Cancel can arrive during the final exit/EOF observation.
        if failure:
            outcome = replace(outcome, complete=False, reason=failure)
        self._status('stopped')
        if discarded:
            buffer.discard()
            self.buffer = None
            return CollectedMeeting(outcome, None, True)
        try:
            audio = buffer.freeze(outcome)
        except Exception:
            # Keep the bounded slabs in memory for explicit worker-side retry or
            # discard. A failed final allocation must not silently lose PCM.
            self.buffer = None
            return CollectedMeeting(replace(outcome, complete=False, reason='collection_failed'), None, False, buffer)
        self.buffer = None
        return CollectedMeeting(outcome, audio, False)
