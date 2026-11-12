import pytest

from saydraft.cleanup.llm.bakeoff import ObservedCleaner, measure_cases, summarize
from saydraft.eval import EvalCase
from tools.bench_cleanup import policy_complete, prepare_policy_case
from tests.test_cleanup_bakeoff import fixtures, pipeline_for
from tests.test_cleanup_gate import prepared_pipeline


def test_policy_setup_is_reported_separately_from_actual_model_measurement():
    pipeline, observer = pipeline_for(reason="timeout")
    golden, adversarial = fixtures()
    prepared = []

    def setup(case):
        prepared.append(case.id)
        return {"prepared": True, "seconds": 3}

    rows = list(measure_cases(golden, adversarial, pipeline, observer, prepare_case=setup))
    assert prepared == ["gold", "adv"]
    assert all(row["policy_preparation"]["seconds"] == 3 for row in rows)
    assert all(row["seconds"] < 1 for row in rows)
    report = summarize(rows, requested_golden=1, requested_adversarial=1)
    assert policy_complete(rows, 1, 1) and not report["measurement_complete"]
    assert report["suites"]["golden"]["accepted_replies"] == 0
    assert report["suites"]["golden"]["client_replies_with_token_counts"] == 0
    assert not policy_complete(rows[:1], 1, 1)
    assert not policy_complete(rows, 2, 0)
    rows[1].pop("policy_preparation")
    assert not policy_complete(rows, 1, 1)


def test_policy_observer_retains_original_cues_and_metadata_for_skips():
    pipeline, _model, local, *_ = prepared_pipeline()
    observer = ObservedCleaner(lambda factory: local)
    pipeline.llm = observer
    cases = [EvalCase("high", "um hello", "Hello", "balanced", "general"),
             EvalCase("low", "hello", "Hello", "balanced", "general")]
    rows = list(measure_cases(cases, [], pipeline, observer))
    assert rows[0]["decision"] == "accepted" and rows[0]["calls"][0]["gate"]["need_score"] == 2
    assert rows[1]["decision"] == "skip_low_need" and rows[1]["calls"][0]["gate"]["need_score"] == 0
    assert "client_reason" not in rows[1]["calls"][0]  # No stale generated reply from the prior case.


def test_failed_policy_setup_stops_before_counting_unprepared_cases():
    pipeline, observer = pipeline_for()

    def unavailable(case):
        raise RuntimeError("not prepared")

    with pytest.raises(RuntimeError, match="not prepared"):
        list(measure_cases(*fixtures(), pipeline, observer, prepare_case=unavailable))
    assert not observer.calls


@pytest.mark.parametrize("mode,profile,group", [("raw", "general", "general"),
    ("balanced", "code/comments", "general"), ("balanced", "general", "code")])
def test_policy_setup_never_constructs_a_model_for_prose_bypass(mode, profile, group):
    case = EvalCase("bypass", "words", "words", mode, profile, app_group=group)
    assert prepare_policy_case(case, None) == {"bypassed": True}


@pytest.mark.parametrize("extra", [["--timeout-ms", "120000"], ["--throughput-repeats", "4"]])
def test_policy_cli_cannot_raise_the_production_budget_or_change_calibration(extra):
    from tools import bench_cleanup
    with pytest.raises(SystemExit) as error:
        bench_cleanup.main(["--candidate", "unused", "--models-dir", "unused", "--runtime-dir", "unused",
                            "--output", "unused", "--interactive-policy", *extra])
    assert error.value.code == 2
