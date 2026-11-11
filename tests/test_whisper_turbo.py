import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from saydraft.asr.selection import configured_model_id, create_asr, select_model
from saydraft.asr.whisper_ct2 import TURBO_MODEL, WhisperCT2Engine, WhisperEngineConfig
from saydraft.config import default_config, sanitize_config
from tools.bench_languages import run_smoke, script_ratio


def test_turbo_selection_uses_whisper_and_preserves_int8_language_configuration():
    cfg = default_config()
    cfg["stt"]["language"] = "bn"
    select_model(cfg, "whisper-" + TURBO_MODEL)
    cfg = sanitize_config(cfg)
    engine = create_asr(cfg)
    assert isinstance(engine, WhisperCT2Engine)
    assert engine.config.model_size == TURBO_MODEL
    assert engine.config.compute_type == "int8"
    assert engine.config.language == "bn"
    assert configured_model_id(cfg) == engine.model_id == "whisper-" + TURBO_MODEL


def test_prepare_loads_turbo_once_and_transcription_retains_bengali_script():
    calls = []
    transcriptions = []

    def transcribe(audio, **kwargs):
        transcriptions.append(kwargs)
        return iter([SimpleNamespace(text="বাংলা ভাষায় কথা বলুন।")]), SimpleNamespace(language="bn")

    model = SimpleNamespace(transcribe=transcribe)

    def factory(*args, **kwargs):
        calls.append((args, kwargs))
        return model

    engine = WhisperCT2Engine(WhisperEngineConfig(model_size=TURBO_MODEL, language="bn", silence_trim=False),
                              model_factory=factory)
    engine.prepare()
    assert len(calls) == 1
    assert engine.transcribe(np.full(16000, 0.1, dtype=np.float32)) == "বাংলা ভাষায় কথা বলুন।"
    assert len(calls) == 1
    assert calls[0][0] == (TURBO_MODEL,)
    assert calls[0][1]["local_files_only"] is True
    assert transcriptions[0]["language"] == "bn"


@pytest.mark.parametrize("language,script", [("bn", "BENGALI"), ("ar", "ARABIC")])
def test_fleurs_smoke_fixtures_have_provenance_checksum_and_expected_audio_format(language, script):
    root = Path(__file__).with_name("fixtures")
    info = json.loads((root / f"fleurs-{language}.json").read_text(encoding="utf-8"))
    audio = root / f"fleurs-{language}.wav"
    assert hashlib.sha256(audio.read_bytes()).hexdigest() == info["sha256"]
    assert info["license"] == "CC-BY-4.0" and info["dataset"] == "google/fleurs"
    assert script_ratio(info["reference"], script) > 0.9
    samples, rate = sf.read(audio, dtype="float32")
    assert rate == 16000 and samples.ndim == 1 and len(samples) > 16000


def test_script_smoke_rejects_english_translation_and_empty_output():
    assert script_ratio("This is a translation.", "BENGALI") == 0
    assert script_ratio("", "ARABIC") == 0


@pytest.mark.integration
@pytest.mark.offline
def test_native_turbo_produces_bengali_and_arabic_script_without_network():
    directory = os.environ.get("SAYDRAFT_TEST_WHISPER_TURBO_MODEL")
    if not directory:
        pytest.skip("provide the explicitly downloaded pinned Whisper turbo model")
    report = run_smoke(Path(directory))
    assert report["passed"], [{key: row[key] for key in ("language", "script_ratio", "passed")}
                              for row in report["clips"]]
