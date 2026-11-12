"""One short-lived insertion observation; owned exclusively by the UIA MTA."""

import hashlib
import threading
import time
from dataclasses import dataclass

FIELD_LIMIT = 8192  # UTF-16 units, including surrounding text in this field only.
INSERT_LIMIT = 4096
CHECK_AFTER = 15
RETIRE_AFTER = 16  # One second for a scheduled final read; then release everything.


@dataclass(frozen=True)
class FieldIdentity:
    window: int
    process_id: int
    runtime_id: tuple[int, ...]

    def valid(self):
        return (type(self.window) is int and 0 < self.window < 2**64
            and type(self.process_id) is int and 0 < self.process_id < 2**32
            and isinstance(self.runtime_id, tuple) and 1 <= len(self.runtime_id) <= 32
            and all(type(n) is int and -(2**31) <= n < 2**31 for n in self.runtime_id))


@dataclass(frozen=True)
class ObservedEdit:
    original: str
    current: str


@dataclass
class _Tracked:
    ticket: int
    identity: FieldIdentity
    element: object
    original: str
    prefix_length: int
    suffix_length: int
    prefix_hash: bytes
    suffix_hash: bytes
    started: float
    confirmed: bool = False


def _digest(text):
    return hashlib.sha256(text.encode("utf-16-le")).digest()


class TrackedEditReader:
    def __init__(self, reader, *, clock=time.monotonic):
        self.reader, self.clock, self._tracked, self._ticket = reader, clock, None, 0
        self._thread = threading.get_ident()

    def _owned(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("Tracked fields belong to their UIA MTA owner")

    @property
    def expires_at(self):
        return self._tracked.started + RETIRE_AFTER if self._tracked else None

    def clear(self, ticket=None):
        self._owned()
        if self._tracked and (ticket is None or ticket == self._tracked.ticket):
            self._tracked = None  # Release COM references on their owner thread.

    def expire(self):
        if self._tracked and self.clock() >= self.expires_at:
            self.clear()

    def _valid(self, tracked, current):
        reader, key = self.reader, tracked.identity
        if (not current() or self.clock() >= tracked.started + RETIRE_AFTER
                or reader.window_pid(key.window) != key.process_id):
            return False
        # Retained Win32 proxy objects can expose stale text/password state even
        # through Current properties. Reacquire this identity using metadata only.
        element = reader.refresh_element(tracked.element, key.window, key.runtime_id, current)
        if element is None:
            return False
        tracked.element = element
        return (reader.runtime_id(tracked.element) == key.runtime_id
            and reader.belongs(tracked.element, key.window)
            and reader.password(tracked.element) is False and current())  # Just-fetched batch, not a retained cache.

    def begin(self, identity, inserted, *, current=lambda: True):
        self._owned()
        self.clear()
        try:
            if (not isinstance(identity, FieldIdentity) or not identity.valid()
                    or not isinstance(inserted, str) or not 0 < len(inserted) <= INSERT_LIMIT
                    or len(inserted.encode("utf-16-le")) // 2 > INSERT_LIMIT or not current()):
                return None
            element = self.reader.focused_element()
            tracked = _Tracked(0, identity, element, inserted, 0, 0, b"", b"", self.clock())
            def valid():
                return self._valid(tracked, current)
            if not valid() or self.reader.keyboard_focus_snapshot(tracked.element) is not True:
                return None
            parts = self.reader.insertion_edges(tracked.element, FIELD_LIMIT, valid)
            if parts is None or len(parts) != 2 or not valid():
                return None
            prefix, suffix = parts
            if (not all(isinstance(s, str) for s in parts)
                    or len((prefix + suffix).encode("utf-16-le")) // 2 > FIELD_LIMIT):
                return None
            self._ticket += 1
            tracked.ticket = self._ticket
            tracked.prefix_length, tracked.suffix_length = len(prefix), len(suffix)
            tracked.prefix_hash, tracked.suffix_hash = _digest(prefix), _digest(suffix)
            self._tracked = tracked
            return tracked.ticket
        except Exception:
            return None  # Never expose provider errors, ranges or surrounding field text.

    def _span(self, tracked, current):
        def valid():
            return self._valid(tracked, current)
        if not valid():
            return None
        text = self.reader.document_text(tracked.element, FIELD_LIMIT, valid)
        if not isinstance(text, str) or not valid() or len(text.encode("utf-16-le")) // 2 > FIELD_LIMIT:
            return None
        a, n = tracked.prefix_length, tracked.suffix_length
        b = len(text) - n
        if (b < a or _digest(text[:a]) != tracked.prefix_hash or _digest(text[b:]) != tracked.suffix_hash
                or b - a > INSERT_LIMIT):
            return None
        return text[a:b]

    def confirm(self, ticket, *, current=lambda: True):
        self._owned()
        tracked = self._tracked
        if tracked is None or tracked.ticket != ticket:
            return False
        try:
            if tracked.confirmed or self._span(tracked, current) != tracked.original:
                self.clear(ticket)
                return False
            tracked.started, tracked.confirmed = self.clock(), True
            return True
        except Exception:
            self.clear(ticket)
            return False

    def check(self, ticket, *, current=lambda: True):
        """None is pending; terminal results are one-shot (empty means unavailable)."""
        self._owned()
        tracked = self._tracked
        if tracked is None or tracked.ticket != ticket:
            return ObservedEdit("", "")
        try:
            if not tracked.confirmed or not self._valid(tracked, current):
                self.clear(ticket)
                return ObservedEdit("", "")
            focus = self.reader.keyboard_focus_snapshot(tracked.element)
            if type(focus) is not bool:
                self.clear(ticket)
                return ObservedEdit("", "")
            if focus and self.clock() - tracked.started < CHECK_AFTER:
                return None  # Metadata only while waiting; no GetFocusedElement/GetText.
            self.clear(ticket)
            span = self._span(tracked, current)
            return ObservedEdit(tracked.original, span) if span is not None else ObservedEdit("", "")
        except Exception:
            self.clear(ticket)
            return ObservedEdit("", "")
