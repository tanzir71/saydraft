"""Synthetic report mutations exercise CI checks without claiming new native data."""

import hashlib
import json

import pytest

from tools import check_cleanup_evidence as evidence

BASE_POLICY = evidence.ROOT / "eval/cleanup/results/2026-11-12-policy-headroom/index.json"
BASE_FORCED = evidence.ROOT / "eval/cleanup/results/2026-11-13-word-guard/index.json"


def fixture(tmp_path):
    # These generated reports test the checker, never count as native evidence.
    golden = evidence.load_eval_corpus(evidence.ROOT / "tests/eval_corpus.jsonl")
    indexes = []
    for label, original in (("policy", BASE_POLICY), ("forced", BASE_FORCED)):
        folder = tmp_path / label
        folder.mkdir()
        index = json.loads(original.read_text())
        for entry in index["reports"]:
            report = json.loads((original.parent / entry["report"]).read_text())
            report["golden_sha256"] = evidence.corpus_digest(golden)
            report["suites"]["golden"].update(requested=len(golden), completed=len(golden),
                                             exact_passes=len(golden), regressions=[])
            # Synthetic source/calibration metadata is local to this test fixture.
            report["source_fingerprints"] = {name.replace("\\", "/"): hashlib.sha256((evidence.ROOT / name).read_bytes()).hexdigest()
                for name in set(report["source_fingerprints"]) | evidence.REQUIRED if (evidence.ROOT / name).exists()}
            report["prompt_sha256"] = {name: hashlib.sha256(
                (evidence.ROOT / "saydraft/cleanup/llm/prompts" / name).read_bytes()).hexdigest()
                for name in report["prompt_sha256"]}
            if label == "policy":
                rate = 30 if report["backend"] == "cpu" else 100
                report["live_decoder_calibration"] = {"tokens_per_sample": 60, "sample_count": 3,
                                                       "tokens_per_second": [rate, rate, rate]}
            content = json.dumps(report).encode()
            (folder / entry["report"]).write_bytes(content)
            entry["report_sha256"] = hashlib.sha256(content).hexdigest()
        path = folder / "index.json"
        path.write_text(json.dumps(index))
        indexes.append(path)
    return indexes


def mutate(index_path, operation, *, name=None):
    index = json.loads(index_path.read_text())
    entry = next(entry for entry in index["reports"] if entry["report"] == name) if name else index["reports"][0]
    path = index_path.parent / entry["report"]
    report = json.loads(path.read_text())
    operation(report)
    content = json.dumps(report).encode()
    path.write_bytes(content)
    entry["report_sha256"] = hashlib.sha256(content).hexdigest()
    index_path.write_text(json.dumps(index))


def test_retained_hybrid_and_forced_model_evidence_are_checked_separately(tmp_path):
    result = evidence.check(*fixture(tmp_path))
    assert result["passed"] and len(result["reports"]) == 2
    assert all(row["accepted_replies"] > 0 for row in result["reports"])
    assert "no tier/latency/default acceptance" in result["scope"]


@pytest.mark.parametrize('count', [472, 555])
def test_self_consistent_evidence_cannot_accept_a_shrunken_golden_corpus(tmp_path, monkeypatch, count):
    golden = evidence.load_eval_corpus(evidence.ROOT / 'tests/eval_corpus.jsonl')
    assert len(golden) >= 556
    monkeypatch.setattr(evidence, 'load_eval_corpus', lambda _path: golden[:count])
    policy, forced = fixture(tmp_path)
    with pytest.raises(ValueError, match='Cleanup corpus shrank'):
        evidence.check(policy, forced)


def test_forced_evidence_pins_the_pipeline_that_activates_post_rules_validation(tmp_path):
    policy, forced = fixture(tmp_path)
    mutate(forced, lambda report: report['source_fingerprints'].update({'saydraft/dictation/pipeline.py': '0' * 64}))
    with pytest.raises(ValueError, match='Stale cleanup source'):
        evidence.check(policy, forced)


@pytest.mark.parametrize("operation,reason", [
    (lambda report: report["suites"]["golden"].update(completed=431), "Incomplete suite"),
    (lambda report: report["suites"]["golden"].update(accepted_replies=0), "Rules fallback"),
    (lambda report: report["suites"]["golden"].update(exact_passes=397), "below 92%"),
    (lambda report: report["suites"]["golden"].update(preservation_failures=["fixture"]), "must-keep"),
    (lambda report: report["suites"]["golden"].update(regressions=["fixture"]), "golden regression"),
    (lambda report: report.update(quality_timeout_ms=120000), "budget changed"),
    (lambda report: report.update(native_exit_observed=[False]), "Native exit"),
    (lambda report: report.update(error_type="RuntimeError"), "Native measurement failed"),
    (lambda report: report["live_decoder_calibration"].update(tokens_per_second=[0, 24, 30]), "Invalid live decoder"),
    (lambda report: report["source_fingerprints"].update({"saydraft/cleanup/llm/client.py": "0" * 64}), "Stale cleanup"),
    (lambda report: report["source_fingerprints"].pop("saydraft/cleanup/styles.py"), "Missing evidence source"),
    (lambda report: report["prompt_sha256"].update({"system.txt": "0" * 64}), "Stale cleanup prompts"),
    (lambda report: report["source_fingerprints"].update({"saydraft/cleanup/../../../outside.py": "0" * 64}), "Unsafe evidence"),
])
def test_semantically_invalid_evidence_fails_even_with_a_matching_file_digest(tmp_path, operation, reason):
    policy, forced = fixture(tmp_path)
    mutate(policy, operation)
    with pytest.raises(ValueError, match=reason):
        evidence.check(policy, forced)


def test_skipped_adversarial_inputs_cannot_replace_forced_generation_proof(tmp_path):
    policy, forced = fixture(tmp_path)
    mutate(forced, lambda report: report["suites"]["adversarial"].update(client_replies_with_token_counts=0))
    with pytest.raises(ValueError, match="Adversarial fallback"):
        evidence.check(policy, forced)


def test_native_report_bytes_are_immutable_even_when_json_meaning_is_unchanged(tmp_path):
    policy, forced = fixture(tmp_path)
    path = policy.parent / "qwen08-cpu.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="report bytes changed"):
        evidence.check(policy, forced)


def test_source_comparison_accepts_only_line_ending_variants(tmp_path):
    path = tmp_path / "source.py"
    path.write_bytes(b"value = 1\n")
    assert evidence.source_matches(path, hashlib.sha256(b"value = 1\r\n").hexdigest())
    assert not evidence.source_matches(path, hashlib.sha256(b"value = 2\n").hexdigest())


def test_quality_pass_does_not_promote_a_below_threshold_hardware_measurement(tmp_path):
    policy, forced = fixture(tmp_path)
    mutate(policy, lambda report: report["live_decoder_calibration"].update(tokens_per_second=[23, 24, 24]))
    result = evidence.check(policy, forced)
    assert result["passed"] and result["reports"][0]["rate_target_met"] is False
    assert result["reports"][0]["decoder_median_tps"] == 24


def test_forced_golden_regression_cannot_hide_behind_passing_policy_output(tmp_path):
    policy, forced = fixture(tmp_path)
    mutate(forced, lambda report: report["suites"]["golden"].update(
        exact_passes=555, regressions=["balanced-chat-05"]), name="qwen08-cpu.json")
    with pytest.raises(ValueError, match="golden regression"):
        evidence.check(policy, forced)
    report = evidence.assess(policy, forced)
    assert not report["passed"] and not report["quality_passed"]
    failed = next(row for row in report["reports"] if row["mode"] == "forced" and row["backend"] == "cpu")
    assert failed["evidence_valid"] and failed["golden_regressions"] == ["balanced-chat-05"]
    assert all(row["quality_passed"] for row in report["reports"] if row["mode"] == "policy")


def test_cli_reports_all_stages_and_fails_for_cpu_speed_even_if_quality_passes(tmp_path, capsys):
    policy, forced = fixture(tmp_path)
    mutate(policy, lambda report: report["live_decoder_calibration"].update(tokens_per_second=[23, 24, 24]))
    assert evidence.main(["--policy-index", str(policy), "--forced-index", str(forced)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["evidence_valid"] and report["quality_passed"] and not report["performance_passed"]
    assert not report["passed"] and len(report["reports"]) == 4


def test_rules_only_output_and_forced_regression_are_both_visible(tmp_path):
    policy, forced = fixture(tmp_path)
    mutate(policy, lambda report: report["suites"]["golden"].update(accepted_replies=0))
    mutate(forced, lambda report: report["suites"]["golden"].update(regressions=["fixture"]))
    report = evidence.assess(policy, forced)
    assert report["evidence_valid"] and len(report["reports"]) == 4
    failures = [row for row in report["reports"] if not row["quality_passed"]]
    assert {row["mode"] for row in failures} == {"forced", "policy"}


def test_invalid_source_cannot_supply_passed_quality_or_speed_metrics(tmp_path):
    policy, forced = fixture(tmp_path)
    mutate(policy, lambda report: report["source_fingerprints"].update({"saydraft/cleanup/llm/client.py": "0" * 64}))
    row = evidence.assess(policy, forced)["reports"][0]
    assert not row["evidence_valid"] and not row["passed"]
    assert "Stale cleanup" in row["reason"] and "decoder_median_tps" not in row


@pytest.mark.parametrize("change", [
    {"valid": False}, {"tokens": 59}, {"tokens_per_second": float("nan")},
    {"tokens_per_second": True}, {"reason": "timeout"},
])
def test_forced_decoder_samples_must_be_three_complete_sixty_token_generations(tmp_path, change):
    policy, forced = fixture(tmp_path)
    mutate(forced, lambda report: report["throughput_60_tokens"][0].update(change), name="qwen08-cpu.json")
    # NaN is rejected by the strict JSON loader before stage assessment.
    if any(isinstance(value, float) and value != value for value in change.values()):
        with pytest.raises(ValueError, match="Nonfinite"):
            evidence.assess(policy, forced)
    else:
        row = next(row for row in evidence.assess(policy, forced)["reports"]
                   if row["backend"] == "cpu" and row["mode"] == "forced")
        assert not row["evidence_valid"] and not row["passed"]
