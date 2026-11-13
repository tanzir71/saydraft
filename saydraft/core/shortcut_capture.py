"""One explicit shortcut-learning lease with observed native teardown."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import threading
import time

from saydraft.hotkeys.capture import ChordCapture, MAX_CAPTURE_SECONDS, OwnedWindowGuard
from saydraft.hotkeys.chords import Chord
from saydraft.hotkeys.llhook import LowLevelHooks


@dataclass
class _Lease:
    generation: int
    window: int
    valid: object
    cancelled: threading.Event = field(default_factory=threading.Event)
    owner: object = None
    timer: object = None
    finishing: bool = False
    revoked: bool = False
    foreground: object = None


class ShortcutCapture:
    def __init__(self, *, emit, finished=lambda: None, executor=None, hooks_factory=LowLevelHooks,
                 guard_factory=OwnedWindowGuard, timer_factory=threading.Timer, clock=time.monotonic):
        self.emit_callback, self.finished = emit, finished
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="Saydraft-shortcut-learn")
        self.hooks_factory, self.guard_factory = hooks_factory, guard_factory
        self.timer_factory, self.clock = timer_factory, clock
        self._lock = threading.RLock()
        self._lease = None
        self.generation = 0
        self.closed = False

    @property
    def active(self):
        with self._lock:
            return self._lease is not None

    def emit(self, *args):
        try:
            self.emit_callback(*args)
        except Exception:
            pass  # A disappeared UI does not become permission to strand hooks.

    def start(self, window, valid):
        with self._lock:
            if self.closed or self._lease is not None or type(window) is not int or window <= 0 or not callable(valid):
                return 0
            self.generation += 1
            lease = self._lease = _Lease(self.generation, window, valid)
            self.emit("shortcut_capture_status", lease.generation, "preparing", "")
            try:
                self.executor.submit(self._start, lease)
            except Exception:
                self._lease = None
                self.emit("shortcut_capture_status", lease.generation, "failed", "")
                return 0
            return lease.generation

    def _current(self, lease):
        return not self.closed and self._lease is lease and not lease.cancelled.is_set()

    def _start(self, lease):
        try:
            if not self._current(lease) or not lease.valid():
                self._request_finish(lease, "cancelled")
                return
            lease.foreground = self.guard_factory(lease.window)
            capture = ChordCapture(valid=lambda: self._current(lease) and lease.valid() and lease.foreground(), clock=self.clock)
            lease.owner = self.hooks_factory((), matcher=capture,
                on_action=lambda value, _when: self._request_finish(lease, value.phase, value.name),
                on_failure=lambda _reason: self._request_finish(lease, "failed"))
            if not self._current(lease):
                self._request_finish(lease, "cancelled")
                return
            lease.owner.start()
            if not self._current(lease):
                return  # Cancellation/completion already queued teardown behind this startup.
            seconds = min(MAX_CAPTURE_SECONDS, max(0, capture.deadline - self.clock()))
            lease.timer = self.timer_factory(seconds, lambda: self._request_finish(lease, "expired"))
            if hasattr(lease.timer, "daemon"):
                lease.timer.daemon = True
            lease.timer.start()
            if self._current(lease):
                self.emit("shortcut_capture_status", lease.generation, "capturing", "")
        except Exception:
            self._request_finish(lease, "failed")

    def _request_finish(self, lease, state, chord=""):
        with self._lock:
            if self._lease is not lease or lease.finishing:
                return
            lease.cancelled.set()
            lease.finishing = True
            try:
                self.executor.submit(self._finish, lease, state, chord)
            except Exception:
                # A retiring executor must not strand an installed hook or block the GUI.
                threading.Thread(target=self._finish, args=(lease, state, chord), daemon=True,
                    name="Saydraft-shortcut-retire").start()

    def _finish(self, lease, state, chord):
        owner = lease.owner
        if lease.timer is not None:
            lease.timer.cancel()
        if owner is not None:
            try:
                stopped = owner.close()
                if not stopped:
                    thread = owner.completion_thread
                    if thread is None:
                        self.emit("shortcut_capture_status", lease.generation, "cleanup_failed", "")
                        return  # Retain the owner/reservation until exit can be observed.
                    thread.join()  # Control worker only; GUI and hook callbacks never join.
                if owner.status.get("reason"):
                    state, chord = "failed", ""
            except Exception:
                self.emit("shortcut_capture_status", lease.generation, "cleanup_failed", "")
                return  # Unknown cleanup never becomes permission to install another owner.
        with self._lock:
            if self._lease is not lease:
                return
            if state not in ("captured", "cancelled", "expired", "invalid", "failed"):
                state, chord = "failed", ""
            if state == "captured":
                try:
                    Chord.parse(chord)
                    if lease.revoked or not lease.valid() or not lease.foreground():
                        state, chord = "cancelled", ""
                except Exception:
                    state, chord = "failed", ""
            lease.owner = None
            self._lease = None
        if not self.closed:
            self.emit("shortcut_capture_status", lease.generation, state, chord if state == "captured" else "")
        self.finished()

    def cancel(self, generation=None):
        with self._lock:
            lease = self._lease
            if lease is None or generation not in (None, lease.generation):
                return False
            lease.revoked = True
            self._request_finish(lease, "cancelled")
            return True

    def close(self):
        with self._lock:
            self.closed = True
            self.cancel()
        self.executor.shutdown(wait=False, cancel_futures=False)
