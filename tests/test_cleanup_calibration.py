import json
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.calibration import DecoderCalibration
from saydraft.cleanup.llm.client import CleanupReply
from saydraft.cleanup.llm.prompts import PromptHints
from saydraft.cleanup.llm.sidecar import SidecarReply
from tests.test_cleanup_preparation import fixture


def decoder(responses, *, reason="ok", after=lambda manager: None):
    requests, operations = [], []
    values = iter(responses)
    manager = SimpleNamespace(generation=1)

    def request(path, **kwargs):
        requests.append((path, kwargs))
        return next(values)

    def run(operation, *, timeout):
        operations.append(timeout)
        if reason != "ok":
            return SidecarReply(None, reason)
        result = operation(SimpleNamespace(request_json=request), 123)
        after(manager)
        return SidecarReply(result, "ok")

    manager.run = run
    return DecoderCalibration(manager), manager, requests, operations


def sample(rate=30, count=60):
    return {"timings": {"predicted_n": count, "predicted_per_second": rate}, "content": "discard this generated prose"}


def test_three_exact_generations_share_one_deadline_and_cache_only_live_instance_metadata():
    calibration, manager, requests, operations = decoder([sample(20), sample(30), sample(25)] * 2)
    assert not requests and calibration.current is None
    assert calibration.measure() == "calibrated" and operations == [60]
    assert calibration.current.metadata() == {"generation": 1, "tokens_per_sample": 60, "sample_count": 3,
        "tokens_per_second": [20, 30, 25], "median_tps": 25, "conservative_tps": 20}
    assert "discard this generated prose" not in json.dumps(calibration.current.metadata())
    assert all(path == "/completion" and kw["deadline"] == 123 and kw["payload"]["ignore_eos"]
               and kw["payload"]["n_predict"] == 60 and not kw["payload"]["cache_prompt"] for path, kw in requests)
    assert calibration.measure() == "calibrated" and len(requests) == 3
    manager.generation = None
    assert calibration.current is None and calibration.measure() == "not_ready"
    manager.generation = 2
    assert calibration.measure() == "calibrated" and len(requests) == 6
    assert calibration.current.generation == 2


@pytest.mark.parametrize("invalid", [sample(count=59), sample(count=True), sample(rate=True), sample(rate=0),
    sample(rate=-2), sample(rate=float("nan")), sample(rate=float("inf")), {"timings": None}, {}])
def test_invalid_or_partial_measurement_never_becomes_ready_or_retries_same_instance(invalid):
    calibration, manager, requests, _operations = decoder([sample(), invalid, sample()] * 2)
    assert calibration.measure() == "decoder_calibration_invalid" and calibration.current is None
    count = len(requests)
    assert calibration.measure() == "decoder_calibration_invalid" and len(requests) == count
    manager.generation = 2
    calibration.measure()
    assert len(requests) > count


@pytest.mark.parametrize("reason", ["busy", "not_ready", "timeout", "closed"])
def test_transport_failure_cannot_publish_a_measurement(reason):
    calibration, _manager, requests, _operations = decoder([], reason=reason)
    assert calibration.measure() == reason and calibration.current is None and not requests


def test_instance_replacement_while_measuring_refuses_stale_result():
    calibration, _manager, _requests, _operations = decoder([sample()] * 3,
        after=lambda manager: setattr(manager, "generation", 2))
    assert calibration.measure() == "instance_changed" and calibration.current is None


def test_explicit_check_replaces_cached_measurement_and_can_retry_invalid_generation():
    calibration, _, requests, _ = decoder([sample(10)] * 3 + [sample(count=59)] + [sample(40)] * 3)
    assert calibration.measure() == "calibrated" and calibration.current.rates == (10, 10, 10)
    assert calibration.measure(force=True) == "decoder_calibration_invalid" and calibration.current is None
    assert calibration.measure() == "decoder_calibration_invalid" and len(requests) == 4
    assert calibration.measure(force=True) == "calibrated" and calibration.current.rates == (40, 40, 40)


def test_background_preparation_calibrates_before_priming_chat_prefix():
    prep, threads, _manager, _calls = fixture()
    order = []
    prep.client.calibrate_decoder = lambda **kw: (order.append("decoder") or CleanupReply(None, "calibrated"))
    prep.client.prepare_prompt = lambda **kw: (order.append("prefix") or CleanupReply(None, "prepared"))
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert order == ["decoder", "prefix"] and prep.ready(PromptHints(post_rules=True))


def test_failed_decoder_calibration_preserves_unprepared_state_without_a_prefix_request():
    prep, threads, _manager, calls = fixture()
    prep.client.calibrate_decoder = lambda **kw: CleanupReply(None, "decoder_calibration_invalid")
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert not calls and not prep.ready(PromptHints(post_rules=True))
    assert prep.status["reason"] == "decoder_calibration_invalid"


def test_latest_context_after_decoder_calibration_is_primed_and_shutdown_prevents_late_prefix_work():
    prep, threads, _manager, calls = fixture()
    def calibrate(**kwargs):
        prep.request(PromptHints(style="formal", post_rules=True))
        return CleanupReply(None, "calibrated")
    prep.client.calibrate_decoder = calibrate
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert len(calls) == 1 and calls[0]["style"] == "formal"
    prep, threads, _manager, calls = fixture()
    prep.client.calibrate_decoder = lambda **kw: (prep.close() or CleanupReply(None, "calibrated"))
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert not calls and prep.status["state"] == "closed"
