"""Bounded, owned audio queue for optional preview; the capture callback never decodes."""

from __future__ import annotations

import logging
import math
import queue
import threading
from dataclasses import dataclass

import numpy as np

from saydraft.stt.whisper_engine import _to_mono_float32

logger = logging.getLogger(__name__)
_STOP = object()


@dataclass(frozen=True)
class PreviewResult:
    text: str
    failed: bool
    complete: bool
    samples: int
    compute_seconds: float
    failure_reason: str | None = None


class PreviewSession:
    def __init__(self, model, *, on_partial=lambda text: None, on_failed=lambda: None,
                 maximum_pending_seconds=2):
        if not math.isfinite(maximum_pending_seconds) or maximum_pending_seconds <= 0:
            raise ValueError("Preview queue limit must be positive and finite")
        self.model, self.on_partial, self.on_failed = model, on_partial, on_failed
        self._limit = max(1, round(maximum_pending_seconds * 16000))
        self._queue = queue.SimpleQueue()
        self._lock = threading.Lock()
        self._discard = threading.Event()
        self._thread = self._stream = self._result = None
        self._started = self._accepting = self._requested = self._failed = False
        self._pending = self._samples = 0
        self._text = ""
        self._failure_reason = None

    def start(self):
        if self._started:
            raise RuntimeError("A preview session belongs to one recording")
        self._started = True
        try:
            self._stream = self.model.create_session(self._publish)  # Before microphone capture.
            self._thread = threading.Thread(target=self._run, name="Saydraft-preview", daemon=True)
            self._accepting = not self._requested
            self._thread.start()
            return True
        except Exception:
            self._failed, self._accepting = True, False
            self._failure_reason = "model_unavailable"
            if self._stream is not None:
                try:
                    self._stream.discard()
                except Exception:
                    logger.debug("Live preview cleanup is unavailable")
            self._thread = None
            self._report_failure()
            return False

    def feed(self, audio):
        # Own the data before returning to PortAudio, which can reuse its buffer.
        data = np.array(_to_mono_float32(audio), dtype=np.float32, copy=True)
        if not len(data):
            return False
        with self._lock:
            if not self._accepting:
                return False
            if self._pending + len(data) > self._limit:
                self._failed = True
                self._failure_reason = "queue_overflow"
                self._accepting = False
                if not self._requested:
                    self._requested = True
                    self._queue.put(_STOP)
                return False
            self._pending += len(data)
            self._samples += len(data)
            self._queue.put(data)
            return True

    def _publish(self, text):
        if text.strip():
            self._text = text
        if self._discard.is_set() or self._failed:
            return
        try:
            self.on_partial(text)
        except Exception:
            logger.debug("Live preview receiver is unavailable")

    def request_finish(self, *, discard=False):
        """Signal first; final-ASR tail work can run while preview shuts down."""
        with self._lock:
            self._accepting = False
            if discard:
                self._discard.set()
            if not self._requested:
                self._requested = True
                self._queue.put(_STOP)

    def finish(self, *, discard=False):
        if not self._started:
            raise RuntimeError("Start preview before finishing it")
        self.request_finish(discard=discard)
        if self._thread is not None:
            self._thread.join()
        if self._result is None:
            self._result = PreviewResult("", True, False, 0, 0, self._failure_reason)
        return self._result

    def _report_failure(self):
        logger.warning("Live preview stopped (%s); normal recognition remains available", self._failure_reason)
        try:
            self.on_failed()
        except Exception:
            logger.debug("Live preview status receiver is unavailable")

    def _run(self):
        complete = False
        try:
            while True:
                data = self._queue.get()
                if data is _STOP:
                    break
                with self._lock:
                    self._pending -= len(data)
                if not self._discard.is_set() and not self._failed:
                    self._stream.feed(data)
            if not self._discard.is_set() and not self._failed:
                self._text = self._stream.finish().strip() or self._text
                complete = bool(getattr(self._stream, "complete", True))
        except Exception as error:
            self._failed = True
            self._failure_reason = f"decoder_{type(error).__name__}"
        finally:
            with self._lock:
                self._accepting = False
            while not self._queue.empty():
                self._queue.get()
            try:
                self._stream.discard()
            except Exception:
                self._failed = True
                self._failure_reason = self._failure_reason or "cleanup_failure"
            self._result = PreviewResult("" if self._discard.is_set() else self._text,
                self._failed, complete and not self._failed and not self._discard.is_set(),
                self._samples, float(getattr(self._stream, "compute_seconds", 0)), self._failure_reason)
            if self._failed:
                self._report_failure()
