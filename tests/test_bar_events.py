from dataclasses import asdict
import threading
from types import SimpleNamespace

import pytest

from saydraft.core.bar_status import BarPhase as Phase, BarStatus, BarUpdate
from saydraft.insert.inserter import InsertionResult
from tests.test_session_worker import make_worker


def observed_worker(**kwargs):
    worker, clock, executor, history, signals, keyboard = make_worker(**kwargs)
    updates = []
    worker.bar_status.callback = updates.append
    return worker, clock, executor, history, signals, updates


def test_preparing_precedes_context_model_and_microphone_then_reports_actual_insertion():
    worker, clock, _, _, _, updates = observed_worker()
    target = worker.services.context.capture()

    def capture():
        assert updates[-1].phase == Phase.PREPARING
        assert worker.services.recorder.started == 0
        return target

    def prepare():
        assert updates[-1].phase == Phase.PREPARING

    worker.services.context.capture = capture
    worker.services.asr.prepare = prepare
    worker.start_recording()
    assert [update.phase for update in updates] == [Phase.PREPARING, Phase.LISTENING]
    clock.now = .5
    worker.stop_recording()
    assert [update.phase for update in updates] == [Phase.PREPARING, Phase.LISTENING, Phase.PROCESSING, Phase.INSERTED]
    assert updates[-1].saved and worker.last_result.history_id == 1
    assert len({update.generation for update in updates}) == 1
    assert set(asdict(updates[-1])) == {"generation", "phase", "reason", "saved"}


@pytest.mark.parametrize("reason", ["focus_changed", "password_field", "target_elevated", "field_unavailable",
    "clipboard_changed", "insertion_unconfirmed", "integrity_unavailable", "modifier_held"])
def test_delivery_refusal_is_a_saved_warning_even_with_legacy_completion_signal(reason):
    worker, clock, _, _, signals, updates = observed_worker()
    worker.services.inserter.insert_text = lambda *args, **kwargs: InsertionResult("not_inserted", "none", reason)
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert updates[-1].phase == Phase.NOT_INSERTED
    assert updates[-1].reason == reason and updates[-1].saved
    assert signals[-1][0] == "processing_finished"


def test_history_write_failure_never_claims_saved_and_keeps_the_recoverable_result():
    worker, clock, _, _, _, updates = observed_worker()

    def fail(_entry):
        raise OSError("fixture disk full")

    worker.services.history.append = fail
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert updates[-1].phase == Phase.NOT_INSERTED and updates[-1].reason == "history_unavailable"
    assert updates[-1].saved is False
    assert worker.last_result in worker.services.processor.pending_results


@pytest.mark.parametrize("review_only", [False, True])
def test_history_only_and_preview_review_have_distinct_saved_reasons(monkeypatch, review_only):
    worker, clock, _, history, _, updates = observed_worker()
    if review_only:
        monkeypatch.setattr("saydraft.core.worker.choose_preview_result", lambda *args, **kwargs:
            SimpleNamespace(text="public review fixture", model="fixture", language="en", review_only=True, edits=()))
    worker.start_recording(insert_text=review_only)
    clock.now = 1
    worker.stop_recording()
    assert [item[0] for item in history] == ["history"]
    assert updates[-1] == BarUpdate(updates[0].generation, Phase.NOT_INSERTED,
        "review_only" if review_only else "saved_only", True)


@pytest.mark.parametrize("short", [True, False])
def test_short_or_empty_dictation_returns_to_idle_without_a_false_inserted_event(short):
    worker, clock, executor, history, _, updates = observed_worker(queued=True)
    worker.services.asr.transcribe = lambda audio: ""
    worker.start_recording()
    executor.drain()
    clock.now = .499 if short else 1
    worker.stop_recording()
    if short:
        assert updates[-1].phase == Phase.IDLE  # Collapse before the audio-stop task runs.
    executor.drain()
    assert updates[-1].phase == Phase.IDLE and not history
    assert Phase.INSERTED not in [update.phase for update in updates]


@pytest.mark.parametrize("stage", ["context", "model"])
def test_cancel_during_blocked_preparation_invalidates_the_ui_before_work_returns(stage):
    worker, _, executor, _, _, updates = observed_worker(queued=True)
    entered, release = threading.Event(), threading.Event()
    target = worker.services.context.capture()

    def blocked():
        entered.set()
        assert release.wait(3)
        if stage == "model":
            raise OSError("late model failure after cancellation")
        return target

    if stage == "context":
        worker.services.context.capture = blocked
    else:
        worker.services.asr.prepare = blocked
    if stage == "model":
        worker.start_recording()
    thread = threading.Thread(target=worker.start_recording if stage == "context" else executor.drain)
    thread.start()
    try:
        assert entered.wait(2)
        preparing = updates[0]
        assert preparing.phase == Phase.PREPARING
        worker.cancel()
        assert updates[-1].phase == Phase.IDLE
        assert not worker.bar_status.is_current(preparing.generation)
        assert worker.services.recorder.started == 0
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive()
    assert updates[-1].phase == Phase.IDLE and worker.services.recorder.started == 0


def test_cancelled_finalization_can_save_words_without_reopening_a_warning():
    worker, clock, executor, history, _, updates = observed_worker(queued=True)
    worker.start_recording()
    executor.drain()
    clock.now = 1
    worker.stop_recording()
    worker.cancel()
    idle = updates[-1]
    executor.drain()
    assert history and updates[-1] == idle and idle.phase == Phase.IDLE
    assert all(update.phase != Phase.NOT_INSERTED for update in updates)


@pytest.mark.parametrize("model", [True, False])
def test_startup_error_has_a_public_fix_reason_without_exception_details(model):
    worker, _, _, _, _, updates = observed_worker()

    def fail():
        raise OSError("private filesystem fixture path")

    if model:
        worker.services.asr.prepare = fail
    else:
        worker.services.recorder.start = fail
    worker.start_recording()
    assert updates[-1].phase == Phase.ERROR
    assert updates[-1].reason == ("model_unavailable" if model else "microphone_unavailable")
    assert "private" not in str(updates[-1]) and updates[-1].saved is False


def test_failed_recognition_is_an_error_and_never_claims_a_history_save():
    worker, clock, _, _, _, updates = observed_worker()

    def fail(_audio):
        raise OSError("fixture recognition failed")

    worker.services.asr.transcribe = fail
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert updates[-1].phase == Phase.ERROR and updates[-1].reason == "processing_failed"
    assert updates[-1].saved is False


def test_failed_pre_session_capture_does_not_reuse_its_bar_generation():
    worker, _, _, _, _, updates = observed_worker()
    capture = worker.services.context.capture

    def fail():
        raise OSError("fixture context unavailable")

    worker.services.context.capture = fail
    assert worker.start_recording() is False
    assert worker.session.session_id == 0 and updates[-1].phase == Phase.IDLE
    previous = updates[0].generation
    worker.services.context.capture = capture
    worker.start_recording()
    assert worker.session.session_id == 1 and updates[-1].generation > previous
    assert not worker.bar_status.is_current(previous)
    worker.cancel()


def test_stale_session_and_cancelled_pre_session_bindings_cannot_emit_current_events():
    updates = []
    status = BarStatus(updates.append)
    first = status.begin()
    status.cancel()
    second = status.begin()
    status.bind(1, first)
    status.session(1, Phase.ERROR)
    assert updates[-1].phase == Phase.PREPARING and updates[-1].generation == second
    status.bind(2, second)
    status.session(1, Phase.INSERTED)
    assert updates[-1].phase == Phase.PREPARING
    status.session(2, Phase.LISTENING)
    assert updates[-1].phase == Phase.LISTENING


def test_observer_failure_does_not_stop_capture_or_delivery():
    worker, clock, _, history, _, _ = observed_worker()

    def fail(_update):
        raise RuntimeError("fixture receiver closed")

    worker.bar_status.callback = fail
    assert worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert worker.last_result.insertion.status == "inserted" and history


def test_hotkey_reconfiguration_preserves_the_completed_delivery_warning():
    from saydraft.config import default_config

    worker, clock, _, _, _, updates = observed_worker()
    worker.services.inserter.insert_text = lambda *args, **kwargs: InsertionResult("not_inserted", "none", "focus_changed")
    worker.hotkeys.start()
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    warning = updates[-1]
    assert warning.phase == Phase.NOT_INSERTED
    worker.services_factory = lambda *args, **kwargs: worker.services
    worker.configure(default_config())
    assert worker.hotkeys.enabled and updates[-1] == warning
    assert worker.bar_status.is_current(warning.generation)
    worker.shutdown()


def test_late_same_session_failure_cannot_replace_an_authoritative_inserted_outcome():
    worker, clock, _, _, _, updates = observed_worker()

    def fail(*args):
        raise RuntimeError("fixture post-delivery observer failed")

    worker.corrections.complete = fail
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert updates[-1].phase == Phase.INSERTED
    worker.bar_status.session(worker.session.session_id, Phase.ERROR, reason="processing_failed")
    assert updates[-1].phase == Phase.INSERTED
