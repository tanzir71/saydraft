import os
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.audio.vad import SilenceTrimConfig
from saydraft.audio.vad_silero import FallbackFrameDetector, SileroVad, optional_silero


class Detector:
    def __init__(self):
        self.reset()

    def reset(self):
        self.offset = 0
        self.queue = []
        self.speech = False

    def accept_waveform(self, frame):
        self.speech = bool(np.max(np.abs(frame)) > 0.01)
        if self.speech:
            self.queue.append(SimpleNamespace(start=self.offset, samples=frame))
        self.offset += len(frame)

    def is_speech_detected(self):
        return self.speech

    def empty(self):
        return not self.queue

    @property
    def front(self):
        return self.queue[0]

    def pop(self):
        self.queue.pop(0)

    def flush(self):
        pass


def make_vad(tmp_path):
    path = tmp_path / "vad.onnx"
    path.write_bytes(b"injected backend fixture")
    return SileroVad(path, detector_factory=lambda path: Detector())


def test_silero_trims_only_outer_silence_and_preserves_internal_pauses(tmp_path):
    vad = make_vad(tmp_path)
    speech = np.full(512, 0.1, dtype=np.float32)
    silence = np.zeros(512, dtype=np.float32)
    audio = np.concatenate((silence, speech, silence, speech, silence))
    trimmed = vad.trim(audio, padding_ms=0)
    np.testing.assert_array_equal(trimmed, audio[512:2048])
    assert not len(vad.trim(np.zeros(16000, dtype=np.float32)))


def test_silero_accepts_non_window_sized_streaming_frames(tmp_path):
    vad = make_vad(tmp_path)
    assert not vad(np.full(480, 0.1, dtype=np.float32))
    assert vad(np.full(480, 0.1, dtype=np.float32))


def test_invalid_padding_cannot_clip_words(tmp_path):
    with pytest.raises(ValueError, match="negative"):
        make_vad(tmp_path).trim(np.ones(512, dtype=np.float32), padding_ms=-1)


def test_missing_optional_model_never_downloads_or_imports_runtime():
    assert optional_silero() is None


def test_web_rtc_fallback_remains_available_after_native_failure(monkeypatch):
    import saydraft.audio.vad_silero as module

    def failed(frame):
        raise RuntimeError("native inference failed")

    monkeypatch.setattr(module, "optional_silero", lambda: failed)
    detector = FallbackFrameDetector(SilenceTrimConfig())
    assert detector(np.full(480, 0.1, dtype=np.float32))
    assert detector.primary is None


@pytest.mark.integration
@pytest.mark.offline
def test_real_silero_detects_bundled_speech_and_skips_silence():
    path = os.environ.get("SAYDRAFT_TEST_SILERO_MODEL")
    if not path:
        pytest.skip("Provide an explicitly downloaded SAYDRAFT_TEST_SILERO_MODEL")
    pytest.importorskip("sherpa_onnx")
    import soundfile as sf

    from saydraft.privacy.netguard import NetworkGuard

    NetworkGuard.install()
    try:
        vad = SileroVad(path)
        audio, rate = sf.read("tests/fixtures/hello.wav", dtype="float32")
        assert rate == 16000
        assert 0 < len(vad.trim(audio)) <= len(audio)
        assert len(vad.trim(np.zeros(3 * rate, dtype=np.float32))) == 0
    finally:
        NetworkGuard.uninstall()
