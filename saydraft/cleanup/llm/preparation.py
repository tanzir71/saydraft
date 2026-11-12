"""One background worker prepares a static chat prefix for the latest style."""

import threading
import time

from .prompts import PromptHints


def _key(hints):
    return (hints.style, hints.post_rules, hints.app[:120] if isinstance(hints.app, str) else "",
            hints.group[:40] if isinstance(hints.group, str) else "")


class PromptPreparation:
    def __init__(self, client, *, thread_factory=threading.Thread, clock=time.monotonic):
        self.client, self._thread_factory, self._clock = client, thread_factory, clock
        self._lock = threading.RLock()
        self._closed = self._running = False
        self._wanted = self._prepared = self._failed = None
        self._reason, self._seconds = "not_prepared", None
        self._settled = threading.Event()
        self._settled.set()

    @property
    def status(self):
        generation = self.client.manager.generation
        with self._lock:
            prepared = self._prepared is not None and self._prepared[0] == generation and generation is not None
            return {"state": "closed" if self._closed else "warming" if self._running else
                    "prepared" if prepared else "unprepared", "reason": self._reason if not self._prepared
                    or prepared or self._closed else "instance_changed", "prompt_seconds": self._seconds if prepared else None}

    def wait(self, timeout):
        """For explicit setup/probes; interactive cleanup never waits here."""
        return self._settled.wait(timeout)

    def ready(self, hints):
        generation = self.client.manager.generation
        with self._lock:
            return (not self._closed and not self._running and generation is not None
                    and self._prepared == (generation, _key(hints)))

    def request(self, hints):
        # Only bounded app/style metadata; never caret, glossary or dictation.
        key = _key(hints)
        PromptHints(style=key[0], post_rules=key[1])
        if self.ready(hints):
            return True
        generation = self.client.manager.generation
        with self._lock:
            if self._closed:
                return False
            if generation is not None and self._failed == (generation, key):
                return False  # Do not repeatedly probe a broken protocol in one instance.
            self._wanted, self._prepared = key, None
            if self._running:
                return True
            self._running, self._reason = True, "prompt_warming"
            self._settled.clear()
            try:
                self._thread_factory(target=self._work, name="Saydraft-prompt-warmup", daemon=True).start()
            except Exception:
                self._prepared, self._running, self._reason = None, False, "prompt_prepare_failed"
                self._settled.set()
                return False
            return True

    def _work(self):
        try:
            while True:
                with self._lock:
                    if self._closed:
                        self._running = False
                        self._settled.set()
                        return
                    key = self._wanted
                manager = self.client.manager
                seconds = None
                if not manager.prepare():
                    reason, generation = "model_not_ready", None
                else:
                    generation = manager.generation
                    with self._lock:
                        self._reason = "decoder_calibrating"
                    reason = self.client.calibrate_decoder(timeout=60).reason
                    if reason == "calibrated":
                        with self._lock:
                            if self._closed:
                                self._running = False
                                self._settled.set()
                                return
                            key, self._reason = self._wanted, "prompt_warming"
                        started = self._clock()
                        reply = self.client.prepare_prompt(style=key[0], post_rules=key[1],
                                                           app=key[2], group=key[3], timeout=60)
                        seconds = self._clock() - started
                        reason = reply.reason
                current = manager.generation
                if reason == "prepared" and (generation is None or generation != current):
                    reason = "instance_changed"
                with self._lock:
                    if self._closed:
                        self._running = False
                        self._settled.set()
                        return
                    valid = reason == "prepared" and generation is not None and generation == current
                    self._prepared = (generation, key) if valid else None
                    self._failed = ((generation, key) if not valid and generation is not None
                                    and reason not in ("busy", "not_ready", "model_not_ready") else None)
                    self._reason = reason if not valid or self._wanted == key else "prompt_warming"
                    self._seconds = seconds if valid else None
                    if not valid or self._wanted == key:
                        self._running = False
                        self._settled.set()
                        return
        except Exception:
            with self._lock:
                self._prepared, self._running = None, False
                if not self._closed:
                    self._reason = "prompt_prepare_failed"
                self._settled.set()

    def close(self):
        with self._lock:
            self._closed, self._prepared, self._wanted = True, None, None
            self._reason = "closed"
            self._settled.set()
