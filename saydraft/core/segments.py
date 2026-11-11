"""Transcribe completed speech segments while capture continues.

The audio callback only copies and queues chunks. One background thread performs
VAD and serial ASR. Split at silence, never in a word; continuous speech remains
one segment and therefore still incurs full recognition at release.
"""

from __future__ import annotations

import logging
import math
import queue
import threading
import time
from dataclasses import dataclass

import numpy as np

from saydraft.audio.vad import SilenceTrimConfig, SpeechFrameDetector
from .interfaces import AsrEngine

logger = logging.getLogger(__name__)
_STOP = object()


@dataclass(frozen=True)
class SegmentResult:
    text: str
    segments: int
    failed: bool
    samples: int
    tail_seconds: float
    background_asr_seconds: float


class SegmentTranscriber:
    def __init__(self, asr: AsrEngine, *, sample_rate=16_000, silence_seconds=0.6,
                 minimum_seconds=0.5, detector=None, clock=time.perf_counter,
                 energy_threshold=0.003, aggressiveness=2):
        if sample_rate != 16_000:
            raise ValueError("background transcription requires mono 16 kHz input")
        if not all(math.isfinite(value) and value > 0 for value in (silence_seconds, minimum_seconds)):
            raise ValueError("segment durations must be positive and finite")
        self.asr = asr
        self.sample_rate = sample_rate
        self.silence_samples = round(silence_seconds * sample_rate)
        self.minimum_samples = round(minimum_seconds * sample_rate)
        self.frame_samples = round(0.03 * sample_rate)
        self.detector = detector or SpeechFrameDetector(SilenceTrimConfig(
            sample_rate=sample_rate, energy_threshold=energy_threshold, aggressiveness=aggressiveness))
        self.clock = clock
        self._queue = queue.SimpleQueue()
        self._lock = threading.Lock()
        self._thread = None
        self._accepting = False
        self._cancelled = threading.Event()
        self._parts = []
        self._segment_samples = 0
        self._quiet_samples = 0
        self._speech_seen = False
        self._pending = np.empty(0, dtype=np.float32)
        self._texts = []
        self._failed = False
        self._samples = 0
        self._asr_seconds = 0.0
        self._result = None

    def start(self):
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("a segment transcriber belongs to one recording")
            self._accepting = True
            self._thread = threading.Thread(target=self._run, name="Saydraft-segments", daemon=True)
            self._thread.start()

    @property
    def completed_segments(self):
        return len(self._texts)

    def feed(self, audio) -> bool:
        chunk = np.array(audio, dtype=np.float32, copy=True).reshape(-1)
        with self._lock:
            if not self._accepting:
                return False
            self._samples += len(chunk)
            self._queue.put(chunk)
            return True

    def finish(self, *, discard=False) -> SegmentResult:
        if self._result is not None:
            return self._result
        if self._thread is None:
            raise RuntimeError("start background transcription before finishing it")
        started = self.clock()
        with self._lock:
            self._accepting = False
            if discard:
                self._cancelled.set()
            self._queue.put(_STOP)
        self._thread.join()
        while not self._queue.empty():
            self._queue.get()
        self._parts.clear()
        self._pending = np.empty(0, dtype=np.float32)
        self._result = SegmentResult(
            text="" if discard else " ".join(text for text in self._texts if text),
            segments=len(self._texts), failed=self._failed, samples=self._samples,
            tail_seconds=self.clock() - started, background_asr_seconds=self._asr_seconds,
        )
        return self._result

    def _run(self):
        try:
            while True:
                chunk = self._queue.get()
                if chunk is _STOP:
                    break
                if self._cancelled.is_set():
                    continue
                waveform = np.concatenate((self._pending, chunk))
                full_frames = len(waveform) // self.frame_samples
                for index in range(full_frames):
                    start = index * self.frame_samples
                    self._consume(waveform[start:start + self.frame_samples])
                self._pending = waveform[full_frames * self.frame_samples:]
            if not self._cancelled.is_set():
                if len(self._pending):
                    self._consume(self._pending)
                self._transcribe_segment()
        except Exception:
            self._failed = True
            logger.warning("Background recognition failed; full recording is available for fallback")
            logger.debug("Background recognition failure detail", exc_info=True)

    def _consume(self, frame):
        self._parts.append(frame)
        self._segment_samples += len(frame)
        analysis_frame = frame if len(frame) == self.frame_samples else np.pad(
            frame, (0, self.frame_samples - len(frame)))
        speech = bool(self.detector(analysis_frame))
        self._speech_seen = self._speech_seen or speech
        self._quiet_samples = 0 if speech else self._quiet_samples + len(frame)
        if self._quiet_samples >= self.silence_samples and self._segment_samples >= self.minimum_samples:
            self._transcribe_segment()

    def _transcribe_segment(self):
        if self._speech_seen and self._parts and not self._cancelled.is_set():
            audio = np.concatenate(self._parts)
            started = self.clock()
            try:
                text = self.asr.transcribe(audio).strip()
                self._texts.append(text)
                if not text:
                    self._failed = True
            except Exception:
                self._failed = True
                logger.warning("A background segment needs full-recording fallback")
                logger.debug("Segment failure detail", exc_info=True)
            finally:
                self._asr_seconds += self.clock() - started
        self._parts.clear()
        self._segment_samples = 0
        self._quiet_samples = 0
        self._speech_seen = False
