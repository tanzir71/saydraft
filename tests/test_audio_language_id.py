import os
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.asr.language_id import AudioLanguageIdentifier
from saydraft.privacy.netguard import NetworkGuard


def make_identifier(tmp_path, monkeypatch, *, verified=True):
    monkeypatch.setattr("saydraft.asr.language_id.installation_ready", lambda *a, **kw: verified)
    calls = []
    model = SimpleNamespace(compute=lambda stream: "bn")
    model.create_stream = lambda: SimpleNamespace(
        accept_waveform=lambda **kwargs: calls.append(kwargs["waveform"]))
    created = []
    identifier = AudioLanguageIdentifier(model_dir=tmp_path,
        factory=lambda path: created.append(path) or model)
    return identifier, model, calls, created


def test_prepare_verifies_once_before_capture_and_bounds_downmixed_audio(tmp_path, monkeypatch):
    identifier, _model, calls, created = make_identifier(tmp_path, monkeypatch)
    audio = np.tile([0.2, 0.4], (16000 * 10, 1))
    assert identifier.identify(audio) is None and not created
    assert identifier.prepare() and identifier.prepare()
    assert len(created) == 1
    assert identifier.identify(audio) == "bn"
    assert calls[0].shape == (16000 * 8,)
    np.testing.assert_allclose(calls[0], 0.3)


def test_unverified_helper_never_reaches_native_runtime(tmp_path, monkeypatch):
    identifier, _model, calls, created = make_identifier(tmp_path, monkeypatch, verified=False)
    assert not identifier.prepare()
    assert identifier.identify(np.ones(16000)) is None
    assert not created and not calls


def test_missing_helper_can_be_found_after_explicit_setup(tmp_path, monkeypatch):
    identifier, _model, _calls, created = make_identifier(tmp_path, monkeypatch)
    identifier._directory = None
    assert not identifier.prepare()
    monkeypatch.setattr("saydraft.asr.language_id.default_model_directory", lambda: tmp_path)
    assert identifier.prepare() and len(created) == 1


@pytest.mark.parametrize("audio", [[], [0.2], np.zeros(16000), np.full(16000, np.nan)])
def test_short_silent_or_invalid_audio_skips_detection(tmp_path, monkeypatch, audio):
    identifier, _model, calls, _created = make_identifier(tmp_path, monkeypatch)
    identifier.prepare()
    assert identifier.identify(audio) is None and not calls


def test_detection_failure_and_unknown_code_keep_recognition_available(tmp_path, monkeypatch):
    identifier, model, _calls, _created = make_identifier(tmp_path, monkeypatch)
    identifier.prepare()
    model.compute = lambda stream: "unknown"
    assert identifier.identify(np.ones(16000)) is None
    model.compute = lambda stream: (_ for _ in ()).throw(RuntimeError("native failure"))
    assert identifier.identify(np.ones(16000)) is None


@pytest.mark.integration
@pytest.mark.offline
def test_native_language_id_on_three_fixtures_when_enabled():
    directory = os.environ.get("SAYDRAFT_TEST_LANGUAGE_ID_MODEL")
    if not directory:
        pytest.skip("set the explicit verified helper directory for native smoke")
    import soundfile as sf

    NetworkGuard.install()
    try:
        identifier = AudioLanguageIdentifier(model_dir=directory)
        assert identifier.prepare()
        for filename, expected in (("hello.wav", "en"), ("fleurs-bn.wav", "bn"), ("fleurs-ar.wav", "ar")):
            audio, rate = sf.read("tests/fixtures/" + filename, dtype="float32")
            assert rate == 16000 and identifier.identify(audio) == expected
    finally:
        NetworkGuard.uninstall()
