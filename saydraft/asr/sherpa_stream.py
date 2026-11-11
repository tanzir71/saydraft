"""Cached English Nemotron model with independent streams; no runtime downloads."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from pathlib import Path

import numpy as np

from saydraft.model_download import find_installed_model
from saydraft.models.downloader import installation_ready
from saydraft.models.manifest import get_model
from saydraft.stt.whisper_engine import _to_mono_float32
from .model_ids import PREVIEW_MODEL

logger = logging.getLogger(__name__)


def default_model_directory():
    return find_installed_model(PREVIEW_MODEL)


def _create_recognizer(directory, threads):
    import sherpa_onnx
    from saydraft.privacy.telemetry import disable_sherpa_telemetry

    version = re.match(r"(\d+)\.(\d+)\.(\d+)", str(getattr(sherpa_onnx, "__version__", "")))
    if not version or tuple(map(int, version.groups())) < (1, 13, 4):
        raise RuntimeError("English live preview requires sherpa-onnx 1.13.4 or newer")
    disable_sherpa_telemetry(sherpa_onnx)
    return sherpa_onnx.OnlineRecognizer.from_transducer(
        encoder=str(directory / "encoder.int8.onnx"), decoder=str(directory / "decoder.int8.onnx"),
        joiner=str(directory / "joiner.int8.onnx"), tokens=str(directory / "tokens.txt"),
        num_threads=threads, provider="cpu", decoding_method="greedy_search", enable_endpoint_detection=False)


class NemotronPreviewModel:
    model_id = PREVIEW_MODEL

    def __init__(self, *, model_dir=None, factory=_create_recognizer, clock=time.perf_counter):
        self._directory = Path(model_dir) if model_dir is not None else None
        self._factory, self._clock = factory, clock
        self._model = None
        self._lock = threading.RLock()

    def prepare(self):
        """Verify/load before capture; subsequent streams reuse the same weights."""
        with self._lock:
            if self._model is not None:
                return
            directory = self._directory or default_model_directory()
            if directory is None or not installation_ready(get_model(PREVIEW_MODEL), directory, check_hashes=True):
                raise FileNotFoundError("Download or resume English live preview in Settings → Labs")
            self._model = self._factory(directory, min(4, os.cpu_count() or 1))

    def create_session(self, on_partial):
        self.prepare()
        with self._lock:
            stream = self._model.create_stream()
        return _NativeSession(self._model, stream, self._lock, on_partial, self._clock)


class _NativeSession:
    def __init__(self, model, stream, lock, callback, clock):
        self.model, self.stream, self.lock = model, stream, lock
        self.callback, self.clock = callback, clock
        self.text = ""
        self.complete = False
        self.compute_seconds = 0.0
        self.samples = 0

    def _decode(self):
        updates = []
        while self.model.is_ready(self.stream):
            self.model.decode_stream(self.stream)
            text = self.model.get_result(self.stream).strip()
            if text:
                self.text = text
            updates.append(text)
        return updates

    def _publish(self, updates):
        for text in updates:
            try:
                if self.callback is not None:
                    self.callback(text)
            except Exception:
                logger.debug("Live preview receiver is unavailable")  # Never log transcript content.

    def feed(self, audio):
        if self.stream is None:
            raise RuntimeError("The preview stream is closed")
        samples = _to_mono_float32(audio)
        if not samples.size:
            return
        if not np.isfinite(samples).all():
            raise ValueError("Preview audio contains invalid samples")
        started = self.clock()
        with self.lock:
            self.stream.accept_waveform(16000, samples)
            self.samples += len(samples)
            updates = self._decode()
        self.compute_seconds += self.clock() - started
        self._publish(updates)

    def finish(self):
        if self.stream is None:
            return self.text
        started = self.clock()
        try:
            with self.lock:
                self.stream.accept_waveform(16000, np.zeros(10560, dtype=np.float32))
                self.stream.input_finished()
                updates = self._decode()
                final = self.model.get_result(self.stream).strip()
                self.complete = bool(final) or not self.text
                self.text = final or self.text
            self.compute_seconds += self.clock() - started
            self._publish(updates)
            return self.text
        finally:
            self.stream, self.callback = None, None

    def discard(self):
        self.stream, self.callback = None, None
        self.complete = False
