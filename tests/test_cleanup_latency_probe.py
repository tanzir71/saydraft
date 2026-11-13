import pytest
import numpy as np
from types import SimpleNamespace

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


def test_streaming_feed_preserves_every_sample_and_real_audio_cadence():
    now, chunks = [10.0], []
    capture = SimpleNamespace(audio=np.arange(3300, dtype=np.float32), sample_rate=16000,
        chunk_callback=lambda chunk: chunks.append((now[0], chunk.copy())))
    probe.feed_capture(capture, clock=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
    np.testing.assert_array_equal(np.concatenate([chunk for _, chunk in chunks]), capture.audio)
    assert [stamp for stamp, _ in chunks] == pytest.approx([10, 10.1, 10.2])
    assert now[0] == pytest.approx(10 + 3300 / 16000)


def test_streaming_feed_refuses_a_missing_background_callback():
    with pytest.raises(RuntimeError, match="callback unavailable"):
        probe.feed_capture(SimpleNamespace(audio=np.ones(1600), sample_rate=16000, chunk_callback=None))


def test_matrix_feed_delivers_frames_only_after_their_samples_have_elapsed():
    now, chunks = [10.0], []
    capture = SimpleNamespace(audio=np.arange(3300, dtype=np.float32), sample_rate=16000,
        chunk_callback=lambda chunk: chunks.append((now[0], chunk.copy())))
    probe.feed_capture(capture, clock=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
                       deliver_after_frame=True)
    np.testing.assert_array_equal(np.concatenate([chunk for _, chunk in chunks]), capture.audio)
    assert [stamp for stamp, _ in chunks] == pytest.approx([10.1, 10.2, 10 + 3300 / 16000])
    assert now[0] == pytest.approx(chunks[-1][0])
