import hashlib
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from saydraft.models.benchmark import fixture_path, run_benchmark
from saydraft.models.hardware import latest_report
from saydraft.ui.hardware_page import HardwarePage
from tests.test_session_worker import make_worker


def make_asr():
    clock = SimpleNamespace(now=0.0)
    seen = []

    def prepare():
        clock.now += 3

    def transcribe(audio):
        seen.append(audio.copy())
        clock.now += 0.5
        return "Benchmark words never leave this call"

    asr = SimpleNamespace(model_id="fixture-model", prepare=prepare, transcribe=transcribe)
    return asr, clock, seen


def test_eight_second_asset_preserves_original_samples_and_is_packaged():
    fixture, rate = sf.read(fixture_path(), dtype="int16")
    original, original_rate = sf.read("tests/fixtures/hello.wav", dtype="int16")
    assert rate == original_rate == 16000
    np.testing.assert_array_equal(fixture, np.tile(original, 3)[:128000])
    assert hashlib.sha256(fixture_path().read_bytes()).hexdigest() == (
        "cc6d363cc90b6c99427041ba6366e334131b05101a142761ae84b2a8b5e2c5ab")


def test_benchmark_excludes_prepare_warms_once_and_persists_metrics_without_text(tmp_path):
    asr, clock, seen = make_asr()
    report = run_benchmark(asr, directory=tmp_path, clock=lambda: clock.now,
        hardware_probe=lambda: {"schema_version": 1, "ram_bytes": 16 * 1024**3},
        cleanup_benchmark=lambda: [{"parameters_b": 0.8, "tokens": 60, "seconds": seconds}
                                  for seconds in (1, 2, 6)])
    assert len(seen) == 4 and all(audio.shape == (128000,) for audio in seen)
    measured = report["measurements"]
    assert measured["prepare_seconds"] == 3 and measured["asr_seconds"] == 0.5
    assert measured["llm_08_tps"] == 30 and report["assessment"]["tier"] == "standard"
    assert latest_report(tmp_path) == report
    assert "Benchmark words" not in next(tmp_path.glob("*.json")).read_text(encoding="utf-8")


def test_missing_model_stays_pending_without_loading_or_downloading_a_replacement(tmp_path):
    def missing():
        raise FileNotFoundError("explicit setup required")

    report = run_benchmark(SimpleNamespace(prepare=missing), directory=tmp_path,
        hardware_probe=lambda: {"schema_version": 1, "ram_bytes": 16 * 1024**3})
    assert report["measurements"]["asr_status"] == "model_missing"
    assert report["assessment"]["tier"] == "pending"


def test_incomplete_cleanup_generation_cannot_establish_a_rate(tmp_path):
    asr, clock, _seen = make_asr()
    report = run_benchmark(asr, directory=tmp_path, clock=lambda: clock.now,
        hardware_probe=lambda: {"schema_version": 1, "ram_bytes": 16 * 1024**3},
        cleanup_benchmark=lambda: [{"parameters_b": 0.8, "tokens": 20, "seconds": 0.1}])
    assert report["measurements"]["cleanup_status"] == "failed"
    assert report["measurements"]["llm_08_tps"] is None
    assert report["assessment"]["tier"] == "pending"


@pytest.mark.parametrize("change", ["partial", "bad_second_model", "bool_tokens", "bool_seconds", "mixed_sizes"])
def test_cleanup_sample_failure_is_atomic_and_cannot_promote_a_tier(tmp_path, change):
    asr, clock, _ = make_asr()
    rows = [{"parameters_b": 0.8, "tokens": 60, "seconds": 1} for _ in range(3)]
    if change == "partial":
        rows.pop()
    elif change == "bad_second_model":
        rows += [{"parameters_b": 2, "tokens": 60, "seconds": float("nan")} for _ in range(3)]
    elif change == "bool_tokens":
        rows[2]["tokens"] = True
    elif change == "bool_seconds":
        rows[2]["seconds"] = True
    else:
        rows[2]["parameters_b"] = 2
    measured = run_benchmark(asr, directory=tmp_path, clock=lambda: clock.now,
        hardware_probe=lambda: {"schema_version": 1, "ram_bytes": 16 * 1024**3},
        cleanup_benchmark=lambda: rows)["measurements"]
    assert measured["cleanup_status"] == "failed" and measured["cleanup"] == []
    assert measured["llm_08_tps"] is measured["llm_2_tps"] is None


@pytest.mark.parametrize("size,key", [(0.82, "llm_08_tps"), (2.03, "llm_2_tps"), (4, None)])
def test_actual_parameter_class_and_numeric_metadata_only(tmp_path, size, key):
    asr, clock, _ = make_asr()
    measured = run_benchmark(asr, directory=tmp_path, clock=lambda: clock.now,
        hardware_probe=lambda: {"schema_version": 1, "ram_bytes": 16 * 1024**3},
        cleanup_benchmark=lambda: [{"parameters_b": size, "tokens": 60, "seconds": seconds,
                                    "content": "private generated words"} for seconds in (1, 3, 2)])["measurements"]
    assert measured["cleanup_status"] == "ok"
    assert all(set(row) == {"parameters_b", "tokens", "seconds"} for row in measured["cleanup"])
    if key:
        assert measured[key] == 30
    else:
        assert measured["llm_08_tps"] is measured["llm_2_tps"] is None


def test_complete_two_model_triples_have_independent_medians(tmp_path):
    asr, clock, _ = make_asr()
    rows = [{"parameters_b": size, "tokens": 60, "seconds": seconds}
            for size, costs in ((0.8, (1, 2, 6)), (2, (2, 1, 0.5))) for seconds in costs]
    measured = run_benchmark(asr, directory=tmp_path, clock=lambda: clock.now,
        hardware_probe=lambda: {"schema_version": 1, "ram_bytes": 16 * 1024**3},
        cleanup_benchmark=lambda: rows)["measurements"]
    assert measured["llm_08_tps"] == 30 and measured["llm_2_tps"] == 60


def test_performance_page_shows_cleanup_median_and_failed_measurement_guidance(tmp_path):
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = HardwarePage(directory=tmp_path)
    report = {"measurements": {"cleanup_status": "ok", "cleanup": [
        {"parameters_b": 2.03, "tokens": 60, "seconds": seconds} for seconds in (1, 2, 6)]}}
    page.render(report)
    assert "30.0 tokens/s median over 3 × 60 tokens" in page.details.toPlainText()
    page.render({"measurements": {"cleanup_status": "failed"}})
    assert "could not be measured" in page.status.text()
    page.deleteLater()
    app.processEvents()


def test_default_worker_supplies_applied_cleaner_benchmark_after_asr(monkeypatch):
    worker, _, executor, events, signals, _ = make_worker(queued=True)
    calls = []
    worker.services.cleaner.benchmark = lambda: calls.append("cleanup") or []
    def benchmark(asr, *, cleanup_benchmark):
        assert asr is worker.services.asr
        calls.append("speech")
        cleanup_benchmark()
        return {"checked": True}
    monkeypatch.setattr("saydraft.models.benchmark.run_benchmark", benchmark)
    assert worker.benchmark_hardware() and not calls
    executor.drain()
    assert calls == ["speech", "cleanup"] and not events
    assert ("hardware_benchmark_finished", {"checked": True}) in signals


def test_serial_worker_benchmark_blocks_capture_and_never_records_or_inserts():
    worker, _clock, executor, events, signals, _keyboard = make_worker(queued=True)
    report = {"assessment": {"tier": "pending"}}
    assert worker.benchmark_hardware(benchmark=lambda asr: report)
    assert worker.busy and not worker.start_recording()
    assert not worker.benchmark_hardware(benchmark=lambda asr: report)
    executor.drain()
    assert not worker.busy and not events
    assert worker.services.recorder.started == worker.services.recorder.stopped == 0
    assert ("hardware_benchmark_finished", report) in signals
    assert worker.start_recording()


def test_queue_failure_releases_benchmark_state():
    worker, _clock, executor, _events, _signals, _keyboard = make_worker()
    executor.submit = lambda *args: (_ for _ in ()).throw(RuntimeError("queue unavailable"))
    assert not worker.benchmark_hardware(benchmark=lambda asr: {})
    assert not worker.busy and not worker._benchmarking


def test_failed_check_releases_capture_without_changing_history():
    worker, _clock, _executor, events, signals, _keyboard = make_worker()

    def fail(asr):
        raise RuntimeError("runtime unavailable")

    assert worker.benchmark_hardware(benchmark=fail)
    assert ("hardware_benchmark_finished", None) in signals and not events
    assert not worker.busy and worker.start_recording()


@pytest.mark.parametrize("accepted", [False, True])
def test_performance_page_is_explicit_and_preserves_results_on_failure(tmp_path, accepted):
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []
    page = HardwarePage(callback=lambda: calls.append(True) or accepted, directory=tmp_path)
    app.processEvents()
    assert not calls and "not been checked" in page.summary.text()
    page.start()
    assert calls == [True] and page.busy is accepted
    if accepted:
        page.finish({"assessment": {"tier": "lite"}, "measurements": {"asr_status": "model_missing"}})
        assert "Lite" in page.summary.text() and "Install" in page.status.text()
        original = page.details.toPlainText()
        page.start()
        page.finish(None)
        assert page.details.toPlainText() == original and "Previous results" in page.status.text()
    assert page.check_button.isEnabled()
