"""One cancellable background retention owner per applied configuration."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import threading

from saydraft.data.retention import AudioRetentionResult, expire_recordings


@dataclass(frozen=True)
class AudioRetentionUpdate:
    policy: object
    state: str
    result: AudioRetentionResult | None = None
    generation: int = 0


class AudioRetention:
    def __init__(self, history, audio, policy, *, changed=lambda update:None, timer_factory=threading.Timer,
                 sweep=expire_recordings):
        self.history,self.audio,self.policy,self.changed = history,audio,policy,changed
        self.timer_factory,self.sweep = timer_factory,sweep
        self._lock = threading.Lock()
        self._closed = self._running = False
        self._cancel = threading.Event()
        self._pool = self._timer = None

    def request(self):
        with self._lock:
            if self._closed or self._running or not self.policy.expires:
                return False
            self._running = True
            timer,self._timer = self._timer,None
            if self._pool is None:
                self._pool = ThreadPoolExecutor(max_workers=1,thread_name_prefix="Saydraft-audio-expiry")
        if timer is not None:
            timer.cancel()
        self.changed(AudioRetentionUpdate(self.policy,"working"))
        try:
            self._pool.submit(self._run)
        except Exception:
            with self._lock:
                self._running = False
            self.changed(AudioRetentionUpdate(self.policy,"failed"))
            return False
        return True

    def _run(self):
        result,state = None,"failed"
        try:
            result = self.sweep(self.history,self.audio,self.policy,cancelled=self._cancel.is_set)
            state = "ready"
        except Exception:
            pass  # No saved text, paths or backend exception details enter feedback.
        with self._lock:
            self._running = False
            closed = self._closed
        if closed:
            if result is not None and (result.removed or result.unavailable):
                self.changed(AudioRetentionUpdate(self.policy,"retired",result))
        else:
            self.changed(AudioRetentionUpdate(self.policy,state,result))
            timer = self.timer_factory(900,self.request)
            timer.daemon = True
            with self._lock:
                if self._closed or self._running:
                    return
                self._timer = timer
            timer.start()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._cancel.set()
            timer,pool = self._timer,self._pool
            self._timer = None
        if timer is not None:
            timer.cancel()
        if pool is not None:
            pool.shutdown(wait=False,cancel_futures=True)
