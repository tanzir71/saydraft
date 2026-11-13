"""Serial, generation-scoped ownership of an explicit microphone level test."""

import threading


class MicrophoneTest:
    def __init__(self, *, schedule, emit, timer_factory=threading.Timer, factory=None, finished=lambda: None):
        self.schedule, self.emit, self.timer_factory = schedule, emit, timer_factory
        self.factory, self.finished = factory, finished
        self._lock = threading.Lock()
        self.generation, self.active, self._starting, self._closed = 0, False, False, False
        self._cancel = threading.Event()
        self._meter = self._timer = None
        self._stop_queued = False

    def start(self, selection):
        with self._lock:
            if self.active or self._closed:
                return 0
            self.generation += 1
            generation = self.generation
            cancel = self._cancel = threading.Event()
            self.active = self._starting = True
            self._stop_queued = False
        self.emit("microphone_test_status", generation, "starting")
        try:
            self.schedule(self._start, generation, cancel, selection)
        except Exception:
            self._retire(generation, "failed")
            return 0
        return generation

    def _level(self, generation, cancel, level):
        if not cancel.is_set() and not self._closed and self.generation == generation:
            self.emit("microphone_test_level", generation, level)

    def _start(self, generation, cancel, selection):
        meter, published, failed = None, False, False
        try:
            if cancel.is_set() or self._closed:
                return
            from saydraft.audio.meter import InputMeter
            meter = (self.factory or InputMeter)(selection,
                on_level=lambda level: self._level(generation, cancel, level),
                on_finished=lambda: self.stop(generation, failed=True))
            if cancel.is_set() or self._closed:
                return
            meter.start()
            with self._lock:
                if cancel.is_set() or self._closed or generation != self.generation:
                    return
                self._meter, self._starting, published = meter, False, True
            self.emit("microphone_test_status", generation, "listening")
            timer = self.timer_factory(10, lambda: self.stop(generation))
            timer.daemon = True
            with self._lock:
                if cancel.is_set() or not self.active:
                    return
                self._timer = timer
            timer.start()
        except Exception:
            failed = True
        finally:
            if not published:
                if meter is not None:
                    try:
                        meter.stop()
                    except Exception:
                        failed = True
                self._retire(generation, "failed" if failed else "stopped")
            elif failed:
                self.stop(generation, failed=True)

    def stop(self, generation=None, *, failed=False):
        with self._lock:
            if not self.active or generation not in (None, self.generation):
                return False
            generation = self.generation
            self._cancel.set()
            if self._stop_queued:
                return True
            self._stop_queued = True
        try:
            self.schedule(self._stop, generation, failed)
        except Exception:
            # A retiring executor must not leave a device open or block the GUI.
            threading.Thread(target=self._stop, args=(generation, failed), daemon=True,
                name="Saydraft-meter-close").start()
        return True

    def _stop(self, generation, failed):
        with self._lock:
            if generation != self.generation or not self.active or self._starting:
                return  # A cancelled start retires its local device before returning.
            meter, self._meter = self._meter, None
        if meter is not None:
            try:
                meter.stop()
            except Exception:
                failed = True
        self._retire(generation, "failed" if failed else "stopped")

    def _retire(self, generation, state):
        with self._lock:
            if generation != self.generation:
                return
            self.active = self._starting = False
            self._cancel.set()
            timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()
        self.emit("microphone_test_status", generation, state)
        self.finished()

    def close(self):
        self._closed = True
        self.stop()
