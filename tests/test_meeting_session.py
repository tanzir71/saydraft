from collections import deque
from dataclasses import replace
import threading

import numpy as np
import pytest

from saydraft.meetings.process import CaptureOutcome
from saydraft.meetings.protocol import AudioChunk, CaptureEnd, CaptureEvent, TrackStarted
from saydraft.meetings.request import CaptureRequest
from saydraft.meetings.session import MeetingCaptureSession
from saydraft.meetings.timeline import MeetingAudioBuffer


class Clock:
    now = 0.

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.now += seconds


def packets(count=100):
    output = [CaptureEvent('track', TrackStarted(track, .1)) for track in ('microphone', 'desktop')]
    output.append(CaptureEvent('ready'))
    for index in range(count):
        for track, value in (('microphone', .25), ('desktop', -.5)):
            output.append(CaptureEvent('audio', AudioChunk(track, index * 1600, np.full(1600, value, np.float32))))
    end = CaptureEnd(True, 'stopped', count * 1600, count * 1600)
    output.append(CaptureEvent('end', end))
    return output, CaptureOutcome(True, True, 'stopped', 0, end=end)


class Capture:
    def __init__(self, *, count=100):
        self.pending, self.outcome = packets(count)
        self.queue = deque()
        self.active = self.started = False
        self.stop_requests = self.forces = 0
        self.exit_hook = lambda: None
        self.allow_exit = True
        self.on_start = lambda: None
        self.calls = []

    def start(self, **options):
        self.calls.append(('start', threading.get_ident(), options))
        self.active = self.started = True
        self.on_start()

    def take(self, *, limit):
        result = []
        for _ in range(min(limit, len(self.queue))):
            result.append(self.queue.popleft())
        return result

    def poll(self):
        # Simulate a bounded native producer. A caller that fails to drain the
        # stream overflows this queue long before these two tracks complete.
        if self.pending:
            batch, self.pending = self.pending[:20], self.pending[20:]
            assert len(self.queue) + len(batch) <= 64
            self.queue.extend(batch)
            return None
        if self.allow_exit:
            self.exit_hook()
            self.active = False
            return self.outcome
        return None

    def request_stop(self):
        self.calls.append(('signal', threading.get_ident()))
        self.stop_requests += 1

    def stop(self, *, timeout):
        self.calls.append(('stop', threading.get_ident(), timeout))
        self.forces += 1
        if self.allow_exit:
            self.active = False
            return replace(self.outcome, complete=False, forced=True)
        return CaptureOutcome(False, False, 'stop_unconfirmed', forced=True)


def rig(owner=None, **options):
    owner, clock, phases = owner or Capture(), Clock(), []
    session = MeetingCaptureSession(CaptureRequest(consent=True, max_seconds=30),
        capture_factory=lambda request: owner, clock=clock, wait=clock.wait, on_status=phases.append, **options)
    return session, owner, clock, phases


def test_continuously_drained_two_track_capture_keeps_all_samples_and_final_end():
    session, owner, clock, phases = rig()
    result = session.run(indicator_ready=True)
    assert result.outcome.complete and result.outcome.stopped and not result.cancelled
    assert result.audio.complete and result.audio.duration == 10.1
    assert [track.frames for track in result.audio.tracks] == [160000, 160000]
    assert np.all(result.audio.waveform(result.audio.tracks[0]) == .25)
    assert np.all(result.audio.waveform(result.audio.tracks[1]) == -.5)
    assert phases == ['preparing', 'recording', 'stopped']
    assert not owner.active and session.owner is None and not owner.queue


@pytest.mark.parametrize('consent,visible', [(False, True), (True, False), (True, 1)])
def test_no_capture_factory_before_both_explicit_consent_and_indicator(consent, visible):
    calls = []
    session = MeetingCaptureSession(CaptureRequest(consent=consent), capture_factory=calls.append)
    with pytest.raises(PermissionError):
        session.run(indicator_ready=visible)
    assert not calls


def test_cancel_before_start_never_creates_native_resources():
    session, owner, _, phases = rig()
    result = session.run(indicator_ready=True, cancelled=lambda: True)
    assert result.cancelled and result.audio is None and result.outcome.stopped
    assert not owner.calls and phases == ['preparing', 'stopped']


def test_cancel_racing_constructor_never_starts_and_retires_the_unused_owner():
    cancelled = threading.Event()
    owner = Capture()
    def factory(request):
        cancelled.set()
        return owner
    session = MeetingCaptureSession(CaptureRequest(consent=True), capture_factory=factory)
    result = session.run(indicator_ready=True, cancelled=cancelled.is_set)
    assert result.cancelled and result.audio is None and session.owner is None and not owner.calls


def test_cancel_after_start_keeps_draining_but_discards_all_pcm():
    session, owner, _, phases = rig()
    result = session.run(indicator_ready=True, cancelled=lambda: owner.started)
    assert result.cancelled and result.audio is None and result.pending_audio is None
    assert result.outcome.stopped and owner.stop_requests == 1 and not owner.queue
    assert phases == ['preparing', 'stopping', 'stopped']


def test_cancel_during_final_exit_discards_the_tail_too():
    cancelled = threading.Event()
    session, owner, _, _ = rig()
    owner.exit_hook = cancelled.set
    result = session.run(indicator_ready=True, cancelled=cancelled.is_set)
    assert result.cancelled and result.audio is None and not owner.queue


def test_unconfirmed_stop_retains_owner_and_never_announces_stopped_until_exit():
    owner = Capture(count=1)
    owner.allow_exit = False
    session, _, clock, phases = rig(owner, stop_grace=.04)
    def status(phase):
        phases.append(phase)
        if phase == 'stop_unconfirmed':
            assert owner.active and session.owner is owner and 'stopped' not in phases
            owner.allow_exit = True
            owner.outcome = replace(owner.outcome, complete=False, forced=True)
    session.on_status = status
    result = session.run(indicator_ready=True, stopping=lambda: owner.started)
    assert owner.forces == 1 and owner.stop_requests == 1 and result.outcome.stopped
    assert phases[-2:] == ['stop_unconfirmed', 'stopped'] and session.owner is None
    assert result.audio is not None and not result.audio.complete


def test_gui_stop_intent_has_no_native_calls_on_the_requesting_thread():
    session, owner, _, _ = rig()
    entered, release, stop = threading.Event(), threading.Event(), threading.Event()
    original_start = owner.on_start
    def on_start():
        entered.set()
        assert release.wait(2)
        original_start()
    owner.on_start = on_start
    values = []
    thread = threading.Thread(target=lambda: values.append(session.run(indicator_ready=True, stopping=stop.is_set)))
    thread.start()
    try:
        assert entered.wait(2)
        stop.set()  # The UI/controller sets only this event.
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive() and values[0].outcome.stopped
    assert all(call[1] == thread.ident for call in owner.calls)


def test_start_failure_after_creation_still_waits_for_confirmed_exit():
    session, owner, _, phases = rig()
    def fail():
        raise OSError('Public fixture start failure')
    owner.on_start = fail
    result = session.run(indicator_ready=True)
    assert result.outcome.stopped and not result.outcome.complete and result.outcome.reason == 'start_failed'
    assert owner.stop_requests == 1 and not owner.active and session.owner is None
    assert phases[-1] == 'stopped' and result.audio is not None and not result.audio.complete


def test_capture_factory_failure_returns_stopped_without_starting_a_child():
    def factory(_request):
        raise OSError('Unavailable fixture helper')
    session = MeetingCaptureSession(CaptureRequest(consent=True), capture_factory=factory)
    result = session.run(indicator_ready=True)
    assert result.outcome.stopped and result.outcome.reason == 'start_failed' and session.owner is None


def test_bad_collection_preserves_the_valid_prefix_and_flags_incomplete_capture():
    owner = Capture(count=1)
    owner.pending.insert(-1, CaptureEvent('audio', AudioChunk('microphone', 0, np.zeros(10, np.float32))))
    session, _, _, _ = rig(owner)
    result = session.run(indicator_ready=True)
    assert result.outcome.stopped and result.outcome.reason == 'collection_failed'
    assert not result.audio.complete and result.audio.tracks[0].frames == 1600
    assert 'incomplete_capture' in result.audio.issues


def test_startup_watchdog_requests_stop_and_keeps_a_missing_ready_stream_incomplete():
    session, owner, _, phases = rig(Capture(count=1), startup_seconds=.02, stop_grace=.02)
    owner.pending = [event for event in owner.pending if event.kind != 'ready']
    owner.allow_exit = False
    def status(phase):
        phases.append(phase)
        if phase == 'stop_unconfirmed':
            owner.allow_exit = True
    session.on_status = status
    result = session.run(indicator_ready=True)
    assert result.outcome.stopped and result.outcome.reason == 'startup_timeout' and not result.audio.complete
    assert owner.stop_requests == 1 and owner.forces >= 1


def test_failed_final_allocation_keeps_bounded_pcm_for_worker_retry(monkeypatch):
    original = MeetingAudioBuffer.freeze
    def fail_once(self, outcome):
        monkeypatch.setattr(MeetingAudioBuffer, 'freeze', original)
        raise MemoryError('Fixture allocation failure')
    monkeypatch.setattr(MeetingAudioBuffer, 'freeze', fail_once)
    session, _, _, _ = rig(Capture(count=1))
    result = session.run(indicator_ready=True)
    assert result.audio is None and result.pending_audio is not None and result.outcome.stopped
    recovered = result.pending_audio.freeze(result.outcome)
    assert not recovered.complete and [track.frames for track in recovered.tracks] == [1600, 1600]


def test_indicator_receiver_failure_cannot_abandon_capture_and_sessions_are_one_use():
    session, owner, _, _ = rig()
    def failed_receiver(phase):
        raise RuntimeError('Fixture view closed')
    session.on_status = failed_receiver
    assert session.run(indicator_ready=True).outcome.stopped and not owner.active
    with pytest.raises(RuntimeError, match='only once'):
        session.run(indicator_ready=True)
