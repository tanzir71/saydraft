"""Serialize Bar listener startup and control changes away from the GUI thread."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import threading

from .bar_status import BarPhase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Request:
    epoch: int
    bar_generation: int


class BarActions:
    def __init__(self, core, *, changed=lambda: None, executor=None):
        self.core, self.changed = core, changed
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="Saydraft-Bar-control")
        self._lock = threading.RLock()
        self._epoch = 0
        self._pending = None
        self._resumed = None
        self.closed = False

    @property
    def pending(self):
        with self._lock:
            return self._pending is not None

    def _current(self, request):
        with self._lock:
            return not self.closed and not self.core._closing and request.epoch == self._epoch

    def _submit(self, callback, *args):
        try:
            self.executor.submit(self._run, callback, args)
            return True
        except RuntimeError:
            return False

    def _run(self, callback, args):
        try:
            callback(*args)
        except Exception:
            logger.warning("Bar listener control unavailable")
            if not self.closed:
                self.core.emit("notification_requested", "Could not update listening or Settings. Check Settings and try again.")
                self.changed()

    def request_start(self):
        with self._lock:
            if self.closed or self._pending is not None or self.core.busy or self.core._closing:
                return False
            self._epoch += 1
            request = _Request(self._epoch, self.core.bar_status.begin())
            self._pending = request
        if not self._submit(self._start, request):
            self._finished(request)
            return False
        return True

    def _stop_owned_resume(self, controller):
        if controller is not None and self.core.hotkeys._controller is controller:
            try:
                self.core.hotkeys.stop()
            except Exception:
                logger.warning("Bar listener teardown unavailable; request admission remains closed")
            finally:
                self.changed()

    def _start(self, request):
        resumed = None
        queued = False
        try:
            if not self._current(request):
                return
            if not self.core.hotkeys.enabled:
                self.core.hotkeys.start(valid=lambda: self._current(request))
                if self.core.hotkeys.enabled:
                    resumed = self.core.hotkeys._controller
                    with self._lock:
                        if self._pending == request:
                            self._resumed = resumed
                    self.changed()
            if not self._current(request):
                self._stop_owned_resume(resumed)
                return
            queued = self.core.hotkeys._controller.request_hands_free(
                valid=lambda: self._current(request), finished=lambda: self._finished(request))
            if not queued:
                self._failed(request)
                self._stop_owned_resume(resumed)
        except Exception:
            logger.warning("Bar listener startup unavailable")
            self._failed(request)
            self._stop_owned_resume(resumed)
        finally:
            if not queued:
                self._finished(request)

    def _failed(self, request):
        if self._current(request) and self.core.bar_status.is_current(request.bar_generation):
            self.core.emit("notification_requested", "Could not start listening. Check shortcuts in Settings and try again.")

    def _finished(self, request):
        with self._lock:
            if self._pending == request:
                self._pending = None
                self._resumed = None
        # An accepted capture has its own newer Bar generation. A refused or
        # cancelled queued action must not leave the earlier preparing state up.
        self.core.bar_status.publish(request.bar_generation, BarPhase.IDLE)

    def _abort(self):
        with self._lock:
            self._epoch += 1
            owned = self._resumed
            self._pending = self._resumed = None
        self.core.hotkeys.revoke_requests()
        self.core._cancel_request.set()
        self.core.bar_status.cancel()
        return owned

    def cancel_pending(self):
        owned = self._abort()
        self._submit(self._cancel, owned)

    def _cancel(self, owned):
        self.core.cancel()
        self._stop_owned_resume(owned)

    def start_listening(self):
        if self.pending:
            owned = self._abort()
            self._submit(self._cancel, owned)
        self._submit(self._listen)

    def _listen(self):
        if not self.closed and not self.core._closing:
            self.core.hotkeys.start()
            self.changed()

    def stop_listening(self):
        self._abort()
        self._submit(self._stop)

    def _stop(self):
        self.core.cancel()
        self.core.hotkeys.stop()
        self.changed()

    def configure(self, config):
        if self.pending and not self.core.busy:
            owned = self._abort()
            self._submit(self._cancel, owned)
        self._submit(self._configure, config)

    def _configure(self, config):
        if not self.closed and not self.core._closing:
            self.core.configure(config)
            self.changed()

    def close(self):
        with self._lock:
            if self.closed:
                return
            self.closed = True
            self.core._closing = True
        self._abort()
        self._submit(self.core.shutdown)
        self.executor.shutdown(wait=False, cancel_futures=False)
