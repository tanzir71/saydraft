"""Keep unit tests independent of the owner's downloaded model installations."""

import pytest


@pytest.fixture(autouse=True)
def isolate_optional_vad_models(monkeypatch):
    # Native smoke tests provide an explicit verified path instead.
    monkeypatch.setattr("saydraft.audio.vad_silero.default_model_path", lambda: None)
    monkeypatch.setattr("saydraft.asr.language_id.default_model_directory", lambda: None)
    monkeypatch.setattr("saydraft.asr.sherpa_stream.default_model_directory", lambda: None)
