import logging
import types

import numpy as np


def test_whisper_engine_records_vad_and_stt_timings():
    from saydraft.stt.whisper_engine import WhisperEngine, WhisperEngineConfig

    class FakeModel:
        def transcribe(self, *_args, **_kwargs):
            return [types.SimpleNamespace(text="hello")], object()

    engine = WhisperEngine(
        WhisperEngineConfig(model_size="base", silence_trim=False),
        model_factory=lambda *_args, **_kwargs: FakeModel(),
    )

    assert engine.transcribe(np.array([0.1, 0.2], dtype=np.float32)) == "hello"

    assert set(engine.last_timings) >= {"vad", "stt"}
    assert engine.last_timings["vad"] >= 0
    assert engine.last_timings["stt"] >= 0


def test_dictation_pipeline_records_rules_and_llm_timings():
    from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline

    class FakeLLM:
        def available(self):
            return False

    pipeline = DictationPipeline(DictationConfig(), llm_cleaner=FakeLLM())

    assert pipeline.process_transcript("um hello hello", DictationContext()) == "Hello"

    assert set(pipeline.last_timings) >= {"rules", "llm"}
    assert pipeline.last_timings["rules"] >= 0
    assert pipeline.last_timings["llm"] >= 0


def test_processing_reports_stage_timings_without_transcript(caplog, monkeypatch):
    from tests.test_processing import make_processor, process
    monkeypatch.setattr(logging.getLogger("saydraft"), "propagate", True)
    processor, _events, _notifications = make_processor()
    processor.clock = iter([10.0, 10.2]).__next__
    processor.cleaner.last_timings = {"rules": 0.11, "llm": 0.22, "dictionary": 0.04}
    with caplog.at_level(logging.INFO, logger="saydraft.core.timings"):
        process(processor, "private words", timings={"record": 1.2, "vad": 0.03, "stt": 0.4})
    assert "record=1.200s" in caplog.text
    assert "rules=0.110s" in caplog.text
    assert "llm=0.220s" in caplog.text
    assert "insert=0.200s" in caplog.text
    assert "dictionary=0.040s" in caplog.text
    assert "total=1.000s" in caplog.text
    assert "private words" not in caplog.text


def test_slow_small_model_suggests_base_only_once():
    from saydraft.core.timings import TimingReporter
    notifications = []
    reporter = TimingReporter(notify=notifications.append)
    for _ in range(2):
        reporter.report({"record": 10, "stt": 1.4, "rules": 0.2, "insert": 0.1}, "small")
    assert notifications == ["Small model is running slowly; try the base model in Settings > Models."]
