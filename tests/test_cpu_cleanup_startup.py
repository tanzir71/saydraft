"""CPU calibration follows speech loading without waiting for AI before capture."""

from dataclasses import replace
from types import SimpleNamespace

from saydraft.config import default_config
from tests.test_processing import make_processor
from tests.test_session_worker import make_worker


def prepared_worker(*, queued=False, backend="cpu", fail_cleanup=False):
    order = []
    config = default_config()
    config["llm"].update(enabled=True, backend=backend)

    def warm(_context=None):
        order.append("cleanup")
        if fail_cleanup:
            raise OSError("fixture cleanup unavailable")

    cleaner = SimpleNamespace(warm_for_context=warm, clean=lambda text: text)
    worker, _clock, executor, _events, signals, _keyboard = make_worker(
        queued=queued, processor=make_processor(cleaner=cleaner), config=config)
    worker.services.asr.prepare = lambda: order.append("speech")
    return worker, executor, order, signals


def test_cpu_startup_defers_cleanup_until_speech_loading_finishes():
    worker, executor, order, _signals = prepared_worker(queued=True)
    try:
        assert order == []
        assert worker.warm_recognition() and order == []
        executor.drain()
        assert order == ["speech", "cleanup"]
        assert worker.services.recorder.started == 0
    finally:
        worker.shutdown()


def test_first_capture_without_startup_warmup_preserves_speech_cleanup_microphone_order():
    worker, _executor, order, _signals = prepared_worker()
    original = worker.services.recorder.start
    worker.services.recorder.start = lambda: (order.append("microphone"), original())
    try:
        assert worker.start_recording()
        assert order == ["speech", "cleanup", "microphone"]
    finally:
        worker.shutdown()


def test_missing_speech_does_not_start_cpu_calibration_and_can_retry():
    worker, executor, order, signals = prepared_worker(queued=True)

    def missing():
        order.append("missing-speech")
        raise FileNotFoundError("fixture missing speech")

    worker.services.asr.prepare = missing
    try:
        assert worker.warm_recognition()
        executor.drain()
        assert order == ["missing-speech"]
        assert ("speech_model_status", "unavailable") in signals
        worker.services.asr.prepare = lambda: order.append("speech")
        assert worker.warm_recognition()
        executor.drain()
        assert order == ["missing-speech", "speech", "cleanup"]
    finally:
        worker.shutdown()


def test_failed_optional_cleanup_does_not_block_capture_after_speech_is_ready():
    worker, _executor, order, _signals = prepared_worker(fail_cleanup=True)
    try:
        assert worker.start_recording()
        assert order == ["speech", "cleanup"] and worker.services.recorder.started == 1
    finally:
        worker.shutdown()


def test_shutdown_during_speech_loading_cannot_start_late_cleanup():
    worker, executor, order, _signals = prepared_worker(queued=True)
    try:
        worker.services.asr.prepare = lambda: (order.append("speech"), worker.shutdown())
        assert worker.warm_recognition()
        executor.drain()
        assert order == ["speech"]
    finally:
        worker.shutdown()


def test_gpu_startup_preserves_existing_independent_cleanup_warmup():
    worker, executor, order, _signals = prepared_worker(queued=True, backend="vulkan")
    try:
        assert order == ["cleanup"]
        assert worker.warm_recognition()
        executor.drain()
        assert order == ["cleanup", "speech"]
    finally:
        worker.shutdown()


def test_settings_successor_cpu_cleanup_waits_for_replacement_speech_model():
    worker, _clock, executor, _events, _signals, _keyboard = make_worker(queued=True)
    order = []
    config = default_config()
    config["llm"].update(enabled=True, backend="cpu")
    cleaner = SimpleNamespace(warm_for_context=lambda _context: order.append("cleanup"), clean=lambda text: text)
    processor, _events, _notifications = make_processor(cleaner=cleaner)
    replacement = replace(worker.services, config=config, cleaner=cleaner, processor=processor,
                          asr=SimpleNamespace(prepare=lambda: order.append("speech")))
    worker.services_factory = lambda *args, **kwargs: replacement
    try:
        worker.configure(config)
        assert order == []
        assert worker.warm_recognition()
        executor.drain()
        assert order == ["speech", "cleanup"]
    finally:
        worker.shutdown()
