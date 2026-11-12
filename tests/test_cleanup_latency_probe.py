import pytest

from tools import probe_cleanup_latency as probe


def rows(count=20, seconds=.5):
    return [{"audio_seconds": duration, "seconds": seconds, "decision": "accepted"}
            for duration in (3, 8, 20) for _ in range(count)]


def test_latency_summary_requires_twenty_samples_in_each_duration_group():
    assert not probe.summary(rows(19), "rules")["targets_met"]
    result = probe.summary(rows(), "rules")
    assert result["targets_met"] and result["accepted_replies"] == 60
    assert result["groups"]["20"]["n"] == 20


def test_tail_latency_detects_two_slow_replies_without_hiding_them_in_the_median():
    samples = rows(seconds=.9)
    samples[-2]["seconds"] = samples[-1]["seconds"] = 2.1
    result = probe.summary(samples, "llm")
    assert result["groups"]["20"]["p50_seconds"] == .9
    assert result["groups"]["20"]["p95_seconds"] == 2.1
    assert not result["targets_met"]


def test_rules_and_llm_use_their_written_latency_targets_and_keep_decision_counts():
    samples = rows(seconds=.9)
    samples[0]["decision"] = "skip_budget"
    assert not probe.summary(samples, "rules")["targets_met"]
    result = probe.summary(samples, "llm")
    assert result["targets_met"] and result["accepted_replies"] == 59
    assert result["groups"]["3"]["decisions"]["skip_budget"] == 1


def test_latency_probe_refuses_dirty_source_before_creating_artifacts_or_loading_asr(monkeypatch, tmp_path):
    monkeypatch.setattr(probe.subprocess, "check_output", lambda *a, **kw: " M saydraft/app.py")
    target = tmp_path / "not-created"
    with pytest.raises(SystemExit) as error:
        probe.main(["--parakeet-dir", "unused", "--lid-dir", "unused", "--output", str(target), "--mode", "rules"])
    assert error.value.code == 2 and not target.exists()
