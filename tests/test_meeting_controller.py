from dataclasses import replace
from types import SimpleNamespace as NS
import threading

import pytest

from saydraft.core.meeting_controller import MeetingController
from saydraft.data.notes import NoteStore
from saydraft.meetings.session import MeetingCaptureSession
from saydraft.meetings.request import CaptureRequest
from saydraft.meetings.summary import SummaryReply
from saydraft.meetings.transcription import MeetingTranscript, Utterance
from tests.test_meeting_session import Capture, Clock
from tests.test_session_worker import make_worker


def rig(tmp_path):
    worker, _, executor, _, signals, _ = make_worker(queued=True)
    worker.services.config['labs']['notetaker'] = True
    store = NoteStore(tmp_path / 'meeting.db')
    primary = store.save('a' * 32, 'Independent active Scratchpad')
    owner, clock, calls = Capture(count=1), Clock(), []
    transcript = MeetingTranscript((Utterance(1, 'microphone', 0., .1, (0,),
        'We agreed to publish on Tuesday.', 'public-fixture', 'en'),), (), True, .1)
    processor = NS(store=store, closed=0, editor=None, prepare_hook=lambda: None,
        transcribe_hook=lambda: None, summary_hook=lambda: None, save_hook=lambda: None)
    def transcribe(audio, **options):
        calls.append(('transcribe', audio, options))
        processor.transcribe_hook()
        return replace(transcript, capture_complete=audio.complete)
    def summarize(source, **options):
        calls.append(('summary', source, options))
        processor.summary_hook()
        return SummaryReply(None, 'timeout')  # Transcript-only Notes are still saved.
    def close():
        processor.closed += 1
    processor.transcribe, processor.summarize, processor.close = transcribe, summarize, close
    def prepare(services, config, **options):
        calls.append(('prepare', services, config, options))
        processor.prepare_hook()
        return processor
    def capture(request, **options):
        calls.append(('capture_factory', request))
        return MeetingCaptureSession(request, capture_factory=lambda _request: owner,
            clock=clock, wait=clock.wait, **options)
    worker.meeting = MeetingController(worker, processor_factory=prepare, capture_factory=capture, indicator_seconds=.02)
    return NS(worker=worker, controller=worker.meeting, executor=executor, signals=signals,
        store=store, primary=primary, owner=owner, calls=calls, processor=processor)


def start(f):
    assert f.controller.request(CaptureRequest(consent=True, max_seconds=30))
    status = f.controller.latest
    assert f.controller.confirm_indicator(status)
    return status


def test_end_to_end_worker_owns_capture_until_stopped_then_saves_an_independent_note(tmp_path):
    f = rig(tmp_path)
    start(f)
    assert f.worker.busy and not f.calls and not f.owner.started
    f.executor.drain()
    assert f.controller.latest.phase == 'finished' and f.controller.latest.capture_stopped
    assert f.controller.latest.reason == 'timeout'  # Visible summary fallback.
    saved = f.store.get(f.controller.latest.note_id)
    assert saved.kind == 'meeting' and 'We agreed to publish on Tuesday.' in saved.body
    assert 'Summary unavailable' in saved.body and f.store.active() == f.primary
    assert not f.worker.busy and not f.owner.active and f.processor.closed == 1
    assert [call[0] for call in f.calls] == ['prepare', 'capture_factory', 'transcribe', 'summary']
    updates = [args[1] for args in f.signals if args[0] == 'meeting_status']
    assert all(not item.capture_stopped for item in updates if item.phase in ('indicator', 'checking', 'preparing', 'recording'))
    assert all(item.capture_stopped for item in updates if item.phase in ('transcribing', 'summarizing', 'saving', 'finished'))


@pytest.mark.parametrize('reason', ['disabled', 'busy', 'settings_pending', 'closing', 'no_consent'])
def test_refused_admission_has_no_device_model_or_indicator_side_effect(tmp_path, reason):
    f = rig(tmp_path)
    if reason == 'disabled':
        f.worker.services.config['labs']['notetaker'] = False
    elif reason == 'busy':
        f.worker._inflight = 1
    elif reason == 'settings_pending':
        f.worker._pending_config = {}
    elif reason == 'closing':
        f.worker._closing = True
    assert not f.controller.request(CaptureRequest(consent=reason != 'no_consent'))
    assert not f.calls and f.controller.latest is None and not f.owner.started


def test_no_painted_indicator_acknowledgement_means_no_model_or_native_capture(tmp_path):
    f = rig(tmp_path)
    assert f.controller.request(CaptureRequest(consent=True))
    f.executor.drain()
    assert f.controller.latest.reason == 'indicator_unavailable' and f.controller.latest.capture_stopped
    assert not f.calls and not f.owner.started and not f.worker.busy


@pytest.mark.parametrize('stage', ['queued', 'after_indicator', 'prepare', 'capture', 'transcribe', 'summary'])
def test_cancel_at_each_boundary_never_saves_or_reports_a_late_note(tmp_path, stage):
    f = rig(tmp_path)
    assert f.controller.request(CaptureRequest(consent=True))
    if stage != 'queued':
        assert f.controller.confirm_indicator(f.controller.latest)
    if stage in ('queued', 'after_indicator'):
        f.worker.cancel()
    elif stage == 'prepare':
        f.processor.prepare_hook = f.worker.cancel
    elif stage == 'capture':
        f.owner.on_start = f.worker.cancel
    elif stage == 'transcribe':
        f.processor.transcribe_hook = f.worker.cancel
    else:
        f.processor.summary_hook = f.worker.cancel
    f.executor.drain()
    assert f.controller.latest.phase == 'cancelled' and f.controller.latest.capture_stopped
    assert f.store.list() == (f.store.list()[0],) and f.store.active() == f.primary
    assert not f.worker.busy and f.controller.recovery is None and not f.owner.active


def test_reservation_refuses_dictation_practice_and_model_removal_until_the_meeting_finishes(tmp_path):
    f = rig(tmp_path)
    start(f)
    assert not f.worker.start_recording()
    assert not f.worker.open_practice(f.worker.services.config, 1, lambda: True, 'messages')
    with pytest.raises(ValueError, match='busy'):
        f.worker.remove_stored_model(None)
    assert not f.controller.request(CaptureRequest(consent=True))
    f.executor.drain()
    assert not f.worker.busy


def test_stale_indicator_and_stop_cannot_admit_or_cancel_a_successor(tmp_path):
    f = rig(tmp_path)
    old = start(f)
    f.executor.drain()
    assert f.controller.request(CaptureRequest(consent=True))
    current = f.controller.latest
    assert not f.controller.confirm_indicator(old) and not f.controller.stop(old, cancel=True)
    assert not f.controller.status_is_current(old) and f.controller.status_is_current(current)
    f.controller.cancel()
    f.executor.drain()


def test_pending_settings_before_capture_revoke_admission_without_touching_devices(tmp_path):
    f = rig(tmp_path)
    start(f)
    f.processor.prepare_hook = lambda: setattr(f.worker, '_pending_config', {})
    # Avoid applying a synthetic empty config after the reservation retires.
    f.worker.configure = lambda config: None
    f.executor.drain()
    assert f.controller.latest.phase == 'cancelled' and not f.owner.started


def test_note_save_failure_preserves_text_only_and_retry_never_recaptures_or_retranscribes(tmp_path, monkeypatch):
    f = rig(tmp_path)
    real_save = f.store.save
    def failed_save(*args, **kwargs):
        raise OSError('Fixture disk unavailable')
    monkeypatch.setattr(f.store, 'save', failed_save)
    start(f)
    f.executor.drain()
    status = f.controller.latest
    assert status.phase == 'recovery' and status.reason == 'save_failed' and not f.worker.busy
    draft = f.controller.recovery.draft
    assert draft is not None and f.controller.recovery.collected is None and f.store.active() == f.primary
    assert not f.controller.request(CaptureRequest(consent=True))
    monkeypatch.setattr(f.store, 'save', real_save)
    before = len(f.calls)
    assert f.controller.retry(status) and f.worker.busy
    f.executor.drain()
    assert len(f.calls) == before and f.controller.latest.note_id == draft.id and f.store.get(draft.id).kind == 'meeting'
    assert f.controller.latest.phase == 'finished' and f.store.active() == f.primary and not f.worker.busy
    assert not f.controller.retry(status)


def test_failed_summary_retry_uses_preserved_transcript_without_another_recording(tmp_path):
    f = rig(tmp_path)
    def fail():
        raise OSError('Fixture model crashed')
    f.processor.summary_hook = fail
    start(f)
    f.executor.drain()
    status = f.controller.latest
    assert status.phase == 'recovery' and f.controller.recovery.transcript is not None
    assert f.controller.recovery.collected is None
    f.processor.summary_hook = lambda: None
    assert f.controller.retry(status)
    f.executor.drain()
    assert [call[0] for call in f.calls].count('capture_factory') == 1
    assert [call[0] for call in f.calls].count('transcribe') == 1
    assert [call for call in f.calls if call[0] == 'prepare'][-1][-1] == {'need_speech': False}
    assert f.controller.latest.phase == 'finished'


def test_failed_recognition_retry_uses_only_the_retained_in_memory_audio(tmp_path):
    f = rig(tmp_path)
    def fail():
        raise OSError('Fixture recognition failed')
    f.processor.transcribe_hook = fail
    start(f)
    f.executor.drain()
    status = f.controller.latest
    audio = f.controller.recovery.collected.audio
    assert status.phase == 'recovery' and audio is not None and not f.owner.active
    f.processor.transcribe_hook = lambda: None
    assert f.controller.retry(status)
    f.executor.drain()
    assert [call[0] for call in f.calls].count('capture_factory') == 1
    assert [call for call in f.calls if call[0] == 'transcribe'][-1][1] is audio
    assert f.controller.latest.phase == 'finished'


def test_explicit_recovery_discard_is_queued_and_does_not_change_notes(tmp_path):
    f = rig(tmp_path)
    f.processor.transcribe_hook = lambda: (_ for _ in ()).throw(OSError('Fixture ASR failure'))
    start(f)
    f.executor.drain()
    status = f.controller.latest
    assert f.controller.discard(status) and f.worker.busy
    f.executor.drain()
    assert f.controller.latest.phase == 'discarded' and f.controller.recovery is None and not f.worker.busy
    assert f.store.active() == f.primary and len(f.store.list()) == 1


def test_cancellation_after_note_commit_reports_the_saved_note_instead_of_claiming_discard(tmp_path, monkeypatch):
    f = rig(tmp_path)
    real_save = f.store.save
    def committed(*args, **kwargs):
        result = real_save(*args, **kwargs)
        f.controller.cancel()
        return result
    monkeypatch.setattr(f.store, 'save', committed)
    start(f)
    f.executor.drain()
    assert f.controller.latest.phase == 'finished' and f.store.get(f.controller.latest.note_id) is not None
    assert f.store.active() == f.primary


def test_unconfirmed_stop_keeps_the_app_busy_and_indicator_recording_until_exit(tmp_path):
    f = rig(tmp_path)
    f.owner.allow_exit = False
    f.owner.on_start = lambda: f.controller.stop()
    original_emit = f.worker.emit_callback
    def emit(name, *args):
        original_emit(name, *args)
        if name == 'meeting_status' and args[0].phase == 'stop_unconfirmed':
            assert f.worker.busy and not args[0].capture_stopped and f.controller.active.capture.owner is f.owner
            f.owner.allow_exit = True
            f.owner.outcome = replace(f.owner.outcome, complete=False, forced=True)
    f.worker.emit_callback = emit
    start(f)
    f.executor.drain()
    assert f.controller.latest.capture_stopped and not f.worker.busy and not f.owner.active


def test_shutdown_cancels_queued_meeting_without_starting_audio(tmp_path):
    f = rig(tmp_path)
    start(f)
    f.worker.shutdown()
    f.executor.drain()
    assert f.controller.latest.phase == 'cancelled' and not f.owner.started and not f.worker.busy


def test_exceptional_collection_teardown_confirms_stop_and_preserves_the_valid_pcm_prefix(tmp_path):
    f = rig(tmp_path)
    def capture(request, **options):
        def failed_wait(seconds):
            raise RuntimeError('Fixture worker wait failure after creation')
        return MeetingCaptureSession(request, capture_factory=lambda _request: f.owner, wait=failed_wait, **options)
    f.controller.capture_factory = capture
    start(f)
    f.executor.drain()
    assert not f.owner.active and not f.worker.busy
    assert f.controller.latest.phase == 'recovery' and f.controller.latest.capture_stopped
    recovered = f.controller.recovery.collected
    assert recovered.pending_audio is not None and not recovered.outcome.complete
    assert f.controller.retry(f.controller.latest)
    f.executor.drain()
    assert f.controller.latest.phase == 'finished' and not f.owner.active


def test_model_cancel_shutdown_runs_off_the_requesting_thread(tmp_path):
    f = rig(tmp_path)
    closed, ids = threading.Event(), []
    def close():
        ids.append(threading.get_ident())
        closed.set()
    f.processor.editor = NS(close=close)
    f.processor.summary_hook = f.controller.cancel
    start(f)
    f.executor.drain()
    assert closed.wait(2) and ids[0] != threading.get_ident()
    assert f.controller.latest.phase == 'cancelled'
