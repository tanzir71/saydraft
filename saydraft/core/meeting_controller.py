"""One consented meeting lease, acknowledged indicator and independent Notes.

The GUI only sets events. Native capture and model/storage work remain on the
serial session worker. A positive capture-stop observation is required before
the indicator can leave recording/stopping or the app reservation can retire.
"""

import copy
from dataclasses import dataclass, field, replace
import math
import threading

from saydraft.meetings.notes import MeetingNoteDraft
from saydraft.meetings.process import CaptureOutcome
from saydraft.meetings.processor import MeetingPreparationError, prepare_meeting
from saydraft.meetings.request import CaptureRequest
from saydraft.meetings.session import CollectedMeeting, MeetingCaptureSession


@dataclass(frozen=True)
class MeetingStatus:
    ticket: object
    phase: str
    capture_stopped: bool
    reason: str = ''
    progress: int | None = None
    note_id: str | None = None
    retained: str | None = None


@dataclass
class _Meeting:
    services: object
    config: dict
    request: CaptureRequest
    ticket: object = field(default_factory=object)
    indicator: threading.Event = field(default_factory=threading.Event)
    stop: threading.Event = field(default_factory=threading.Event)
    cancelled: threading.Event = field(default_factory=threading.Event)
    capture_stopped: bool = False
    captured: bool = False
    capture: object = None
    processor: object = None
    collected: object = None
    transcript: object = None
    draft: object = None
    store: object = None
    summary_reason: str = ''


class MeetingController:
    def __init__(self, worker, *, processor_factory=prepare_meeting, capture_factory=MeetingCaptureSession,
                 indicator_seconds=10.):
        if (type(indicator_seconds) not in (int, float) or not math.isfinite(indicator_seconds)
                or not 0 < indicator_seconds <= 30):
            raise ValueError('Invalid meeting indicator deadline')
        self.worker, self.processor_factory, self.capture_factory = worker, processor_factory, capture_factory
        self.indicator_seconds = indicator_seconds
        self.active = self.recovery = self.latest = None

    @property
    def busy(self):
        return self.active is not None

    def status_is_current(self, status):
        return type(status) is MeetingStatus and status is self.latest

    def _status(self, job, phase, *, reason='', progress=None, note_id=None):
        if progress is not None:
            progress = max(0, min(100, int(progress)))
        retained = None
        if phase == 'recovery':
            retained = 'text' if job.draft is not None or job.transcript is not None else 'audio'
        value = MeetingStatus(job.ticket, phase, job.capture_stopped, reason, progress, note_id, retained)
        if value != self.latest:
            self.latest = value
            self.worker.emit('meeting_status', value)

    def request(self, request, *, expected_config=None):
        w = self.worker
        if type(request) is not CaptureRequest or not request.consent or not w._lock.acquire(blocking=False):
            return False
        try:
            if (w._closing or w.busy or w._pending_config is not None or self.recovery is not None
                    or w.services.config.get('labs', {}).get('notetaker') is not True
                    or expected_config is not None and w.services.config != expected_config):
                return False
            request.to_json()
            job = self.active = _Meeting(w.services, copy.deepcopy(w.services.config), request)
            w.corrections.cancel()
            self._status(job, 'indicator')
            try:
                w._submit(self._run, job)
            except Exception:
                self.active = None
                job.capture_stopped = True
                self._status(job, 'failed', reason='schedule_failed')
                return False
            return True
        finally:
            w._lock.release()

    def confirm_indicator(self, status):
        job = self.active
        if (job is None or not self.status_is_current(status) or status.ticket is not job.ticket
                or status.phase != 'indicator' or job.cancelled.is_set() or job.stop.is_set()):
            return False
        job.indicator.set()
        return True

    def stop(self, status=None, *, cancel=False):
        job = self.active
        if job is None or status is not None and (type(status) is not MeetingStatus or status.ticket is not job.ticket):
            return False
        if cancel:
            job.cancelled.set()
        job.stop.set()
        job.indicator.set()  # Wake a pending acknowledgement without admitting capture.
        if cancel and job.processor is not None:
            editor = getattr(job.processor, 'editor', None)
            if editor is not None:
                # Interrupt a blocked summary read without joining on the GUI.
                threading.Thread(target=editor.close, name='Saydraft-meeting-model-stop', daemon=True).start()
        return True

    def cancel(self):
        return self.stop(cancel=True)

    def _cancelled(self, job):
        return job.cancelled.is_set() or self.worker._closing

    def _ready_to_start(self, job):
        w = self.worker
        return (self.active is job and not self._cancelled(job) and not job.stop.is_set()
                and w.services is job.services and w._pending_config is None)

    def _ensure_stopped(self, job):
        """Exceptional worker teardown still cannot abandon a started helper."""
        session = job.capture
        if session is None or session.owner is None:
            job.capture_stopped = True
            return
        owner = session.owner
        buffer = getattr(session, 'buffer', None)
        def drain():
            events = owner.take(limit=64)
            if buffer is not None and not self._cancelled(job):
                for event in events:
                    try:
                        buffer.consume(event)
                    except Exception:
                        pass  # Keep the valid prefix, with incomplete capture.
            return len(events)
        while True:
            try:
                drain()
                outcome = owner.stop(timeout=0)
                if type(outcome) is CaptureOutcome and outcome.stopped is True:
                    try:
                        while drain():
                            pass
                    except Exception:
                        pass  # A collection error cannot undo confirmed exit.
                    session.owner = None
                    job.capture_stopped = True
                    if buffer is not None:
                        if self._cancelled(job):
                            buffer.discard()
                        else:
                            job.collected = CollectedMeeting(replace(outcome, complete=False,
                                reason='control_failed'), None, False, buffer)
                            job.captured = True
                        session.buffer = None
                    return
            except Exception:
                pass
            self._status(job, 'stop_unconfirmed')
            threading.Event().wait(.1)

    def _run(self, job):
        phase, reason = 'failed', 'preparation_failed'
        try:
            if not job.captured:
                if not job.indicator.wait(self.indicator_seconds):
                    reason = 'indicator_unavailable'
                    return
                if not self._ready_to_start(job):
                    phase, reason = 'cancelled', 'cancelled'
                    return
            self._status(job, 'checking')
            if job.draft is None:
                job.processor = self.processor_factory(job.services, job.config, need_speech=job.transcript is None)
                job.store = job.processor.store
                if self._cancelled(job):
                    phase, reason = 'cancelled', 'cancelled'
                    return
            if not job.captured:
                if not self._ready_to_start(job):
                    phase, reason = 'cancelled', 'cancelled'
                    return
                job.capture = self.capture_factory(job.request,
                    on_status=lambda state: self._status(job, state) if state != 'stopped' else None)
                job.collected = job.capture.run(indicator_ready=True, stopping=job.stop.is_set,
                    cancelled=lambda: self._cancelled(job))
                if not job.collected.outcome.stopped:
                    raise RuntimeError('Meeting capture stop was not confirmed')
                job.capture_stopped = True
                job.captured = True
            if self._cancelled(job) or job.collected is not None and job.collected.cancelled:
                phase, reason = 'cancelled', 'cancelled'
                return
            if job.draft is None:
                if job.transcript is None:
                    audio = job.collected.audio
                    if audio is None and job.collected.pending_audio is not None:
                        audio = job.collected.pending_audio.freeze(job.collected.outcome)
                    if audio is None or not audio.tracks:
                        reason = job.collected.outcome.reason if not job.collected.outcome.complete else 'no_audio'
                        job.collected = None
                        return
                    self._status(job, 'transcribing')
                    job.transcript = job.processor.transcribe(audio, cancelled=lambda: self._cancelled(job),
                        on_progress=lambda value: self._status(job, 'transcribing', progress=value * 100))
                    if not job.transcript.utterances:
                        issues = job.transcript.issues
                        job.transcript = None
                        if issues:
                            raise RuntimeError('No usable transcript; retain audio for explicit retry')
                        job.collected = None
                        phase, reason = 'empty', 'no_speech'
                        return
                    # PCM is never written to disk and is released once a
                    # transcript exists. A later save failure retains text only.
                    audio = None
                    job.collected = None
                if self._cancelled(job):
                    phase, reason = 'cancelled', 'cancelled'
                    return
                self._status(job, 'summarizing')
                reply = job.processor.summarize(job.transcript, cancelled=lambda: self._cancelled(job))
                job.summary_reason = reply.reason
                if self._cancelled(job):
                    phase, reason = 'cancelled', 'cancelled'
                    return
                job.draft = MeetingNoteDraft.create(job.transcript, reply.summary)
            self._status(job, 'saving')
            note = job.draft.save(job.store)
            phase, reason = 'finished', job.summary_reason
            self._status(job, phase, reason=reason, note_id=note.id)
            return
        except MeetingPreparationError as error:
            reason = str(error)
        except Exception:
            reason = 'save_failed' if job.draft is not None else 'analysis_failed'
        finally:
            self._ensure_stopped(job)
            processor, job.processor = job.processor, None
            if processor is not None:
                try:
                    processor.close()
                except Exception:
                    pass  # The shared native process slot remains authoritative.
            if self._cancelled(job) and phase != 'finished':
                phase, reason = 'cancelled', 'cancelled'
            if phase == 'finished':
                job.transcript = job.draft = job.collected = None
            elif phase == 'cancelled':
                if job.collected is not None and job.collected.pending_audio is not None:
                    job.collected.pending_audio.discard()
                job.transcript = job.draft = job.collected = None
                self._status(job, phase, reason=reason)
            elif job.draft is not None or job.transcript is not None or (
                    job.collected is not None and (job.collected.audio is not None or job.collected.pending_audio is not None)):
                self.recovery = job
                self._status(job, 'recovery', reason=reason)
            else:
                self._status(job, phase, reason=reason)
            with self.worker._lock:
                if self.active is job:
                    self.active = None

    def retry(self, status):
        w = self.worker
        if not w._lock.acquire(blocking=False):
            return False
        try:
            job = self.recovery
            if (job is None or not self.status_is_current(status) or status.ticket is not job.ticket
                    or w.busy or w._closing or w._pending_config is not None):
                return False
            job.ticket, job.services = object(), w.services
            job.cancelled, job.stop = threading.Event(), threading.Event()
            self.active, self.recovery = job, None
            try:
                w._submit(self._run, job)
            except Exception:
                self.active, self.recovery = None, job
                self._status(job, 'recovery', reason='schedule_failed')
                return False
            return True
        finally:
            w._lock.release()

    def discard(self, status):
        w = self.worker
        if not w._lock.acquire(blocking=False):
            return False
        try:
            job = self.recovery
            if (job is None or not self.status_is_current(status) or status.ticket is not job.ticket
                    or w.busy or w._closing):
                return False
            job.ticket = object()
            self.active, self.recovery = job, None
            try:
                w._submit(self._discard, job)
            except Exception:
                self.active, self.recovery = None, job
                self._status(job, 'recovery', reason='schedule_failed')
                return False
            return True
        finally:
            w._lock.release()

    def _discard(self, job):
        if job.collected is not None and job.collected.pending_audio is not None:
            job.collected.pending_audio.discard()
        job.collected = job.transcript = job.draft = None
        self._status(job, 'discarded')
        with self.worker._lock:
            if self.active is job:
                self.active = None
