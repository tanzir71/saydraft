"""Explicit selected-text leases; COM ranges never leave their UIA MTA owner."""

from dataclasses import dataclass, replace
import math
import threading
import time

from .focused_edit import read_focused_edit
from .tracked_edit import FieldIdentity

SELECTION_LIMIT = 8192  # UTF-16 units; incomplete selections are never returned.
REPLACEMENT_LIMIT = 16384
MAX_SELECTION_LEASE = 3660  # Maximum recording cap plus processing time.
COPY_CONTROL_TYPES = frozenset((50004, 50020, 50030))  # Edit, Text, Document only.


@dataclass(frozen=True)
class SelectionSnapshot:
    status: str = "unavailable"
    ticket: int = 0
    identity: FieldIdentity | None = None
    control_type: int | None = None
    text: str = ""
    read_only: bool | None = None
    generation: int = 0  # Minted by the bounded caller, never a native proxy.
    origin: str = "uia"


@dataclass
class _Lease:
    snapshot: SelectionSnapshot
    anchor: object
    expires_at: float
    position: int | None = None  # Native text-unit offset; never surrounding text.


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

    def begin(self, window, process_id, *, lease_seconds=1260, allow_copy=False, current=lambda: True):
        self._owned()
        self.clear()
        if (type(window) is not int or not 0 < window < 2**64
                or type(process_id) is not int or not 0 < process_id < 2**32
                or type(lease_seconds) not in (int, float) or not math.isfinite(lease_seconds)
                or not 0 < lease_seconds <= MAX_SELECTION_LEASE or type(allow_copy) is not bool):
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
                anchor = None
            if anchor is None:
                if allow_copy and field.control_type in COPY_CONTROL_TYPES:
                    # This reserves only original safe field metadata. No text
                    # or write authority is obtained until an explicit copy.
                    read_only = self._read_only(element)
                    _element, reason = self._element(identity, field.control_type, current)
                    if reason:
                        return SelectionSnapshot(status=reason)
                    self._ticket += 1
                    snapshot = SelectionSnapshot("copy_pending", self._ticket, identity, field.control_type,
                                                 read_only=read_only, origin="clipboard")
                    self._lease = _Lease(snapshot, None, self.clock() + lease_seconds)
                    return snapshot
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
            position = None
            positioning = getattr(self.reader, "selection_position", None)
            if positioning is not None:
                try:
                    position = positioning(element, anchor, current)
                except Exception:
                    pass  # Selection remains readable; a later paste cannot be confirmed.
            if type(position) is not int or not 0 <= position < 2**31:
                position = None
            element, reason = self._element(identity, field.control_type, current)
            if reason:
                return SelectionSnapshot(status=reason)
            final = self.reader.selection_range(element, current)
            if final is None or not self.reader.same_selection(anchor, final):
                return SelectionSnapshot(status="selection_changed")
            self._ticket += 1
            snapshot = SelectionSnapshot("ready", self._ticket, identity, field.control_type, text, read_only)
            self._lease = _Lease(snapshot, anchor, self.clock() + lease_seconds, position)
            return snapshot
        except Exception:
            self.clear()
            return SelectionSnapshot()

    def _matching(self, snapshot):
        self.expire()
        lease = self._lease
        if (type(snapshot) is not SelectionSnapshot or snapshot.status not in ("ready", "copy_pending") or type(snapshot.ticket) is not int
                or lease is None or snapshot.ticket != lease.snapshot.ticket
                or snapshot.status != lease.snapshot.status or snapshot.origin != lease.snapshot.origin
                or snapshot.identity != lease.snapshot.identity or snapshot.control_type != lease.snapshot.control_type
                or type(snapshot.text) is not str or snapshot.text != lease.snapshot.text):
            return None
        return lease

    def verify(self, snapshot, *, for_write=True, current=lambda: True):
        self._owned()
        if type(for_write) is not bool:
            return "field_unavailable"
        lease = self._matching(snapshot)
        if lease is None:
            return "selection_expired"
        try:
            element, reason = self._element(snapshot.identity, snapshot.control_type, current)
            if not reason and snapshot.origin == "clipboard":
                # A copied string has no anchored original range. Metadata can
                # authorize reading/generation, never an automatic write.
                return "copy_only" if for_write else ""
            if not reason and for_write and (lease.snapshot.read_only is True or self._read_only(element) is True):
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

    def seal_copy(self, snapshot, text, *, current=lambda: True):
        """Bind one complete copied string to the same revocable metadata lease."""
        self._owned()
        lease = self._matching(snapshot)
        if lease is None or snapshot.status != "copy_pending" or snapshot.origin != "clipboard":
            return SelectionSnapshot(status="selection_expired")
        try:
            if (type(text) is not str or not text or "\0" in text
                    or len(text.encode("utf-16-le")) // 2 > SELECTION_LIMIT):
                self.clear()
                return SelectionSnapshot(status="selection_unavailable")
            element, reason = self._element(snapshot.identity, snapshot.control_type, current)
            if reason:
                self.clear()
                return SelectionSnapshot(status=reason)
            read_only = self._read_only(element)
            _element, reason = self._element(snapshot.identity, snapshot.control_type, current)
            if reason:
                self.clear()
                return SelectionSnapshot(status=reason)
            sealed = replace(lease.snapshot, status="ready", text=text, read_only=read_only)
            lease.snapshot = sealed
            return sealed
        except Exception:
            self.clear()
            return SelectionSnapshot(status="field_unavailable")

    def confirm(self, snapshot, replacement, *, current=lambda: True):
        """One-shot post-write read of the intended span; never another write."""
        self._owned()
        lease = self._matching(snapshot)
        if lease is None:
            return "selection_expired"  # Never retire a newer session's lease.
        try:
            if snapshot.origin == "clipboard":
                return "insertion_unconfirmed"
            if type(replacement) is not str or not 0 < len(replacement) <= REPLACEMENT_LIMIT:
                return "insertion_unconfirmed"
            units = len(replacement.encode("utf-16-le")) // 2
            if not 0 < units <= REPLACEMENT_LIMIT or lease.position is None:
                return "insertion_unconfirmed"
            read = getattr(self.reader, "replacement_text", None)
            if read is None:
                return "insertion_unconfirmed"
            for _ in range(2):
                element, reason = self._element(snapshot.identity, snapshot.control_type, current)
                if reason:
                    return reason
                if self._read_only(element) is True:
                    return "read_only"
                text = read(element, lease.position, units, current)
                if type(text) is not str or text != replacement:
                    return "insertion_unconfirmed"
            _element, reason = self._element(snapshot.identity, snapshot.control_type, current)
            return reason
        except Exception:
            return "insertion_unconfirmed"
        finally:
            self.clear()  # A confirmation receipt cannot be replayed.
