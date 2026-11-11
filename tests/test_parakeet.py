import hashlib
import json
import os
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.asr.sherpa_parakeet import DEFAULT_MODEL, ParakeetConfig, ParakeetEngine
from saydraft.privacy.netguard import NetworkGuard


def make_engine(tmp_path, monkeypatch):
    content = b"tiny model fixture"
    (tmp_path / "model.bin").write_bytes(content)
    model = {"revision": "fixture", "files": [{"path": "model.bin", "size": len(content),
                                                "sha256": hashlib.sha256(content).hexdigest()}]}
    (tmp_path / ".verified.json").write_text(json.dumps(model), encoding="utf-8")
    monkeypatch.setattr("saydraft.asr.sherpa_parakeet.get_model", lambda model_id: model)
    calls = []
    recognizer = SimpleNamespace()

    def stream():
        item = SimpleNamespace(result=SimpleNamespace(text="  Hello,  мир! "))
        item.accept_waveform = lambda rate, audio: calls.append((rate, audio.copy()))
        return item

    recognizer.create_stream = stream
    recognizer.decode_stream = lambda stream: None
    created = []

    def factory(directory, threads):
        created.append((directory, threads))
        return recognizer

    engine = ParakeetEngine(ParakeetConfig(silence_trim=False), model_dir=tmp_path, model_factory=factory)
    return engine, created, calls


def test_prepare_verifies_and_loads_once_then_transcribes_independent_mono_streams(tmp_path, monkeypatch):
    engine, created, calls = make_engine(tmp_path, monkeypatch)
    assert not created
    engine.prepare()
    audio = np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32)
    assert engine.transcribe(audio) == "Hello, мир!"
    assert engine.transcribe(audio) == "Hello, мир!"
    assert len(created) == 1 and len(calls) == 2
    assert calls[0][0] == 16000
    np.testing.assert_allclose(calls[0][1], [0.3, 0.7])
    assert engine.last_timings["stt"] > 0 and engine.load_seconds > 0


def test_tampered_weights_never_reach_native_runtime(tmp_path, monkeypatch):
    engine, created, calls = make_engine(tmp_path, monkeypatch)
    (tmp_path / "model.bin").write_bytes(b"corrupt model data")
    with pytest.raises(FileNotFoundError, match="Download or resume"):
        engine.prepare()
    assert not created and not calls


def test_empty_and_nonfinite_audio_do_not_load_weights(tmp_path, monkeypatch):
    engine, created, calls = make_engine(tmp_path, monkeypatch)
    assert engine.transcribe([]) == ""
    with pytest.raises(ValueError, match="invalid samples"):
        engine.transcribe([float("nan")])
    assert not created


@pytest.mark.parametrize("version", [3, 2])
@pytest.mark.integration
@pytest.mark.offline
def test_native_parakeet_transcribes_fixture_without_network_when_enabled(version):
    directory = os.environ.get(f"SAYDRAFT_TEST_PARAKEET_V{version}_MODEL")
    if not directory:
        pytest.skip("set the explicit verified model directory to run the native smoke")
    import soundfile as sf

    engine = ParakeetEngine(ParakeetConfig(model_id=DEFAULT_MODEL.replace("v3", f"v{version}")),
                            model_dir=directory)
    audio, rate = sf.read("tests/fixtures/hello.wav", dtype="float32")
    assert rate == 16000
    NetworkGuard.install()
    try:
        text = engine.transcribe(audio)
        assert text and "hello" in text.lower()
    finally:
        NetworkGuard.uninstall()
