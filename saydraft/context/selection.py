"""Explicit selected-text leases; COM ranges never leave their UIA MTA owner."""

from dataclasses import dataclass
import math
import threading
import time

from .focused_edit import read_focused_edit
from .tracked_edit import FieldIdentity

SELECTION_LIMIT = 8192  # UTF-16 units; incomplete selections are never returned.
MAX_SELECTION_LEASE = 3660  # Maximum recording cap plus processing time.


@dataclass(frozen=True)
class SelectionSnapshot:
    status: str = "unavailable"
    ticket: int = 0
    identity: FieldIdentity | None = None
    control_type: int | None = None
    text: str = ""
    read_only: bool | None = None
    generation: int = 0  # Minted by the bounded caller, never a native proxy.


@dataclass
class _Lease:
    snapshot: SelectionSnapshot
    anchor: object
    expires_at: float


class SelectionTracker:
    def __init__(self, reader, *, clock=time.monotonic):
        self.reader, self.clock = reader, clock
        self._thread = threading.get_ident()
        self._lease, self._ticket = None, 0

    def _owned(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("Selection ranges belong to their UIA MTA owner")

    @property
    def expires_at(self):
        self._owned()
        return self._lease.expires_at if self._lease else None

    def clear(self):
        self._owned()
        self._lease = None  # Release every retained range/text on its owner.

    def expire(self):
        self._owned()
        if self._lease and self.clock() >= self._lease.expires_at:
            self.clear()

    def _element(self, identity, control_type, current):
        if not current():
            return None, "cancelled"
        reader = self.reader
        if reader.window_pid(identity.window) != identity.process_id:
            return None, "focus_changed"
        element = reader.focused_element()
        if element is None or not reader.belongs(element, identity.window):
            return None, "focus_changed"
        # Both metadata and the fresh property must explicitly deny password state.
        for check in (reader.password, getattr(reader, "fresh_password", reader.password)):
            password = check(element)
            if password is True:
                return None, "password_field"
            if password is not False:
                return None, "field_unavailable"
        if (reader.runtime_id(element) != identity.runtime_id or reader.control_type(element) != control_type
                or not reader.same_focus(element)):
            return None, "focus_changed"
        return (element, "") if current() else (None, "cancelled")

    def _text(self, anchor, current):
        text = self.reader.selection_text(anchor, SELECTION_LIMIT, current)
        if type(text) is not str or not current():
            return None, "field_unavailable"
        try:
            if len(text.encode("utf-16-le", errors="surrogatepass")) // 2 > SELECTION_LIMIT:
                return None, "selection_too_long"
            units = len(text.encode("utf-16-le")) // 2
        except UnicodeError:
            return None, "field_unavailable"
        return (None, "selection_too_long") if units > SELECTION_LIMIT else (text, "")

    def _read_only(self, element):
        method = getattr(self.reader, "selection_read_only", None)
        value = method(element) if method else None
        return value if type(value) is bool else None

    def begin(self, window, process_id, *, lease_seconds=1260, current=lambda: True):
        self._owned()
        self.clear()
        if (type(window) is not int or not 0 < window < 2**64
                or type(process_id) is not int or not 0 < process_id < 2**32
                or type(lease_seconds) not in (int, float) or not math.isfinite(lease_seconds)
                or not 0 < lease_seconds <= MAX_SELECTION_LEASE):
            return SelectionSnapshot()
        try:
            field = read_focused_edit(self.reader, window, include_text=False, current=current)
            if field.status != "ok":
                return SelectionSnapshot(status={"password": "password_field", "changed": "focus_changed"}.get(field.status, field.status))
            identity = FieldIdentity(window, process_id, field.runtime_id)
            if not identity.valid():
                return SelectionSnapshot()
            base = {"identity": identity, "control_type": field.control_type}
            element, reason = self._element(identity, field.control_type, current)
            if reason:
                return SelectionSnapshot(status=reason)
            try:
                anchor = self.reader.selection_range(element, current)
            except Exception:
                return SelectionSnapshot(status="unsupported", **base)
            if anchor is None:
                return SelectionSnapshot(status="unsupported", **base)
            text, reason = self._text(anchor, current)
            element, sensitive = self._element(identity, field.control_type, current)
            if sensitive:
                return SelectionSnapshot(status=sensitive)
            if reason:
                return SelectionSnapshot(status=reason, **base)
            fresh = self.reader.selection_range(element, current)
            if fresh is None or not self.reader.same_selection(anchor, fresh):
                return SelectionSnapshot(status="selection_changed")
            again, reason = self._text(fresh, current)
            if reason or again != text:
                return SelectionSnapshot(status=reason or "selection_changed")
            read_only = self._read_only(element)
            element, reason = self._element(identity, field.control_type, current)
            if reason:
                return SelectionSnapshot(status=reason)
            final = self.reader.selection_range(element, current)
            if final is None or not self.reader.same_selection(anchor, final):
                return SelectionSnapshot(status="selection_changed")
            if not text:
                return SelectionSnapshot(status="empty", read_only=read_only, **base)
            self._ticket += 1
            snapshot = SelectionSnapshot("ready", self._ticket, identity, field.control_type, text, read_only)
            self._lease = _Lease(snapshot, anchor, self.clock() + lease_seconds)
            return snapshot
        except Exception:
            self.clear()
            return SelectionSnapshot()

    def verify(self, snapshot, *, for_write=True, current=lambda: True):
        self._owned()
        if type(for_write) is not bool:
            return "field_unavailable"
        self.expire()
        lease = self._lease
        if (type(snapshot) is not SelectionSnapshot or snapshot.status != "ready" or type(snapshot.ticket) is not int
                or lease is None or snapshot.ticket != lease.snapshot.ticket
                or snapshot.identity != lease.snapshot.identity or snapshot.control_type != lease.snapshot.control_type
                or type(snapshot.text) is not str or snapshot.text != lease.snapshot.text):
            return "selection_expired"
        try:
            element, reason = self._element(snapshot.identity, snapshot.control_type, current)
            if not reason and for_write and self._read_only(element) is True:
                reason = "read_only"
            if not reason:
                fresh = self.reader.selection_range(element, current)
                if fresh is None or not self.reader.same_selection(lease.anchor, fresh):
                    reason = "selection_changed"
                else:
                    text, reason = self._text(fresh, current)
                    if not reason and text != lease.snapshot.text:
                        reason = "selection_changed"
            if not reason:
                element, reason = self._element(snapshot.identity, snapshot.control_type, current)
            if not reason:
                final = self.reader.selection_range(element, current)
                if final is None or not self.reader.same_selection(lease.anchor, final):
                    reason = "selection_changed"
            if reason:
                self.clear()
            return reason
        except Exception:
            self.clear()
            return "field_unavailable"
