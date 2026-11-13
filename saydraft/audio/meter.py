"""An explicit level-only input test; no audio buffers survive a callback."""

from functools import partial
import math
import threading
import time

import numpy as np

from .devices import InputSelection, selected_input_stream


class InputMeter:
    def __init__(self, selection=InputSelection(), *, on_level=lambda level: None,
                 on_finished=lambda: None, stream_factory=None, clock=time.monotonic, level_hz=20):
        self.selection, self.on_level, self.on_finished = selection, on_level, on_finished
        self.factory = stream_factory or partial(selected_input_stream, selection)
        self.clock, self.interval, self._last = clock, 1 / level_hz, None
        self._stream, self._closed = None, False
        self._accepting = threading.Event()

    def start(self):
        if self._closed:
            raise RuntimeError("Input test is closed")
        self._stream = self.factory(samplerate=16000, channels=1, dtype="float32", blocksize=0,
            device=self.selection.name or None, callback=self._audio, finished_callback=self._finished)
        self._accepting.set()
        try:
            self._stream.start()
        except BaseException:
            self.stop()
            raise

    def _audio(self, samples, _frames, _time, _status):
        if not self._accepting.is_set():
            return
        now = self.clock()
        if self._last is not None and now - self._last < self.interval:
            return
        self._last = now
        values = np.asarray(samples)
        level = float(np.sqrt(np.mean(np.square(values, dtype=np.float64)))) if values.size else 0.
        level = min(1., max(0., level)) if math.isfinite(level) else 0.
        try:
            self.on_level(level)
        except Exception:
            pass

    def _finished(self):
        if self._accepting.is_set():
            self.on_finished()

    def stop(self):
        self._closed = True
        self._accepting.clear()
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
