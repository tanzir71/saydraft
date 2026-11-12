import json
import time
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.bakeoff import ObservedCleaner, corpus_digest, measure_cases, summarize
from saydraft.cleanup.llm.sidecar import SidecarReply
from saydraft.dictation import DictationConfig, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.eval import EvalCase
from tests.test_cleanup_streaming import DONE, FakeModel, frame


def pipeline_for(output="Send 2 files", reason="ok"):
    model = FakeModel([frame(output, finish="stop"), DONE])
    manager = SimpleNamespace(close=lambda: None, run=lambda operation, timeout: (
        SidecarReply(operation(model, time.monotonic() + timeout), "ok") if reason == "ok" else SidecarReply(None, reason)))
    cfg = LocalLLMConfig(enabled=True, model_path="unit-fixture-not-a-real-model", prepare_prompt=False)
    observer = ObservedCleaner(lambda factory: LocalLLMCleaner(cfg, manager_factory=lambda config: manager,
                                                             client_factory=factory))
    return DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=observer), observer


def fixtures():
    return [EvalCase("gold", "send 2 files", "Send 2 files", "balanced", "general")], [
        {"id": "adv", "input": "Send 2 files", "candidate": "Send 3 files", "category": "numbers"}]


@pytest.mark.parametrize("output,decision,exact,accepted", [
    ("Send 2 files", "accepted", True, 1),
    ("Send 2 files.", "accepted", False, 0),
    ("Send 3 files", "rejected:numbers_changed", True, 0),
])
def test_strict_output_and_model_use_do_not_confuse_fallback_with_model_quality(output, decision, exact, accepted):
    pipeline, observer = pipeline_for(output)
    golden, adversarial = fixtures()
    rows = list(measure_cases(golden, adversarial, pipeline, observer))
    report = summarize(rows, requested_golden=1, requested_adversarial=1)
    assert rows[0]["exact_pass"] == exact and rows[0]["decision"] == decision
    assert rows[0]["preservation_ok"]
    assert report["suites"]["golden"]["accepted_exact_passes"] == accepted
    assert report["suites"]["golden"]["client_replies_with_token_counts"] == 1
    assert report["measurement_complete"] and not report["selection_performed"]
    if "rejected" in decision:
        assert report["suites"]["golden"]["fallback_exact_passes"] == 1
    serialized = json.dumps(rows)
    assert output not in serialized and '"input"' not in serialized


def test_all_timeout_fallback_can_pass_app_goldens_without_completing_a_model_measurement():
    pipeline, observer = pipeline_for(reason="timeout")
    golden, adversarial = fixtures()
    rows = list(measure_cases(golden, adversarial, pipeline, observer))
    report = summarize(rows, requested_golden=1, requested_adversarial=1)
    assert report["suites"]["golden"]["exact_rate"] == 100
    assert report["suites"]["golden"]["accepted_exact_rate"] == 0
    assert not report["measurement_complete"] and not report["selection_performed"]


def test_sidecar_failure_stops_before_fallback_only_followup_and_retains_yielded_evidence():
    pipeline, observer = pipeline_for()
    golden, adversarial = fixtures()
    checks = iter((True, False))
    results = measure_cases(golden, adversarial, pipeline, observer, ready=lambda: next(checks))
    assert next(results)["id"] == "gold"
    with pytest.raises(RuntimeError, match="stopped before counting"):
        next(results)
    assert pipeline.glossary.protected_terms == ()


def test_actual_action_and_snippet_processing_and_raw_bypass_are_measured():
    pipeline, observer = pipeline_for("Hello")
    cases = [EvalCase("command", "sig press enter", "Hello", "balanced", "general", voice_enter_enabled=True,
                     expected_enter=True, snippets=(("sig", "Hello"),)),
             EvalCase("raw", "keep this", "keep this", "raw", "general")]
    # The model's replacement loses the protected snippet token, so real client
    # refusal falls back to the safe expansion while retaining source-only Enter.
    rows = list(measure_cases(cases, [], pipeline, observer, include_text=True))
    assert rows[0]["exact_pass"] and rows[0]["enter_sent"] and rows[0]["decision"] == "protected_changed"
    assert rows[1]["decision"] == "bypassed" and not rows[1]["calls"]
    assert rows[1]["actual"] == "keep this"
    assert not summarize(rows, requested_golden=2, requested_adversarial=0)["measurement_complete"]


def test_fingerprints_include_source_context_and_action_configuration():
    from dataclasses import replace
    case = fixtures()[0][0]
    assert corpus_digest([case]) == corpus_digest([case])
    assert corpus_digest([case]) != corpus_digest([replace(case, voice_enter_enabled=True)])
    assert not summarize([], requested_golden=0, requested_adversarial=0)["measurement_complete"]


@pytest.mark.parametrize("tokens,tps,valid", [(60, 25.0, True), (59, 25.0, False), (60, None, False), (60, float("nan"), False)])
def test_generation_throughput_requires_exactly_sixty_tokens_and_a_finite_rate(tokens, tps, valid):
    from tools.bench_cleanup import throughput
    client = SimpleNamespace(request_json=lambda *a, **kw: {"timings": {"predicted_n": tokens, "predicted_per_second": tps}})
    manager = SimpleNamespace(run=lambda operation, timeout: SidecarReply(operation(client, 100), "ok"))
    assert throughput(manager, 1, 30)[0]["valid"] == valid


def test_full_run_refuses_dirty_source_before_resolving_or_loading_a_model(monkeypatch):
    from tools import bench_cleanup
    monkeypatch.setattr(bench_cleanup.subprocess, "check_output", lambda *a, **kw: " M saydraft/app.py\n")
    monkeypatch.setattr(bench_cleanup, "get_candidate", lambda name: pytest.fail("model must not be resolved"))
    with pytest.raises(SystemExit) as error:
        bench_cleanup.main(["--candidate", "unused", "--models-dir", "unused", "--runtime-dir", "unused",
                            "--output", "unused"])
    assert error.value.code == 2
