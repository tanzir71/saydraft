"""Local spoken-language identification through the existing sherpa runtime."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np

from saydraft.model_download import find_installed_model
from saydraft.models.downloader import installation_ready
from saydraft.models.manifest import get_model
from saydraft.stt.whisper_engine import _to_mono_float32
from .languages import WHISPER_LANGUAGES
from .model_ids import LANGUAGE_ID_MODEL

logger = logging.getLogger(__name__)


def default_model_directory():
    return find_installed_model(LANGUAGE_ID_MODEL)


def _create_identifier(directory):
    import sherpa_onnx
    from saydraft.privacy.telemetry import disable_sherpa_telemetry

    disable_sherpa_telemetry(sherpa_onnx)
    config = sherpa_onnx.SpokenLanguageIdentificationConfig(
        whisper=sherpa_onnx.SpokenLanguageIdentificationWhisperConfig(
            encoder=str(directory / "tiny-encoder.int8.onnx"),
            decoder=str(directory / "tiny-decoder.int8.onnx")),
        num_threads=2, provider="cpu", debug=False)
    return sherpa_onnx.SpokenLanguageIdentification(config)


class AudioLanguageIdentifier:
    def __init__(self, *, model_dir=None, factory=_create_identifier):
        self._directory = Path(model_dir) if model_dir is not None else None
        self._factory = factory
        self._model = None
        self._checked = False
        self._lock = threading.Lock()

    def prepare(self):
        with self._lock:
            if self._checked:
                return self._model is not None
            directory = self._directory or default_model_directory()
            if directory is None:
                return False  # Setup may finish before the next recording.
            self._checked = True
            if not installation_ready(
                    get_model(LANGUAGE_ID_MODEL), directory, check_hashes=True):
                return False  # Existing installations remain usable until setup is completed.
            try:
                self._model = self._factory(directory)
            except Exception:
                logger.warning("Local language identification unavailable; keeping transcript checks")
                logger.debug("Language identification failure detail", exc_info=True)
            return self._model is not None

    def identify(self, audio):
        if self._model is None:
            return None  # Native initialization belongs before microphone capture.
        samples = _to_mono_float32(audio)[:8 * 16000]
        if len(samples) < 16000 or not np.isfinite(samples).all() or np.max(np.abs(samples)) < 0.001:
            return None
        with self._lock:
            try:
                stream = self._model.create_stream()
                stream.accept_waveform(sample_rate=16000, waveform=np.ascontiguousarray(samples))
                language = str(self._model.compute(stream)).strip().lower()
                return language if language in WHISPER_LANGUAGES else None
            except Exception:
                logger.warning("Language identification failed; keeping available recognition")
                logger.debug("Language identification error detail", exc_info=True)
                return None
