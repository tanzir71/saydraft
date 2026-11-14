"""Explicit Ctrl+C capture; the caller supplies fresh field/modifier guards.

This is an inert transaction primitive, not permission to read the clipboard.
There is no input default, model call or automatic paste. Integration must wait
for the held Command chord to clear and verify known non-password field identity.
"""

from dataclasses import dataclass
import math
import time

from saydraft.context.selection import SELECTION_LIMIT
from .clipboard_handles import ClipboardUnavailable
from .clipboard_win import ClipboardLease, Snapshot


@dataclass(frozen=True)
class CopiedSelection:
    text: str = ""
    reason: str = "clipboard_unavailable"
    restore_status: str = "unchanged"


def capture_selection(clipboard, *, process_id, guard, send_copy, current=lambda: True,
                      timeout=.75, clock=time.monotonic, sleep=time.sleep):
    """Attempt one copy, returning complete text only after exact restoration.

    `guard` must recheck the original foreground/PID/field/password, UIPI and all
    physical modifiers; it returns a refusal reason or ''. It must not wait for
    a GUI/session mutex. `send_copy` sends one genuine Ctrl+C without releasing
    physically held keys. Neither callback is invoked implicitly elsewhere.

    Sequence + owner PID provide race checks, not proof of the origin of a copy
    made concurrently by the same app. There is no selected-range anchor and no
    write-back authority. Target-generated clipboard history/sync policy remains
    the target app's. A copy arriving after the bounded observation window cannot
    be reclaimed safely; this routine never overwrites an unobserved late copy.
    """
    if (type(process_id) is not int or not 0 < process_id < 2**32
            or type(timeout) not in (int, float) or not math.isfinite(timeout) or not .05 <= timeout <= 2
            or not all(callable(fn) for fn in (guard, send_copy, current, clock, sleep))):
        raise ValueError("Invalid explicit selection-copy request")

    def admission():
        try:
            if not current():
                return "cancelled"
            reason = guard()
            if type(reason) is not str:
                return "field_unavailable"
            return reason if current() else "cancelled"
        except Exception:
            return "field_unavailable"

    snapshot = None
    try:
        with clipboard._ui_lock():
            if reason := admission():
                return CopiedSelection(reason=reason)
            if clipboard.pending is not None:
                return CopiedSelection(reason="clipboard_restore_pending", restore_status="pending")
            api = clipboard._factory()
            with api.window() as hwnd:
                try:
                    with api.opened(hwnd):
                        snapshot = Snapshot.take(api)
                        if snapshot.skipped:
                            return CopiedSelection(reason="clipboard_incomplete")
                        before, original_owner = api.sequence(), api.owner()
                    # Do not adopt a copy racing snapshot/CloseClipboard. A
                    # synthesized format may also conservatively refuse here.
                    if not before:
                        return CopiedSelection()
                    if api.sequence() != before or api.owner() != original_owner:
                        return CopiedSelection(reason="clipboard_changed")
                    if reason := admission():
                        return CopiedSelection(reason=reason)
                    if api.sequence() != before or api.owner() != original_owner:
                        return CopiedSelection(reason="clipboard_changed")

                    failed = False
                    deadline = clock() + timeout
                    try:
                        send_copy()
                    except Exception:
                        # Partial SendInput can already have copied. Observe
                        # once and restore if attributable by our bounded checks.
                        failed = True
                    while True:
                        sequence = api.sequence()
                        if not sequence:
                            return CopiedSelection()
                        if sequence != before:
                            owner = api.owner()
                            try:
                                ours = bool(owner and api.window_pid(owner) == process_id)
                            except (OSError, ValueError, TypeError):
                                ours = False
                            if not ours:
                                return CopiedSelection(reason="clipboard_changed")
                            # Bind before OpenClipboard: if the target keeps it
                            # busy, this copy still needs restore/recovery.
                            lease = ClipboardLease(api, owner, sequence)
                            reason, text = "", ""
                            try:
                                with api.opened(hwnd):
                                    reason = admission() or ("copy_failed" if failed else "")
                                    matched = lease.current()
                                    if not matched:
                                        reason = "clipboard_changed"
                                    try:
                                        if not reason:
                                            handle = api.get(13)  # Only CF_UNICODETEXT; no stale fallback.
                                            if not handle:
                                                raise ClipboardUnavailable("Copy has no Unicode text")
                                            text = api.unicode_text(handle, limit=SELECTION_LIMIT)
                                            if type(text) is not str or "\0" in text:
                                                reason = "selection_invalid"
                                            elif not text:
                                                reason = "empty"
                                            elif len(text.encode("utf-16-le")) // 2 > SELECTION_LIMIT:
                                                reason = "selection_too_long"
                                    finally:
                                        # Delayed rendering may change sequence
                                        # even if Unicode reading then fails.
                                        # Adopt only our matched locked interval.
                                        if matched and api.owner() == owner and api.sequence():
                                            lease.expected_sequence = api.sequence()
                                        else:
                                            reason = "clipboard_changed"
                            except (OSError, UnicodeError):
                                reason = "selection_unavailable"
                            reason = admission() or reason
                            # Transfer the complete snapshot to the existing
                            # restoration/recovery owner exactly once.
                            original, snapshot = snapshot, None
                            restored = clipboard._finish(api, hwnd, lease, original)
                            reason = admission() or reason
                            if restored != "restored":
                                reason = {"pending": "clipboard_restore_pending",
                                          "replaced": "clipboard_changed"}.get(restored, "clipboard_cleanup_failed")
                            return CopiedSelection(text if not reason else "", reason or "ok", restored)
                        # Even after cancellation, observe the already-sent copy
                        # until this deadline so its formats can be restored.
                        if clock() >= deadline:
                            reason = admission() or ("copy_failed" if failed else "copy_timeout")
                            return CopiedSelection(reason=reason)
                        sleep(min(.01, max(0, deadline - clock())))
                finally:
                    if snapshot is not None:
                        original, snapshot = snapshot, None
                        original.close()
    except (ClipboardUnavailable, OSError):
        return CopiedSelection()
