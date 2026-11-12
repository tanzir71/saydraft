import logging
import json
import re
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.calibration import DecodeMeasurement
from saydraft.cleanup.llm.client import CleanupClient
from saydraft.cleanup.llm.gate import NeedScore, predict, request_timeout, score_need
from saydraft.cleanup.llm.prompts import PromptHints
from saydraft.cleanup.llm.sidecar import SidecarReply
from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.insert.inserter import InsertionResult
from tests.test_cleanup_streaming import DONE, FakeModel, frame


@pytest.mark.parametrize("text,style,intensity,score", [
    ("hello comma world", "neutral", 3, 0), ("hello team", "formal", 3, 1),
    ("um hello", "neutral", 3, 2), ("send it actually keep it", "neutral", 3, 2),
    ("next item apples", "neutral", 3, 2), ("hello", "neutral", 4, 2),
    ("word " * 26, "neutral", 3, 2), ("বাংলা " * 26, "neutral", 3, 2),
])
def test_need_score_uses_written_cues_without_rewriting_words(text, style, intensity, score):
    assert score_need(text, style=style, intensity=intensity).score == score


def test_timeout_reserves_fifty_ms_and_refuses_expired_or_invalid_budgets():
    assert request_timeout(800, now=100) == .75
    assert request_timeout(800, now=100, deadline=100.3) == pytest.approx(.25)
    assert request_timeout(800, now=100, deadline=100.04) == 0
    assert request_timeout(800, now=100, deadline=float("nan")) == 0


def test_prediction_uses_live_rate_output_length_and_uncached_prefix_cost():
    need = NeedScore(2, ("polished",))
    fast = predict(need, source_tokens=10, pending_tokens=20, output_limit=256, rate=100, remaining=.75)
    slow = predict(need, source_tokens=10, pending_tokens=20, output_limit=256, rate=10, remaining=.75)
    assert fast["reason"] == "call" and fast["predicted_ms"] == 400
    assert slow["reason"] == "skip_budget" and slow["predicted_ms"] == 4000
    assert predict(need, source_tokens=10, pending_tokens=20, output_limit=256,
                   rate=None, remaining=.75)["reason"] == "skip_calibration"


def prepared_pipeline(rate=200):
    clock = SimpleNamespace(now=100.0)
    invalidations, timeouts = [], []

    class Model(FakeModel):
        def __init__(self):
            super().__init__([frame("Hello", finish="stop"), DONE])
            self.vocabulary, self.delay = {}, 0

        def request_json(self, path, **kwargs):
            self.requests.append((path, kwargs))
            clock.now += self.delay
            values = re.findall(r"\w+|[^\w\s]", kwargs["payload"]["content"])
            return {"tokens": [self.vocabulary.setdefault(value, len(self.vocabulary)) for value in values]}

    model = Model()
    manager = SimpleNamespace(generation=1)
    def run(operation, *, timeout):
        timeouts.append(timeout)
        result = operation(model, clock.now + timeout)
        return SidecarReply(result, "ok")
    manager.run = run
    client = CleanupClient(manager, clock=lambda: clock.now)
    client.decoder._measurement = DecodeMeasurement(1, (rate, rate, rate))
    assert client.prepare_prompt().reason == "prepared"
    cfg = LocalLLMConfig(enabled=True, model_path="unit-fixture-not-a-real-model")
    local = LocalLLMCleaner(cfg, manager_factory=lambda cfg: manager,
        client_factory=lambda *a, **kw: client, clock=lambda: clock.now)
    local._get_client()
    local._preparation = SimpleNamespace(ready=lambda hints: True,
        request=lambda hints: invalidations.append("request"), invalidate=lambda: invalidations.append("invalidate"))
    model.requests.clear()
    timeouts.clear()
    return DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=local), model, local, client, clock, timeouts, invalidations


def generation_requests(model):
    return [request for path, request in model.requests if path == "/v1/chat/completions"]


def test_low_need_keeps_rules_without_tokenization_and_logs_no_dictation(caplog):
    pipeline, model, local, *_ = prepared_pipeline()
    with caplog.at_level(logging.INFO, logger="saydraft.dictation.llm_local"):
        assert pipeline.process_transcript("hello comma world", DictationContext()) == "Hello comma world"
    assert pipeline.last_llm_decision == "skip_low_need" and not model.requests
    assert local.last_gate_info["need_score"] == 0 and "hello comma world" not in caplog.text


def test_original_filler_cue_survives_rules_and_a_fitting_generation_is_accepted():
    pipeline, model, local, _client, _clock, timeouts, _invalidations = prepared_pipeline()
    assert pipeline.process_transcript("um hello", DictationContext()) == "Hello"
    assert pipeline.last_llm_decision == "accepted" and len(generation_requests(model)) == 1
    assert timeouts == [.75] and local.last_gate_info["need_reasons"] == ["fillers"]


def test_slow_budget_skip_uses_no_generation_and_receives_no_generation_token_credit():
    pipeline, model, local, client, *_ = prepared_pipeline(rate=1)
    assert pipeline.process_transcript("um hello", DictationContext()) == "Hello"
    assert pipeline.last_llm_decision == "skip_budget" and not generation_requests(model)
    reply = client.clean("Hello", hints=PromptHints(post_rules=True), gate=NeedScore(2, ("fillers",)))
    assert reply.reason == "skip_budget" and reply.input_tokens == reply.output_limit == 0
    assert local.last_gate_info["predicted_ms"] > local.last_gate_info["remaining_ms"]


def test_tokenization_time_is_charged_before_the_generation_fit_check():
    pipeline, model, _local, _client, _clock, _timeouts, _invalidations = prepared_pipeline(rate=50)
    model.delay = .3
    assert pipeline.process_transcript("um hello", DictationContext()) == "Hello"
    assert pipeline.last_llm_decision == "skip_budget" and not generation_requests(model)


def test_unknown_prefix_defers_generation_and_requests_background_repreparation():
    pipeline, model, _local, client, _clock, _timeouts, invalidations = prepared_pipeline()
    client._prefix = None
    pipeline.process_transcript("um hello", DictationContext())
    assert pipeline.last_llm_decision == "skip_unprepared_prefix" and not generation_requests(model)
    assert invalidations == ["invalidate", "request"]


def test_history_persists_gate_decision_and_rules_before_simulated_insertion():
    pipeline, model, *_ = prepared_pipeline()
    events, rows = [], []
    def append(row):
        rows.append(row)
        events.append("history")
        return 1
    processor = TranscriptProcessor(cleaner=pipeline, formatter=IdentityFormatter(),
        history=SimpleNamespace(append=append), inserter=SimpleNamespace(insert_text=lambda *a, **kw: (
            events.append("insert") or InsertionResult("inserted", "fixture"))))
    result = processor.process("hello comma world", context=DictationContext(),
        target=TargetContext("fixture", ""), model="fixture")
    assert rows[0].llm_decision == "skip_low_need" and rows[0].cleaned_text == result.cleaned_text
    assert events == ["history", "insert"] and not generation_requests(model)


def test_low_need_does_not_construct_any_model_when_called_without_worker_warmup():
    local = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path="unused"),
        manager_factory=lambda cfg: pytest.fail("low need must not construct a model"))
    assert local.clean_after_rules("Hello", raw_text="hello", context=DictationContext()) == (None, "skip_low_need")


def test_expired_outer_budget_refuses_even_high_need_without_constructing_a_model():
    context = DictationContext(cleanup_deadline=100.04)
    local = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path="unused"), clock=lambda: 100,
        manager_factory=lambda cfg: pytest.fail("expired budget must not construct a model"))
    assert local.clean_after_rules("Hello", raw_text="um hello", context=context) == (None, "skip_budget")


def test_outer_deadline_shortens_the_shared_transport_deadline():
    _pipeline, model, local, _client, clock, timeouts, _invalidations = prepared_pipeline()
    context = DictationContext(cleanup_deadline=clock.now + .3)
    assert local.clean_after_rules("Hello", raw_text="um hello", context=context) == ("Hello", "ok")
    assert timeouts == [pytest.approx(.25)] and len(generation_requests(model)) == 1


def test_ungated_request_invalidates_unknown_cache_before_a_later_gated_request():
    _pipeline, model, _local, client, *_ = prepared_pipeline()
    assert client.clean("Hello", hints=PromptHints(post_rules=True)).reason == "ok"
    model.requests.clear()
    reply = client.clean("Hello", hints=PromptHints(post_rules=True), gate=NeedScore(2, ("fillers",)))
    assert reply.reason == "skip_unprepared_prefix" and not generation_requests(model)


def test_prompt_assembly_cannot_reset_the_absolute_budget(monkeypatch):
    from saydraft.cleanup.llm import client as client_module
    _pipeline, model, local, _client, clock, timeouts, _invalidations = prepared_pipeline()
    original = client_module.build_messages
    def delayed(*args, **kwargs):
        clock.now += .4
        return original(*args, **kwargs)
    monkeypatch.setattr(client_module, "build_messages", delayed)
    context = DictationContext(cleanup_deadline=clock.now + .3)
    assert local.clean_after_rules("Hello", raw_text="um hello", context=context) == (None, "skip_budget")
    assert not model.requests and not timeouts


def test_standalone_deadline_without_need_metadata_can_expire_without_a_request():
    _pipeline, model, _local, client, clock, timeouts, _invalidations = prepared_pipeline()
    assert client.clean("Hello", stop_at=clock.now - 1).reason == "skip_budget"
    assert not model.requests and not timeouts


def test_extreme_positive_rate_cannot_put_infinity_into_gate_metadata():
    info = predict(NeedScore(2, ("long",)), source_tokens=100, pending_tokens=100,
                   output_limit=256, rate=1e-320, remaining=.75)
    assert info["reason"] == "skip_budget"
    json.dumps(info, allow_nan=False)


def test_prediction_headroom_declines_short_cpu_work_that_the_raw_estimate_admitted():
    info = predict(NeedScore(2, ("polished",)), source_tokens=5, pending_tokens=21,
                   output_limit=256, rate=27.8, remaining=.719)
    assert info["reason"] == "skip_budget" and info["predicted_ms"] > 1000


def test_failed_generation_retains_the_plan_without_claiming_complete_token_evidence():
    _pipeline, _model, local, client, *_ = prepared_pipeline()
    run = client.manager.run
    def failed(operation, *, timeout):
        run(operation, timeout=timeout)
        return SidecarReply(None, "timeout")
    client.manager.run = failed
    assert local.clean_after_rules("Hello", raw_text="um hello", context=DictationContext()) == (None, "timeout")
    assert local.last_gate_info["reason"] == "call" and local.last_gate_info["outcome"] == "timeout"
    assert local.last_gate_info["predicted_ms"] > 0
    reply = client.clean("Hello", hints=PromptHints(post_rules=True), gate=NeedScore(2, ("fillers",)))
    assert reply.reason == "timeout" and reply.input_tokens == reply.output_limit == 0


def test_busy_transport_still_records_need_and_outcome_without_generation_evidence():
    _pipeline, model, local, client, *_ = prepared_pipeline()
    client.manager.run = lambda operation, timeout: SidecarReply(None, "busy")
    assert local.clean_after_rules("Hello", raw_text="um hello", context=DictationContext()) == (None, "busy")
    assert local.last_gate_info["need_score"] == 2 and local.last_gate_info["outcome"] == "busy"
    assert local.last_gate_info["source_tokens"] == 0 and not model.requests
