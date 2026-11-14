"""Local Silero v5 VAD through sherpa-onnx, with an explicit WebRTC fallback."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from .vad import SilenceTrimConfig, SpeechFrameDetector, trim_silence

logger = logging.getLogger(__name__)
MODEL_ID = "silero-vad-v5"


def default_model_path() -> Path | None:
    from saydraft.model_download import find_installed_model

    directory = find_installed_model(MODEL_ID, check_hashes=True)
    return directory / "silero_vad.onnx" if directory is not None else None


def _create_detector(model_path: Path, *, threshold=0.5):
    import sherpa_onnx
    from saydraft.privacy.telemetry import disable_sherpa_telemetry

    disable_sherpa_telemetry(sherpa_onnx)

    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = str(model_path)
    config.silero_vad.window_size = 512
    config.silero_vad.threshold = threshold
    config.silero_vad.min_silence_duration = 0.1
    config.silero_vad.min_speech_duration = 0.1
    config.sample_rate = 16000
    config.num_threads = 1
    config.provider = "cpu"
    return sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)


class SileroVad:
    window_samples = 512

    def __init__(self, model_path: str | Path, *, detector_factory=None, threshold=0.5):
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError("Download the Silero speech detection model in Settings first")
        if not np.isfinite(threshold) or not 0 < threshold < 1:
            raise ValueError("Speech detection threshold must be between 0 and 1")
        self.detector = detector_factory(path) if detector_factory is not None else _create_detector(path, threshold=threshold)
        self._pending = np.empty(0, dtype=np.float32)
        self._speech = False

    def __call__(self, frame: np.ndarray) -> bool:
        audio = np.concatenate((self._pending, np.asarray(frame, dtype=np.float32)))
        count = len(audio) // self.window_samples
        for index in range(count):
            self.detector.accept_waveform(audio[index * self.window_samples:(index + 1) * self.window_samples])
            self._speech = bool(self.detector.is_speech_detected())
            while not self.detector.empty():
                self.detector.pop()
        self._pending = audio[count * self.window_samples:]
        return self._speech

    def trim(self, audio, *, padding_ms=120) -> np.ndarray:
        if padding_ms < 0:
            raise ValueError("speech padding cannot be negative")
        waveform = np.ascontiguousarray(audio, dtype=np.float32).reshape(-1)
        if not len(waveform):
            return waveform
        self.detector.reset()
        bounds = []

        def collect():
            while not self.detector.empty():
                segment = self.detector.front
                bounds.append((segment.start, segment.start + len(segment.samples)))
                self.detector.pop()

        for offset in range(0, len(waveform), self.window_samples):
            frame = waveform[offset:offset + self.window_samples]
            if len(frame) < self.window_samples:
                frame = np.pad(frame, (0, self.window_samples - len(frame)))
            self.detector.accept_waveform(frame)
            collect()
        self.detector.flush()
        collect()
        if not bounds:
            return np.empty(0, dtype=np.float32)
        padding = round(padding_ms * 16)
        start = max(0, min(item[0] for item in bounds) - padding)
        end = min(len(waveform), max(item[1] for item in bounds) + padding)
        return waveform[start:end]


def optional_silero(model_path: str | Path | None = None, *, threshold=0.5) -> SileroVad | None:
    path = Path(model_path) if model_path is not None else default_model_path()
    if path is None:
        return None
    try:
        return SileroVad(path) if threshold == 0.5 else SileroVad(path, threshold=threshold)
    except Exception:
        logger.warning("Silero speech detection unavailable; using WebRTC")
        logger.debug("Silero initialization detail", exc_info=True)
        return None


class FallbackFrameDetector:
    def __init__(self, config: SilenceTrimConfig):
        self.primary = optional_silero() if config.silero_threshold == 0.5 else optional_silero(threshold=config.silero_threshold)
        self.fallback = SpeechFrameDetector(config)

    def __call__(self, frame):
        if self.primary is not None:
            try:
                return self.primary(frame)
            except Exception:
                logger.warning("Silero speech detection failed; using WebRTC for this recording")
                logger.debug("Silero inference detail", exc_info=True)
                self.primary = None
        return self.fallback(frame)


def trim_with_fallback(audio, config: SilenceTrimConfig, primary: SileroVad | None):
    if primary is not None:
        try:
            return primary.trim(audio, padding_ms=config.padding_ms)
        except Exception:
            logger.warning("Silero trimming failed; using WebRTC")
            logger.debug("Silero trimming detail", exc_info=True)
    return trim_silence(audio, config)
