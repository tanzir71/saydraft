"""Release timing survives worker queues, recognition and captured context."""

import pytest

from saydraft.core.session import DictationSession
from tests.test_cleanup_gate import generation_requests, prepared_pipeline
from tests.test_processing import make_processor
from tests.test_session_worker import make_worker


def release_worker(*, queue_delay=0, recorder_delay=0, asr_delay=0):
    pipeline, model, local, client, clock, timeouts, _ = prepared_pipeline()
    processor = make_processor(cleaner=pipeline)
    worker, _unused_clock, executor, events, signals, _ = make_worker(queued=True, processor=processor)
    worker.session = DictationSession(clock=lambda: clock.now)
    # Match the actual captured context, as background preparation does in production.
    assert client.prepare_prompt(app="Notepad").reason == "prepared"
    model.requests.clear()
    timeouts.clear()
    original_stop = worker.services.recorder.stop

    def stop():
        clock.now += recorder_delay
        return original_stop()

    def transcribe(audio):
        clock.now += asr_delay
        return "um hello"

    worker.services.recorder.stop = stop
    worker.services.asr.transcribe = transcribe
    assert worker.start_recording()
    executor.drain()
    assert worker._context.cleanup_deadline is None  # Listening has no running release budget.
    clock.now += 1.5
    released_at = clock.now
    worker.stop_recording()
    assert worker._context.cleanup_deadline == released_at + 2
    clock.now += queue_delay
    executor.drain()
    return worker, local, model, timeouts, events, signals, clock, executor


@pytest.mark.parametrize("delays,timeout", [
    ({}, .75), ({"asr_delay": 1.6}, .35),
    ({"queue_delay": .5, "recorder_delay": .2, "asr_delay": 1}, .25),
])
def test_release_budget_charges_all_stages_before_real_cleanup_client(delays, timeout):
    worker, local, model, timeouts, events, _signals, _clock, _executor = release_worker(**delays)
    assert timeouts == [pytest.approx(timeout)]
    assert len(generation_requests(model)) == 1 and local.last_gate_info["reason"] == "call"
    assert [event[0] for event in events] == ["history", "insert"]
    assert events[0][1].llm_decision == "accepted" and worker.last_result.cleaned_text == "Hello"


@pytest.mark.parametrize("delays", [
    {"queue_delay": 2.1}, {"recorder_delay": 2.1}, {"asr_delay": 2.1},
    {"queue_delay": .8, "recorder_delay": .3, "asr_delay": .9},
])
def test_exhausted_release_budget_never_tokenizes_and_still_saves_before_delivery(delays):
    worker, local, model, timeouts, events, _signals, _clock, _executor = release_worker(**delays)
    assert not model.requests and not timeouts
    assert local.last_gate_info["reason"] == "skip_budget"
    assert [event[0] for event in events] == ["history", "insert"]
    assert events[0][1].llm_decision == "skip_budget" and worker.last_result.cleaned_text == "Hello"


def test_next_recording_gets_its_own_release_budget_after_an_expired_one():
    worker, _local, model, timeouts, events, _signals, clock, executor = release_worker(queue_delay=2.1)
    expired = worker._context.cleanup_deadline
    assert worker.start_recording()
    executor.drain()
    assert worker._context.cleanup_deadline is None
    clock.now += 1.5
    worker.stop_recording()
    executor.drain()
    assert worker._context.cleanup_deadline > expired
    assert timeouts == [.75] and len(generation_requests(model)) == 1
    assert [event[1].llm_decision for event in events if event[0] == "history"] == ["skip_budget", "accepted"]
