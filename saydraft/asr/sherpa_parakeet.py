"""Pinned Parakeet TDT int8 inference on CPU, without runtime downloads."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from saydraft.audio.vad import SilenceTrimConfig
from saydraft.audio.vad_silero import optional_silero, trim_with_fallback
from saydraft.model_download import find_installed_model
from saydraft.models.downloader import installation_ready
from saydraft.models.manifest import get_model
from saydraft.stt.whisper_engine import _to_mono_float32

logger = logging.getLogger(__name__)
DEFAULT_MODEL = "parakeet-tdt-0-6b-v3-int8"
ENGLISH_MODEL = "parakeet-tdt-0-6b-v2-int8"


@dataclass(frozen=True)
class ParakeetConfig:
    model_id: str = DEFAULT_MODEL
    threads: int = 4
    silence_trim: bool = True
    silence_padding_ms: int = 120
    vad_aggressiveness: int = 2
    vad_energy_threshold: float = 0.003

    @classmethod
    def from_app_config(cls, config):
        stt = config.get("stt", {})
        return cls(model_id=stt.get("model_id", DEFAULT_MODEL),
                   threads=max(1, min(4, os.cpu_count() or 1)),
                   **{key: stt.get(key, getattr(cls, key)) for key in (
                       "silence_trim", "silence_padding_ms", "vad_aggressiveness", "vad_energy_threshold")})


def _create_recognizer(directory, threads):
    import sherpa_onnx
    from saydraft.privacy.telemetry import disable_sherpa_telemetry

    disable_sherpa_telemetry(sherpa_onnx)
    # The official NeMo example uses the runtime's feature defaults; the encoder
    # metadata supplies the model-specific feature dimensions and TDT parameters.
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(directory / "encoder.int8.onnx"),
        decoder=str(directory / "decoder.int8.onnx"),
        joiner=str(directory / "joiner.int8.onnx"), tokens=str(directory / "tokens.txt"),
        num_threads=threads, provider="cpu", model_type="nemo_transducer",
        decoding_method="greedy_search", debug=False,
    )


class ParakeetEngine:
    def __init__(self, config=None, *, model_dir=None, model_factory=_create_recognizer):
        self.config = config or ParakeetConfig()
        if self.config.model_id not in (DEFAULT_MODEL, ENGLISH_MODEL):
            raise ValueError("Unknown Parakeet model")
        self.model_id = self.config.model_id
        self._directory = Path(model_dir) if model_dir is not None else None
        self._factory = model_factory
        self._recognizer = None
        self._lock = threading.RLock()
        self._vad = None
        self.load_seconds = 0.0
        self.last_timings = {}
        self.last_language = None
        self.last_audio_seconds = 0.0

    def prepare(self):
        """Load before microphone capture so native initialization cannot stall callbacks."""
        with self._lock:
            if self._recognizer is not None:
                return
            started = time.perf_counter()
            directory = self._directory or find_installed_model(self.model_id)
            if directory is None or not installation_ready(get_model(self.model_id), directory, check_hashes=True):
                raise FileNotFoundError("Download or resume the selected Parakeet model in Settings → Models")
            recognizer = self._factory(directory, self.config.threads)
            if self.config.silence_trim:
                self._vad = optional_silero()
            self._recognizer = recognizer
            self.load_seconds = time.perf_counter() - started
            logger.info("ASR loaded: model=%s provider=cpu threads=%d seconds=%.3f",
                        self.model_id, self.config.threads, self.load_seconds)

    def transcribe(self, audio):
        with self._lock:
            self.last_timings = {"vad": 0.0, "stt": 0.0}
            self.last_language = None
            self.last_audio_seconds = 0.0
            waveform = _to_mono_float32(audio)
            if not np.isfinite(waveform).all():
                raise ValueError("Audio contains invalid samples")
            if not waveform.size:
                return ""
            self.prepare()
            started = time.perf_counter()
            if self.config.silence_trim:
                waveform = trim_with_fallback(waveform, SilenceTrimConfig(
                    sample_rate=16000, padding_ms=self.config.silence_padding_ms,
                    aggressiveness=self.config.vad_aggressiveness,
                    energy_threshold=self.config.vad_energy_threshold), self._vad)
            self.last_timings["vad"] = time.perf_counter() - started
            self.last_audio_seconds = len(waveform) / 16000
            if not waveform.size:
                return ""
            started = time.perf_counter()
            try:
                stream = self._recognizer.create_stream()
                stream.accept_waveform(16000, waveform)
                self._recognizer.decode_stream(stream)
                self.last_language = getattr(stream.result, "lang", None) or None
                return " ".join(stream.result.text.split())
            finally:
                self.last_timings["stt"] = time.perf_counter() - started
