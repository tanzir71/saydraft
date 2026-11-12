"""One fixed learning MTA; critical focused-field queries remain independent."""

import math
import threading
import time

from .tracked_edit import (
    CHECK_AFTER, MAX_PREPARATION_LEASE, RETIRE_AFTER, FieldIdentity, TrackedEditReader, valid_inserted,
)


class ObservationTicket:
    """Plain synchronization/data only; never contains an element or text range."""
    def __init__(self, identity, deadline, lease):
        self.ready, self.active, self.done = (threading.Event() for _ in range(3))
        self._identity, self._deadline, self._lease = identity, deadline, lease
        self._stage, self._token, self._text, self._when, self._result = "queued", None, "", None, None


class ObservationWorker:
    def __init__(self, *, factory=None, clock=time.monotonic):
        if factory is None:
            from .uia_native import NativeUIAReader
            factory = NativeUIAReader
        self._factory, self.clock = factory, clock
        self._lock, self._wake, self._stopped = threading.Lock(), threading.Event(), threading.Event()
        self._scope, self._closed = None, False
        self._thread = threading.Thread(target=self._run, name="Saydraft-corrections-UIA", daemon=True)
        self._thread.start()

    @staticmethod
    def _retire(scope):
        if scope is not None:
            scope._stage, scope._text, scope._result = "cancelled", "", None
            scope.ready.set()
            scope.active.set()
            scope.done.set()

    def prepare(self, identity, *, lease_seconds=1260):
        if (not isinstance(identity, FieldIdentity) or not identity.valid()
                or type(lease_seconds) not in (int, float) or not math.isfinite(lease_seconds)
                or not 0 < lease_seconds <= MAX_PREPARATION_LEASE):
            return None
        with self._lock:
            if self._closed:
                return None
            self._retire(self._scope)
            scope = ObservationTicket(identity, self.clock() + 2, self.clock() + lease_seconds)
            self._scope = scope
            self._wake.set()
            return scope

    def reserve(self, scope):
        """Call before OS insertion; a late preparation can never anchor after paste."""
        with self._lock:
            if (not self._closed and scope is not None and self._scope is scope
                    and scope._stage == "prepared" and self.clock() < scope._deadline):
                scope._stage, scope._deadline = "reserved", self.clock() + RETIRE_AFTER
                self._wake.set()
                return True
            if scope is self._scope:
                self._retire(scope)
                self._wake.set()
            return False

    def commit(self, scope, text):
        """Only successful insertion should commit; this call never waits for UIA."""
        with self._lock:
            if (not self._closed and scope is not None and self._scope is scope
                    and scope._stage == "reserved" and self.clock() < scope._deadline
                    and valid_inserted(text)):
                scope._when, scope._text = self.clock(), text
                scope._stage, scope._deadline = "confirming", scope._when + RETIRE_AFTER
                self._wake.set()
                return True
            if scope is self._scope:
                self._retire(scope)
                self._wake.set()
            return False

    def cancel(self, scope):
        with self._lock:
            if scope is not None and self._scope is scope:
                self._retire(scope)
                self._wake.set()

    def take(self, scope):
        with self._lock:
            if (scope is None or self._scope is not scope or scope._stage != "done"
                    or self._closed or self.clock() >= scope._deadline):
                return None
            result = scope._result
            self._retire(scope)
            self._wake.set()
            return result

    def close(self):
        with self._lock:
            self._closed = True
            self._retire(self._scope)
            self._wake.set()
        return self._stopped.is_set()

    def wait_closed(self, timeout):
        return self._stopped.wait(timeout)

    def _current_unlocked(self, scope, stage):
        return (not self._closed and self._scope is scope and scope._stage == stage
            and self.clock() < scope._deadline)

    def _current(self, scope, stage):
        with self._lock:
            return self._current_unlocked(scope, stage)

    def _finish(self, scope, result):
        scope._text = ""
        scope._stage, scope._result = "done", result if result and result.original else None
        scope._deadline = self.clock() + 30  # Bounded retention if the consumer stops polling.
        scope.ready.set()
        scope.active.set()
        scope.done.set()

    def _run(self):
        reader = tracked = active = None
        try:
            reader = self._factory()
            tracked = TrackedEditReader(reader, clock=self.clock)
            while True:
                with self._lock:
                    self._wake.clear()
                    if self._closed:
                        break
                    scope = self._scope
                    if scope is not None and self.clock() >= scope._deadline:
                        self._retire(scope)
                    stage = scope._stage if scope else "cancelled"
                if active is not scope:
                    tracked.clear()
                    active = scope
                if scope is None or stage in ("cancelled", "done"):
                    tracked.clear()
                elif stage == "queued":
                    with self._lock:
                        if self._scope is scope and scope._stage == "queued":
                            scope._stage = "preparing"
                    token = tracked.prepare(scope._identity, lease_seconds=max(.001, scope._lease - self.clock()),
                        current=lambda: self._current(scope, "preparing"))
                    with self._lock:
                        discard = not self._current_unlocked(scope, "preparing")
                        if not discard:
                            if token is None:
                                self._finish(scope, None)
                            else:
                                scope._token, scope._stage, scope._deadline = token, "prepared", scope._lease
                                scope.ready.set()
                    if discard:
                        tracked.clear()
                elif stage == "confirming":
                    result = tracked.commit(scope._token, scope._text, inserted_at=scope._when,
                        current=lambda: self._current(scope, "confirming"))
                    with self._lock:
                        if self._current_unlocked(scope, "confirming"):
                            scope._text = ""
                            if result is None:
                                scope._stage = "watching"
                                scope.active.set()
                            else:
                                self._finish(scope, result)
                        result = None  # Idle owner frames must retain no completed field text.
                elif stage == "watching":
                    result = tracked.check(scope._token, current=lambda: self._current(scope, "watching"))
                    with self._lock:
                        if self._current_unlocked(scope, "watching") and result is not None:
                            self._finish(scope, result)
                        result = None
                with self._lock:
                    delay = None
                    if self._scope is scope and scope is not None:
                        if scope._stage in ("queued", "confirming"):
                            delay = 0
                        elif scope._stage == "watching":
                            delay = .25
                            if self.clock() < scope._when + CHECK_AFTER:
                                delay = min(delay, scope._when + CHECK_AFTER - self.clock())
                        elif scope._stage in ("prepared", "reserved", "done"):
                            delay = max(0, scope._deadline - self.clock())
                    if self._scope is not scope:
                        delay = 0
                self._wake.wait(delay)
        except Exception:
            pass  # No provider messages or field content enter logs.
        finally:
            if tracked is not None:
                tracked.clear()
            if reader is not None:
                try:
                    reader.close()
                except Exception:
                    pass
            with self._lock:
                self._closed = True
                self._retire(self._scope)
            self._stopped.set()
