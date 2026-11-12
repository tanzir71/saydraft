"""One windowless MTA owner and one request; caller timeout never spawns more work."""

import threading
import time
from dataclasses import dataclass, field

from .focused_edit import FocusedEdit, read_focused_edit


@dataclass
class _Request:
    window: int
    include_text: bool
    deadline: float
    done: threading.Event = field(default_factory=threading.Event)
    result: FocusedEdit | None = None
    abandoned: bool = False


class BoundedUIA:
    def __init__(self, *, factory=None, timeout=.2):
        if type(timeout) not in (int, float) or not 0 < timeout <= .5:
            raise ValueError("UIA caller timeout must be at most half a second")
        if factory is None:
            from .uia_native import NativeUIAReader  # Import before starting the MTA owner.
            factory = NativeUIAReader
        self._factory, self.timeout = factory, timeout
        self._lock, self._wake, self._stopped = threading.Lock(), threading.Event(), threading.Event()
        self._closed, self._request = False, None
        self._thread = threading.Thread(target=self._run, name="Saydraft-UIA", daemon=True)
        self._thread.start()

    def query(self, window, *, include_text=True):
        if type(window) is not int or not 0 < window < 2**64 or type(include_text) is not bool:
            return FocusedEdit()
        request = _Request(window, include_text, time.monotonic() + self.timeout)
        with self._lock:
            if self._closed or self._request is not None:
                return FocusedEdit()
            self._request = request
            self._wake.set()
        request.done.wait(max(0, request.deadline - time.monotonic()))
        with self._lock:
            result = request.result
            request.result = None
            request.abandoned = True
            return result if not self._closed and result is not None and time.monotonic() <= request.deadline else FocusedEdit()

    def close(self):
        """Signal retirement without joining a provider that may need the GUI."""
        with self._lock:
            self._closed = True
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
                    and time.monotonic() < request.deadline)

    def _run(self):
        reader = None
        try:
            reader = self._factory()
            while True:
                self._wake.wait()
                with self._lock:
                    self._wake.clear()
                    if self._closed:
                        break
                    request = self._request
                if request is None:
                    continue
                result = FocusedEdit()
                if not request.abandoned and time.monotonic() < request.deadline:
                    result = read_focused_edit(reader, request.window, include_text=request.include_text,
                                               current=lambda: self._current(request))
                with self._lock:
                    if not self._closed and not request.abandoned and time.monotonic() <= request.deadline:
                        request.result = result
                    self._request = None
                    request.done.set()
                result = request = None  # Idle workers retain no completed field content.
        except Exception:
            pass  # No provider error/partial content crosses the boundary or enters logs.
        finally:
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
