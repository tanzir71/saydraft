"""Bounded eager clipboard transactions with privacy flags and recovery copies."""

import threading
from contextlib import contextmanager
from dataclasses import dataclass

from .clipboard_handles import MAX_SNAPSHOT_BYTES, ClipboardUnavailable


def release(copies):
    failed = False
    for copy in copies:
        try:
            copy.close()
        except OSError:
            failed = True
    if failed:
        raise ClipboardUnavailable("Some clipboard copies did not retire")


@dataclass
class Snapshot:
    copies: list
    size: int = 0
    skipped: int = 0

    @classmethod
    def take(cls, api):
        snapshot = cls([])
        try:
            formats = list(api.formats())
            for format in formats:
                if format == 0x80 or 0x200 <= format <= 0x2FF:
                    raise ClipboardUnavailable("Opaque clipboard owner format")
                handle = api.get(format)
                if not handle:  # The owner failed to render this format.
                    snapshot.skipped += 1
                    continue
                copy = api.duplicate(format, handle, remaining=MAX_SNAPSHOT_BYTES - snapshot.size)
                snapshot.copies.append(copy)
                snapshot.size += copy.size
            if formats and not snapshot.copies:
                raise ClipboardUnavailable("No clipboard formats could be rendered")
            return snapshot
        except BaseException:
            snapshot.close()
            raise

    def close(self):
        release(self.copies)

    def stage(self, api):
        copies, size = [], 0
        try:
            for copy in self.copies:
                duplicate = api.duplicate(copy.format, copy.handle, remaining=MAX_SNAPSHOT_BYTES - size)
                copies.append(duplicate)
                size += duplicate.size
            return copies
        except BaseException:
            release(copies)
            raise


class DeliveryBlocked(ClipboardUnavailable):
    def __init__(self, reason):
        super().__init__("Delivery guard refused clipboard publication")
        self.reason = reason


@dataclass
class ClipboardLease:
    api: object
    window: int
    expected_sequence: int = 0
    skipped: int = 0
    restore_status: str = "unchanged"

    def current(self):
        return bool(self.expected_sequence and self.api.sequence() == self.expected_sequence
                    and self.api.owner() == self.window)


class WindowsClipboard:
    def __init__(self, *, api_factory=None):
        if api_factory is None:
            from ._clipboard_win32 import NativeClipboardApi
            api_factory = NativeClipboardApi
        self._factory, self._lock = api_factory, threading.RLock()
        self.pending, self.pending_sequence = None, 0

    def close(self):
        if not self._lock.acquire(blocking=False):
            return False  # An active transaction restores itself in its finally block.
        try:
            return self.recover()
        finally:
            self._lock.release()

    def setText(self, text):
        """Explicit Copy replaces the clipboard and keeps all dictation privacy flags."""
        if not isinstance(text, str) or "\0" in text:
            raise ValueError("Clipboard text must be a string without embedded NUL characters")
        with self._ui_lock():
            api, payloads = self._factory(), []
            try:
                with api.window() as hwnd, api.opened(hwnd):
                    try:
                        for format in api.privacy:
                            payloads.append(api.memory(format, bytes(4)))
                        payloads.append(api.memory(13, (text + "\0").encode("utf-16-le")))
                        api.empty()
                        for copy in payloads:
                            api.put(copy)
                        if self.pending is not None:
                            original, self.pending = self.pending, None
                            self.pending_sequence = 0
                            original.close()
                    finally:
                        if self.pending is not None and api.owner() == hwnd:
                            self.pending_sequence = api.sequence()
            finally:
                release(payloads)

    def read_text(self):
        """Read only an explicitly requested snippet value; never publish or restore."""
        with self._ui_lock():
            if self.pending is not None:
                raise ClipboardUnavailable("Previous clipboard restoration is pending")
            api = self._factory()
            with api.window() as hwnd, api.opened(hwnd):
                handle = api.get(13)
                if not handle:
                    raise ClipboardUnavailable("Clipboard has no text")
                return api.unicode_text(handle)

    @contextmanager
    def _ui_lock(self):
        if not self._lock.acquire(blocking=False):
            raise ClipboardUnavailable("A clipboard transaction is active")
        try:
            yield
        finally:
            self._lock.release()

    def _restore_locked(self, api, snapshot):
        copies = snapshot.stage(api)  # All allocations happen before EmptyClipboard.
        try:
            api.empty()
            failed = False
            for copy in copies:
                try:
                    api.put(copy)
                except ClipboardUnavailable:
                    failed = True  # Still attempt the other original formats.
            return not failed
        finally:
            release(copies)

    @staticmethod
    def _owned_sequence(api, hwnd, previous):
        # Windows can synthesize formats on CloseClipboard. Read sequence before
        # checking our unique owner so a racing user copy cannot be adopted.
        sequence = api.sequence()
        return sequence if api.owner() == hwnd else previous

    def recover(self):
        """Retry the single retained original, unless a new clipboard copy supersedes it."""
        if not self._lock.acquire(blocking=False):
            return False
        try:
            return self._recover_locked()
        finally:
            self._lock.release()

    def _recover_locked(self):
        with self._lock:
            if self.pending is None:
                return True
            api = self._factory()
            try:
                with api.window() as hwnd:
                    with api.opened(hwnd):
                        try:
                            sequence = api.sequence()
                            if not sequence or not self.pending_sequence:
                                return False
                            if sequence != self.pending_sequence or self._restore_locked(api, self.pending):
                                original, self.pending = self.pending, None
                                self.pending_sequence = 0
                                original.close()
                                return True
                        finally:
                            if self.pending is not None and api.owner() == hwnd:
                                self.pending_sequence = api.sequence()
                    if self.pending is not None:
                        self.pending_sequence = self._owned_sequence(api, hwnd, self.pending_sequence)
            except ClipboardUnavailable:
                return False
            return False

    def _finish(self, api, hwnd, lease, snapshot):
        expected, retired = lease.expected_sequence, False
        try:
            with api.opened(hwnd):
                try:
                    if not api.sequence() or not lease.expected_sequence:
                        raise ClipboardUnavailable("Clipboard sequence is unavailable")
                    if not lease.current():
                        status = "replaced"  # Never overwrite a new user copy.
                    else:
                        status = "restored" if self._restore_locked(api, snapshot) else "pending"
                    if status != "pending":
                        retired = True
                        try:
                            snapshot.close()
                        except ClipboardUnavailable:
                            return "cleanup_failed"
                        return status
                finally:
                    if api.owner() == hwnd:
                        expected = api.sequence()  # Only sample our writes while holding the lock.
        except ClipboardUnavailable:
            pass
        if retired:
            return "cleanup_failed"
        expected = self._owned_sequence(api, hwnd, expected)
        self.pending, self.pending_sequence = snapshot, expected
        return "pending"  # Original handles remain owned in RAM for recover().

    @contextmanager
    def temporary_text(self, text, *, guard=lambda: ""):
        if not isinstance(text, str) or "\0" in text:
            raise ValueError("Clipboard text must be a string without embedded NUL characters")
        with self._lock:
            if not self.recover():
                raise ClipboardUnavailable("Previous clipboard restoration is pending")
            api = self._factory()
            with api.window() as hwnd:
                lease, snapshot, payloads, changed = ClipboardLease(api, hwnd), None, [], False
                try:
                    with api.opened(hwnd):
                        snapshot = Snapshot.take(api)
                        lease.skipped = snapshot.skipped
                        if reason := guard():
                            raise DeliveryBlocked(reason)
                        # Every privacy flag must be available before publishing dictation text.
                        for format in api.privacy:
                            payloads.append(api.memory(format, b"\0\0\0\0"))
                        payloads.append(api.memory(13, (text + "\0").encode("utf-16-le")))
                        api.empty()
                        changed = True
                        try:
                            for copy in payloads:
                                api.put(copy)
                        finally:
                            lease.expected_sequence = api.sequence()
                    lease.expected_sequence = self._owned_sequence(api, hwnd, lease.expected_sequence)
                    yield lease
                finally:
                    try:
                        if snapshot is not None:
                            if changed:
                                lease.expected_sequence = self._owned_sequence(api, hwnd, lease.expected_sequence)
                                lease.restore_status = self._finish(api, hwnd, lease, snapshot)
                            else:
                                snapshot.close()
                    finally:
                        release(payloads)
