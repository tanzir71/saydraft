"""A revocable Command editor on the cleaner's exclusive native process slot."""

import logging
import math
import threading
import time

from saydraft.cleanup.llm.edit import EditClient, EditReply

logger = logging.getLogger(__name__)


class CommandModelSession:
    def __init__(self, owner, config, model_id, *, manager_factory, clock=time.monotonic):
        self.owner, self.config, self.model_id = owner, config, model_id
        self._factory, self._clock = manager_factory, clock
        self._lock, self._closed = threading.Lock(), threading.Event()
        self._manager = None
        self._closing = False

    def _current(self):
        return not self._closed.is_set() and not self.owner._closed and self.owner._command is self

    def _get_manager(self):
        with self._lock:
            if not self._current():
                return None
            if self._manager is None:
                self._manager = self._factory(self.config)
            return self._manager

    def prepare(self, *, cancelled=lambda: False, timeout=65):
        """Wait off the GUI thread; cancel/close never joins a native starter."""
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 185:
            raise ValueError("Command startup budget must be positive and bounded")
        prepared = False
        try:
            if cancelled() or not self._current():
                self.close()
                return "cancelled"
            manager = self._get_manager()
            if manager is None:
                return "cancelled"
            deadline = self._clock() + timeout
            manager.warm()
            while self._current() and not cancelled():
                state = manager.status
                if not self._current() or cancelled():
                    return "cancelled"
                if state["state"] == "ready":
                    prepared = self._current() and not cancelled()
                    return "ready" if prepared else "cancelled"
                if state["state"] in ("closed", "missing", "failed"):
                    return "unavailable"
                remaining = deadline - self._clock()
                if remaining <= 0:
                    return "startup_timeout"
                self._closed.wait(min(.05, remaining))
            return "cancelled"
        except Exception:
            logger.warning("Command model preparation unavailable")
            return "unavailable" if self._current() and not cancelled() else "cancelled"
        finally:
            # Failed/cancelled preparation cannot keep a retry timer or a native
            # starter alive on behalf of an abandoned instruction session.
            if not prepared or not self._current() or cancelled():
                self.close()

    def edit_selection(self, selection, instruction, *, cancelled=lambda: False, timeout=45):
        def retired():
            return cancelled() or not self._current()
        if retired():
            return EditReply(None, "cancelled")
        try:
            manager = self._get_manager()
            if manager is None or retired():
                return EditReply(None, "cancelled")
            reply = EditClient(manager, clock=self._clock).edit(
                selection, instruction, timeout=timeout, cancelled=retired)
            return EditReply(None, "cancelled") if retired() else reply
        except Exception:
            logger.warning("Command edit unavailable; no replacement delivered")
            return EditReply(None, "cancelled" if retired() else "unavailable")

    def close(self):
        self._closed.set()
        with self._lock:
            if self._closing:
                return
            self._closing = True
            manager, self._manager = self._manager, None
        try:
            if manager is not None:
                manager.close()
        finally:
            self.owner._release_command(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
