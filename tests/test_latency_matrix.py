import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import bench, latency_matrix as matrix
from tools.latency_trial import CheckedDelivery


def cases(*, seconds=.2, decision="accepted", count=20):
    return [{"phase": phase, "audio_seconds": duration, "release_to_paste_seconds": seconds,
             "decision": decision} for phase in matrix.PHASES for duration in matrix.DURATIONS
            for _ in range(count)]


def pair():
    return {"complete": True, "git_commit": "source", "audio_seconds": 3, "repeat": 0,
        "native_exits": [True], "cases": [{"phase": phase, "audio_seconds": 3, "repeat": 0,
            "history_before_paste": True, "clipboard_restored": True, "release_deadline_present": True,
            "no_early_delivery": True, "fed_samples": 48000} for phase in matrix.PHASES]}


def test_matrix_requires_twenty_independent_samples_in_every_phase_and_duration():
    assert matrix.summarize(cases(), "pro")["latency_targets_met"]
    assert not matrix.summarize(cases(count=19), "pro")["latency_targets_met"]
    assert not matrix.summarize([row for row in cases() if row["phase"] != "cold"], "pro")["latency_targets_met"]
    assert not matrix.summarize([row for row in cases() if row["audio_seconds"] != 90], "pro")["latency_targets_met"]


def test_matrix_uses_nearest_rank_and_exposes_tail_and_distinct_thresholds():
    rows = cases(seconds=.7)
    assert matrix.summarize(rows, "pro")["latency_targets_met"]
    assert not matrix.summarize(rows, "lite")["latency_targets_met"]
    rows[18]["release_to_paste_seconds"] = 2.1
    rows[19]["release_to_paste_seconds"] = 2.2
    result = matrix.summarize(rows, "pro")
    assert not result["latency_targets_met"]
    assert result["groups"]["cold-3"]["p50_seconds"] == .7
    assert result["groups"]["cold-3"]["p95_seconds"] == 2.1
    assert result["groups"]["cold-3"]["max_seconds"] == 2.2


@pytest.mark.parametrize("invalid", [-1, float("nan"), float("inf")])
def test_matrix_refuses_invalid_measurements(invalid):
    with pytest.raises(ValueError):
        matrix.summarize(cases(seconds=invalid), "pro")


def test_rules_fallback_cannot_earn_model_use_in_either_phase():
    rows = cases(decision="skip_budget")
    assert not matrix.summarize(rows, "standard")["actual_model_use"]
    rows[0]["decision"] = "accepted"
    assert not matrix.summarize(rows, "standard")["actual_model_use"]
    rows[-1]["decision"] = "accepted"
    result = matrix.summarize(rows, "standard")
    assert result["actual_model_use"]
    assert result["accepted_by_phase"] == {"cold": 1, "warm": 1}
    assert result["groups"]["cold-10"]["decisions"] == {"skip_budget": 20}


@pytest.mark.parametrize("change", [
    {"complete": False}, {"git_commit": "other"}, {"repeat": 1}, {"audio_seconds": 10},
    {"native_exits": [False]}, {"native_exits": [1]}, {"cases": []},
])
def test_parent_rejects_incomplete_or_mismatched_child_receipts(change):
    value = {**pair(), **change}
    with pytest.raises(ValueError):
        matrix.validate_pair(value, seconds=3, repeat=0, commit="source")


@pytest.mark.parametrize("field,value", [("phase", "cold"), ("fed_samples", 47999),
    ("history_before_paste", False), ("clipboard_restored", False),
    ("release_deadline_present", False), ("no_early_delivery", False)])
def test_parent_checks_both_cases(field, value):
    receipt = pair()
    receipt["cases"][1][field] = value
    with pytest.raises(ValueError):
        matrix.validate_pair(receipt, seconds=3, repeat=0, commit="source")


def test_checked_delivery_times_only_the_current_durable_paste():
    row = SimpleNamespace(id=1, raw_text="public fixture", cleaned_text="Fixture.")
    history = SimpleNamespace(list_recent=lambda **kw: [row])
    delivery = CheckedDelivery(history, clock=lambda: 12)
    delivery.begin(1)
    delivery.clipboard.copy(row.cleaned_text)
    with pytest.raises(RuntimeError):
        delivery.before_paste("ctrl+v")
    delivery.released_at = 11.5
    row.id = 2
    with pytest.raises(RuntimeError):
        delivery.before_paste("ctrl+v")
    row.id = 1
    delivery.before_paste("ctrl+v")
    assert delivery.pasted_at - delivery.released_at == .5
    with pytest.raises(RuntimeError):
        delivery.before_paste("ctrl+v")


def test_child_environment_has_private_cache_and_no_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-inherit")
    monkeypatch.setenv("HTTPS_PROXY", "do-not-inherit")
    environment = matrix.child_environment(tmp_path)
    assert "OPENAI_API_KEY" not in environment and "HTTPS_PROXY" not in environment
    assert environment["HF_HUB_OFFLINE"] == "1"
    assert Path(environment["LOCALAPPDATA"]).is_relative_to(tmp_path)
    assert Path(environment["TEMP"]).is_dir()


@pytest.mark.parametrize("code", [0, 1])
def test_parent_waits_for_one_child_and_closes_job_on_success_or_failure(tmp_path, code):
    processes = []

    class Process:
        def __init__(self, argv, **kwargs):
            processes.append(self)
            self.closed = False
            assert kwargs["capture_output"] and kwargs["max_output_bytes"] == 65536
            assert argv[1:3] == ["-m", "tools.latency_trial"]
            matrix.write_json(tmp_path / "report.json", pair())

        def poll(self):
            return code

        def read_output(self, timeout):
            return b"private native output"

        def close(self):
            self.closed = True

    if code:
        with pytest.raises(RuntimeError):
            matrix.run_pair({"audio_seconds": 3}, tmp_path, process_factory=Process)
    else:
        assert matrix.run_pair({"audio_seconds": 3}, tmp_path, process_factory=Process) == pair()
    assert len(processes) == 1 and processes[0].closed
    assert "private native output" not in (tmp_path / "process.json").read_text()


def test_bench_matrix_dispatch_preserves_legacy_cli(monkeypatch):
    monkeypatch.setattr(matrix, "main", lambda argv: 7 if argv == ["--help"] else 9)
    assert bench.main(["matrix", "--help"]) == 7


def test_dirty_source_is_rejected_before_artifacts_or_child_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix, "source_receipt", lambda: {"source_dirty": True})
    monkeypatch.setattr(matrix, "os", SimpleNamespace(name="nt"))
    output = tmp_path / "new"
    with pytest.raises(SystemExit) as caught:
        matrix.main(["--tier", "lite", "--parakeet-dir", str(tmp_path), "--lid-dir", str(tmp_path),
                     "--vad-dir", str(tmp_path), "--isolated", "--output", str(output)])
    assert caught.value.code == 2 and not output.exists()


def test_debug_completion_keeps_full_matrix_and_target_false(tmp_path, monkeypatch):
    source = {"source_dirty": False, "git_commit": "source", "source_fingerprints": {}}
    monkeypatch.setattr(matrix, "source_receipt", lambda: copy.deepcopy(source))
    monkeypatch.setattr(matrix, "os", SimpleNamespace(name="nt"))

    def run(spec, output):
        receipt = pair()
        receipt["cases"] = [{**row, "release_to_paste_seconds": .1, "decision": "disabled"}
                            for row in receipt["cases"]]
        matrix.write_json(output / "report.json", receipt)
        return receipt

    monkeypatch.setattr(matrix, "run_pair", run)
    output = tmp_path / "new"
    assert matrix.main(["--tier", "lite", "--parakeet-dir", str(tmp_path), "--lid-dir", str(tmp_path),
        "--output", str(output), "--debug", "--repeats", "1", "--durations", "3"]) == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["complete"] and not report["full_matrix"] and not report["latency_target_met"]


@pytest.mark.parametrize("change,latency_ok,recipe_ok", [
    ("none", True, True), ("source", False, False), ("rules_only", False, False),
    ("slow_decoder", True, False),
])
def test_full_measurement_separates_latency_model_use_decoder_and_source_integrity(
        tmp_path, monkeypatch, change, latency_ok, recipe_ok):
    # CI keeps pytest's basetemp inside its checkout. These synthetic reports
    # belong outside the synthetic immutable source, regardless of that layout.
    monkeypatch.setattr(matrix, "ROOT", tmp_path / "immutable-source")
    source = {"source_dirty": False, "git_commit": "source", "source_fingerprints": {"worker.py": "before"}}
    reads = 0

    def receipt():
        nonlocal reads
        reads += 1
        return {**source, "source_fingerprints": {"worker.py": "after"}} if change == "source" and reads > 1 else source

    monkeypatch.setattr(matrix, "source_receipt", receipt)
    monkeypatch.setattr(matrix, "os", SimpleNamespace(name="nt"))

    def run(spec, output):
        value = pair()
        value.update(audio_seconds=spec["audio_seconds"], repeat=spec["repeat"])
        value["cases"] = [{**row, "audio_seconds": spec["audio_seconds"], "repeat": spec["repeat"],
            "fed_samples": spec["audio_seconds"] * 16000, "release_to_paste_seconds": .2,
            "decision": "skip_budget" if change == "rules_only" else "accepted",
            "cleanup_at_release": {"decoder": {"median_tps": 20 if change == "slow_decoder" else 30}}}
            for row in value["cases"]]
        matrix.write_json(output / "report.json", value)
        return value

    monkeypatch.setattr(matrix, "run_pair", run)
    output = tmp_path / "new"
    assert matrix.main(["--tier", "standard", "--parakeet-dir", str(tmp_path), "--lid-dir", str(tmp_path),
        "--vad-dir", str(tmp_path), "--models-dir", str(tmp_path), "--runtime-dir", str(tmp_path),
        "--output", str(output), "--isolated"]) == 0
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["complete"] and len(report["cases"]) == 160
    assert report["latency_target_met"] is latency_ok
    assert report["tier_recipe_target_met"] is recipe_ok


def test_full_run_refuses_artifacts_inside_source_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix, "ROOT", tmp_path)
    monkeypatch.setattr(matrix, "source_receipt", lambda: {"source_dirty": False})
    monkeypatch.setattr(matrix, "os", SimpleNamespace(name="nt"))
    output = tmp_path / "new"
    with pytest.raises(SystemExit) as caught:
        matrix.main(["--tier", "lite", "--parakeet-dir", str(tmp_path), "--lid-dir", str(tmp_path),
                     "--vad-dir", str(tmp_path), "--isolated", "--output", str(output)])
    assert caught.value.code == 2 and not output.exists()
