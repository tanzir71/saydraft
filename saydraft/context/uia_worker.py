"""One windowless MTA owner and one request; caller timeout never spawns more work."""

import threading
import time
from dataclasses import dataclass, field, replace
import math

from .focused_edit import FocusedEdit, read_focused_edit
from .selection import MAX_SELECTION_LEASE, SelectionSnapshot, SelectionTracker
from .tracked_edit import FieldIdentity


@dataclass
class _Request:
    window: int
    include_text: bool
    deadline: float
    done: threading.Event = field(default_factory=threading.Event)
    result: object | None = None
    abandoned: bool = False
    operation: str = "context"
    process_id: int | None = None
    lease_seconds: float = 1260
    snapshot: SelectionSnapshot | None = None
    for_write: bool = True
    selection_epoch: int = 0


class BoundedUIA:
    def __init__(self, *, factory=None, timeout=.2, capture_timeout=None):
        if type(timeout) not in (int, float) or not 0 < timeout <= .5:
            raise ValueError("UIA caller timeout must be at most half a second")
        capture_timeout = timeout if capture_timeout is None else capture_timeout
        if type(capture_timeout) not in (int, float) or not 0 < capture_timeout <= .5:
            raise ValueError("UIA capture timeout must be at most half a second")
        if factory is None:
            from .uia_native import NativeUIAReader  # Import before starting the MTA owner.
            factory = NativeUIAReader
        self._factory, self.timeout = factory, timeout
        self.capture_timeout = capture_timeout
        self._lock, self._wake, self._stopped = threading.Lock(), threading.Event(), threading.Event()
        self._closed, self._request = False, None
        self._selection_epoch, self._clear_selection = 0, False
        self._thread = threading.Thread(target=self._run, name="Saydraft-UIA", daemon=True)
        self._thread.start()

    def query(self, window, *, include_text=True):
        if type(window) is not int or not 0 < window < 2**64 or type(include_text) is not bool:
            return FocusedEdit()
        budget = self.capture_timeout if include_text else self.timeout
        request = _Request(window, include_text, time.monotonic() + budget)
        return self._submit(request, FocusedEdit())

    def capture_selection(self, window, process_id, *, lease_seconds=1260):
        if (type(window) is not int or not 0 < window < 2**64
                or type(process_id) is not int or not 0 < process_id < 2**32
                or type(lease_seconds) not in (int, float) or not math.isfinite(lease_seconds)
                or not 0 < lease_seconds <= MAX_SELECTION_LEASE):
            return SelectionSnapshot()
        request = _Request(window, True, time.monotonic() + self.capture_timeout,
                           operation="capture_selection", process_id=process_id, lease_seconds=lease_seconds)
        return self._submit(request, SelectionSnapshot())

    def verify_selection(self, snapshot, *, for_write=True):
        if (type(snapshot) is not SelectionSnapshot or type(snapshot.identity) is not FieldIdentity
                or not snapshot.identity.valid() or type(for_write) is not bool or snapshot.status != "ready"
                or type(snapshot.generation) is not int or type(snapshot.ticket) is not int or snapshot.ticket <= 0):
            return "selection_expired"
        request = _Request(snapshot.identity.window, True, time.monotonic() + self.capture_timeout,
                           operation="verify_selection", snapshot=snapshot, for_write=for_write)
        return self._submit(request, "field_unavailable")

    def cancel_selection(self, snapshot=None):
        """Nonblocking revocation; stale completion cleanup cannot cancel a newer lease."""
        with self._lock:
            if self._closed:
                return False
            if snapshot is not None and (type(snapshot) is not SelectionSnapshot
                    or type(snapshot.generation) is not int or snapshot.generation != self._selection_epoch):
                return False
            self._selection_epoch += 1
            self._clear_selection = True
            if self._request is not None and self._request.operation != "context":
                self._request.abandoned, self._request.result = True, None
                self._request.done.set()
            self._wake.set()
        return True

    def _submit(self, request, fallback):
        with self._lock:
            if self._closed or self._request is not None:
                return fallback
            if request.operation == "capture_selection":
                self._selection_epoch += 1
                self._clear_selection = True
            elif request.operation == "verify_selection" and request.snapshot.generation != self._selection_epoch:
                return "selection_expired"
            request.selection_epoch = self._selection_epoch
            self._request = request
            self._wake.set()
        request.done.wait(max(0, request.deadline - time.monotonic()))
        with self._lock:
            result = request.result
            request.result = None
            request.abandoned = True
            valid = (not self._closed and result is not None and time.monotonic() <= request.deadline
                     and (request.operation == "context" or request.selection_epoch == self._selection_epoch))
            if not valid and request.operation != "context" and request.selection_epoch == self._selection_epoch:
                self._selection_epoch += 1
                self._clear_selection = True
                self._wake.set()
            return result if valid else fallback

    def close(self):
        """Signal retirement without joining a provider that may need the GUI."""
        with self._lock:
            self._closed = True
            self._selection_epoch += 1
            self._clear_selection = True
            if self._request is not None:
                self._request.abandoned, self._request.result = True, None
                self._request.done.set()
            self._wake.set()
        return self._stopped.is_set()

    def wait_closed(self, timeout):
        """QA/background use only; GUI shutdown uses nonblocking close()."""
        return self._stopped.wait(timeout)

    def _current(self, request):
        with self._lock:
            return (not self._closed and not request.abandoned and self._request is request
                    and time.monotonic() < request.deadline
                    and (request.operation == "context" or request.selection_epoch == self._selection_epoch))

    def _run(self):
        reader = tracker = None
        try:
            reader = self._factory()
            tracker = SelectionTracker(reader)
            while True:
                expires = tracker.expires_at
                self._wake.wait(None if expires is None else max(0, expires - time.monotonic()))
                tracker.expire()  # Retirement reads no field content.
                with self._lock:
                    self._wake.clear()
                    clear, closed = self._clear_selection, self._closed
                    self._clear_selection = False
                    request = self._request
                if clear or closed:
                    tracker.clear()
                if closed:
                    break
                if request is None:
                    continue
                result = FocusedEdit()
                if self._current(request):
                    def current(request=request):
                        return self._current(request)
                    if request.operation == "capture_selection":
                        result = replace(tracker.begin(request.window, request.process_id,
                            lease_seconds=request.lease_seconds, current=current), generation=request.selection_epoch)
                    elif request.operation == "verify_selection":
                        result = tracker.verify(request.snapshot, for_write=request.for_write, current=current)
                    else:
                        result = read_focused_edit(reader, request.window, include_text=request.include_text, current=current)
                with self._lock:
                    accepted = (not self._closed and not request.abandoned and time.monotonic() <= request.deadline
                                and (request.operation == "context" or request.selection_epoch == self._selection_epoch))
                    if accepted:
                        request.result = result
                    self._request = None
                    request.done.set()
                if not accepted and request.operation != "context":
                    tracker.clear()
                result = request = None  # Idle workers retain no completed field content.
        except Exception:
            pass  # No provider error/partial content crosses the boundary or enters logs.
        finally:
            if tracker is not None:
                tracker.clear()
            if reader is not None:
                try:
                    reader.close()
                except Exception:
                    pass
            with self._lock:
                self._closed = True
                if self._request is not None:
                    self._request.result = None
                    self._request.done.set()
                    self._request = None
            self._stopped.set()
