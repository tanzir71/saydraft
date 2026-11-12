"""One short-lived insertion observation; owned exclusively by the UIA MTA."""

import hashlib
import math
import threading
import time
from dataclasses import dataclass

FIELD_LIMIT = 8192  # UTF-16 units, including surrounding text in this field only.
INSERT_LIMIT = 4096
CHECK_AFTER = 15
RETIRE_AFTER = 16  # One second for a scheduled final read; then release everything.
MAX_PREPARATION_LEASE = 3660  # Settings permits a one-hour recording; allow processing time.


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
    lease_seconds: float = RETIRE_AFTER


def _digest(text):
    return hashlib.sha256(text.encode("utf-16-le")).digest()


def valid_inserted(text):
    try:
        return (isinstance(text, str) and 0 < len(text) <= INSERT_LIMIT
            and len(text.encode("utf-16-le")) // 2 <= INSERT_LIMIT)
    except UnicodeError:
        return False


class TrackedEditReader:
    def __init__(self, reader, *, clock=time.monotonic):
        self.reader, self.clock, self._tracked, self._ticket = reader, clock, None, 0
        self._thread = threading.get_ident()

    def _owned(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("Tracked fields belong to their UIA MTA owner")

    @property
    def expires_at(self):
        return self._tracked.started + self._tracked.lease_seconds if self._tracked else None

    def clear(self, ticket=None):
        self._owned()
        if self._tracked and (ticket is None or ticket == self._tracked.ticket):
            self._tracked = None  # Release COM references on their owner thread.

    def expire(self):
        if self._tracked and self.clock() >= self.expires_at:
            self.clear()

    def _valid(self, tracked, current):
        reader, key = self.reader, tracked.identity
        if (not current() or self.clock() >= tracked.started + tracked.lease_seconds
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
        if not valid_inserted(inserted):
            self.clear()
            return None
        ticket = self.prepare(identity, lease_seconds=RETIRE_AFTER, current=current)
        if ticket is not None:
            self._tracked.original = inserted
        return ticket

    def prepare(self, identity, *, lease_seconds=RETIRE_AFTER, current=lambda: True):
        """Capture edges before recognition finishes; retain no transcript yet."""
        self._owned()
        self.clear()
        try:
            if (not isinstance(identity, FieldIdentity) or not identity.valid()
                    or type(lease_seconds) not in (int, float) or not math.isfinite(lease_seconds)
                    or not 0 < lease_seconds <= MAX_PREPARATION_LEASE or not current()):
                return None
            element = self.reader.focused_element()
            tracked = _Tracked(0, identity, element, "", 0, 0, b"", b"", self.clock(), lease_seconds=lease_seconds)
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
        """Compatibility for callers that supplied text to begin()."""
        self._owned()
        tracked = self._tracked
        return (tracked is not None and tracked.ticket == ticket
            and self.commit(ticket, tracked.original, current=current) is None)

    def commit(self, ticket, inserted, *, inserted_at=None, current=lambda: True):
        """None starts watching; a terminal span also covers an already-made edit."""
        self._owned()
        tracked = self._tracked
        if tracked is None or tracked.ticket != ticket:
            return ObservedEdit("", "")
        try:
            now = self.clock()
            when = now if inserted_at is None else inserted_at
            if (tracked.confirmed or not valid_inserted(inserted) or now >= self.expires_at
                    or type(when) not in (int, float) or not math.isfinite(when) or not 0 <= when <= now):
                self.clear(ticket)
                return ObservedEdit("", "")
            tracked.original, tracked.started = inserted, when
            tracked.lease_seconds, tracked.confirmed = RETIRE_AFTER, True
            span = self._span(tracked, current)
            if span == inserted:
                return None
            self.clear(ticket)
            return ObservedEdit(inserted, span) if span is not None else ObservedEdit("", "")
        except Exception:
            self.clear(ticket)
            return ObservedEdit("", "")

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
