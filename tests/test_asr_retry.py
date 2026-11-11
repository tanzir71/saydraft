from types import SimpleNamespace

import numpy as np

from saydraft.asr.retry import AllLanguagesRetry
from saydraft.asr.router import ALL_LANGUAGES
from saydraft.asr.whisper_ct2 import WhisperCT2Engine, WhisperEngineConfig
from saydraft.config import default_config


def test_explicit_retry_selects_local_only_multilingual_engine_once():
    calls = []
    engine = SimpleNamespace(transcribe=lambda audio: "retry words", last_language="ar", last_timings={"stt": 0.2})
    config = default_config()
    config["stt"]["local_files_only"] = False

    def factory(selected):
        calls.append(selected)
        return engine

    retry = AllLanguagesRetry(config, SimpleNamespace(), factory=factory)
    assert retry.transcribe(np.ones(16000, dtype=np.float32)) == "retry words"
    retry.transcribe(np.ones(16000, dtype=np.float32))
    assert len(calls) == 1
    assert calls[0]["stt"]["model_size"] == "large-v3-turbo"
    assert calls[0]["stt"]["language"] == "auto"
    assert calls[0]["stt"]["local_files_only"] is True
    assert calls[0]["stt"]["routing_enabled"] is False
    assert retry.model_id == ALL_LANGUAGES and retry.last_language == "ar"
    assert config["stt"]["engine"] == "parakeet"


def test_language_view_shares_whisper_weights_and_preserves_original_hint():
    created = []
    hints = []
    model = SimpleNamespace(transcribe=lambda audio, **kwargs: (
        hints.append(kwargs["language"]) or iter([SimpleNamespace(text="hello")]),
        SimpleNamespace(language="en")))

    def factory(*args, **kwargs):
        created.append(True)
        return model

    primary = WhisperCT2Engine(WhisperEngineConfig(model_size="large-v3-turbo", language="ar", silence_trim=False),
                               model_factory=factory)
    primary.prepare()
    retry = AllLanguagesRetry(default_config(), primary)
    retry.transcribe(np.ones(16000, dtype=np.float32))
    primary.transcribe(np.ones(16000, dtype=np.float32))
    assert len(created) == 1
    assert hints == [None, "ar"]
    assert primary.config.language == "ar"
