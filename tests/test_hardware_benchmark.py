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
        cleanup_benchmark=lambda: [{"parameters_b": 0.8, "tokens": 60, "seconds": 2}])
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
