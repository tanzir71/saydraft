import pytest

from tools.bench import percentile, run_benchmark, summarize, to_markdown
from saydraft.privacy.netguard import NetworkGuard


def test_latency_summary_keeps_cold_and_warm_separate():
    rows = summarize([
        {"phase": "cold", "total": 1.0},
        {"phase": "warm", "total": 0.1},
        {"phase": "warm", "total": 0.2},
    ])
    totals = [row for row in rows if row["stage"] == "total"]
    assert totals == [
        {"phase": "cold", "stage": "total", "samples": 1, "p50_ms": 1000, "p95_ms": 1000},
        {"phase": "warm", "stage": "total", "samples": 2, "p50_ms": 150, "p95_ms": 200},
    ]
    assert percentile([2, 1, 3], 0.95) == 3
    with pytest.raises(ValueError):
        percentile([], 0.95)


def test_synthetic_benchmark_reports_missing_asr_without_user_data(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    try:
        report = run_benchmark(iterations=2)
    finally:
        NetworkGuard.uninstall()
    assert report["model"] is None
    assert all(row["samples"] == 0 for row in report["rows"] if row["stage"] in ("stt", "vad", "llm"))
    text = to_markdown(report)
    assert "not measured" in text
    assert "um hello" not in text
    assert not list(tmp_path.rglob("history.db"))
