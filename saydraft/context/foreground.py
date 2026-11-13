"""Read bounded foreground identity without sending messages to our GUI."""

import ctypes as ct
import ntpath
import sys
import threading
from dataclasses import dataclass
from ctypes import wintypes as wt

from saydraft.core.interfaces import TargetContext
from .app_groups import app_group, browser_site
from .focused_edit import FocusedEdit
from .selection import SelectionSnapshot
from .tracked_edit import FieldIdentity


@dataclass(frozen=True)
class SelectedContext:
    target: TargetContext = TargetContext()
    selection: SelectionSnapshot = SelectionSnapshot()


class NativeForegroundApi:
    def __init__(self):
        self.user = ct.WinDLL("user32", use_last_error=True)
        self.kernel = ct.WinDLL("kernel32", use_last_error=True)
        signatures = (
            (self.user, "GetForegroundWindow", [], wt.HWND),
            (self.user, "GetWindowThreadProcessId", [wt.HWND, ct.POINTER(wt.DWORD)], wt.DWORD),
            (self.user, "GetWindowTextW", [wt.HWND, wt.LPWSTR, ct.c_int], ct.c_int),
            (self.kernel, "GetCurrentProcessId", [], wt.DWORD),
            (self.kernel, "OpenProcess", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
            (self.kernel, "QueryFullProcessImageNameW",
             [wt.HANDLE, wt.DWORD, wt.LPWSTR, ct.POINTER(wt.DWORD)], wt.BOOL),
            (self.kernel, "CloseHandle", [wt.HANDLE], wt.BOOL))
        for library, name, args, result in signatures:
            function = getattr(library, name)
            function.argtypes, function.restype = args, result

    def foreground(self):
        return self.user.GetForegroundWindow()

    def window_pid(self, window):
        pid = wt.DWORD()
        if not self.user.GetWindowThreadProcessId(window, ct.byref(pid)) or not pid.value:
            raise OSError("Foreground process unavailable")
        return pid.value

    def title(self, window, pid):
        # GetWindowText sends WM_GETTEXT to same-process windows, which could
        # wait for our GUI while it is waiting for the worker's session lock.
        if pid == self.kernel.GetCurrentProcessId():
            return ""
        buffer = ct.create_unicode_buffer(4097)
        self.user.GetWindowTextW(window, buffer, len(buffer))
        return buffer.value

    def executable(self, pid):
        process = self.kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION only.
        if not process:
            raise OSError("Foreground image unavailable")
        try:
            buffer = ct.create_unicode_buffer(32768)
            length = wt.DWORD(len(buffer))
            if (not self.kernel.QueryFullProcessImageNameW(process, 0, buffer, ct.byref(length))
                    or not 0 < length.value < len(buffer)):
                raise OSError("Foreground image unavailable")
            return ntpath.basename(buffer.value).casefold()
        finally:
            if not self.kernel.CloseHandle(process):
                raise OSError("Foreground process handle could not close")


class ForegroundContextProvider:
    def __init__(self, *, api=None, profiles=(), uia=None, use_uia=False, observation=None):
        self.api, self.profiles = api, profiles
        self._uia, self._use_uia, self._closed = uia, use_uia or uia is not None, False
        self._uia_lock = threading.Lock()
        self._observation = observation

    def prepare(self):
        with self._uia_lock:
            if self._use_uia and self._uia is None and not self._closed:
                from .uia_worker import BoundedUIA
                self._uia = BoundedUIA(capture_timeout=.5)

    def set_profiles(self, profiles):
        self.profiles = profiles

    def close(self):
        with self._uia_lock:
            self._closed = True
            owners = self._uia, self._observation
        closed = True
        for owner in owners:
            if owner is not None:
                try:
                    closed = owner.close() and closed
                except Exception:
                    closed = False
        return closed

    def prepare_observation(self, target, *, lease_seconds=1260):
        from .tracked_edit import FieldIdentity
        identity = FieldIdentity(target.focus, target.process_id, target.field_id)
        if (self._closed or not self._use_uia or target.uia_status != "ok"
                or target.is_password or not identity.valid()):
            return None
        with self._uia_lock:
            if self._closed:
                return None
            if self._observation is None:
                from .observation_worker import ObservationWorker
                self._observation = ObservationWorker()
            observation = self._observation
        return observation.prepare(identity, lease_seconds=lease_seconds)

    def reserve_observation(self, ticket):
        return bool(not self._closed and self._observation and self._observation.reserve(ticket))

    def commit_observation(self, ticket, text):
        return bool(not self._closed and self._observation and self._observation.commit(ticket, text))

    def cancel_observation(self, ticket):
        if self._observation is not None:
            self._observation.cancel(ticket)

    def take_observation(self, ticket):
        return self._observation.take(ticket) if not self._closed and self._observation else None

    def _field(self, window, *, include_text=True):
        if self._closed:
            return FocusedEdit()
        if not self._use_uia:
            return FocusedEdit(status="not_requested")
        try:
            self.prepare()
            return self._uia.query(int(window), include_text=include_text)
        except Exception:
            return FocusedEdit()

    def _native(self):
        if self.api is None and sys.platform == "win32":
            self.api = NativeForegroundApi()
        return self.api

    def focus(self):
        """Delivery checks need only HWND, never title, image or future UIA calls."""
        if self._closed:
            return None
        api = self._native()
        return (api.foreground() or None) if api is not None else None

    def capture(self):
        return self._capture(include_text=True)

    def capture_for_insertion(self):
        return self._capture(include_text=False)

    def cancel_selection(self, captured=None):
        owner = self._uia
        if owner is None or (captured is not None and type(captured) is not SelectedContext):
            return False
        return owner.cancel_selection(None if captured is None else captured.selection)

    def capture_selection(self, *, lease_seconds=1260):
        """Explicit power-feature read; normal dictation keeps its smaller context bound."""
        if self._closed or not self._use_uia:
            return SelectedContext()
        self.cancel_selection()  # A new intent retires the previous range before any new read.
        try:
            api = self._native()
            if api is None or not (window := api.foreground()):
                return SelectedContext()
            if type(window) is not int or not 0 < window < 2**64:
                return SelectedContext()
            pid = api.window_pid(window)
            if type(pid) is not int or not 0 < pid < 2**32:
                return SelectedContext()
            title = api.title(window, pid)
            try:
                exe = api.executable(pid)
            except OSError:
                exe = ""
            self.prepare()
            snapshot = self._uia.capture_selection(int(window), pid, lease_seconds=lease_seconds)
            if self._closed or api.foreground() != window or api.window_pid(window) != pid:
                self._uia.cancel_selection(snapshot)
                return SelectedContext()
            identity = snapshot.identity
            if identity is None or identity.window != window or identity.process_id != pid:
                return SelectedContext(selection=snapshot)
            site = browser_site(exe, title)
            target = TargetContext(focus=int(window), app_title=title or None, app_exe=exe,
                app_group=app_group(exe, site, self.profiles), app_site=site, process_id=pid,
                uia_status="ok", control_type=snapshot.control_type, field_id=identity.runtime_id,
                selection=snapshot.text, selection_known=snapshot.status in ("ready", "empty"),
                selection_truncated=snapshot.status == "selection_too_long")
            return SelectedContext(target, snapshot)
        except Exception:
            self.cancel_selection()
            return SelectedContext()

    def verify_selection(self, captured, *, for_write=True):
        if self._closed or not self._use_uia or self._uia is None:
            return "field_unavailable"
        if (type(captured) is not SelectedContext or type(captured.selection) is not SelectionSnapshot
                or type(captured.target) is not TargetContext or captured.selection.status != "ready"):
            return "selection_expired"
        target, snapshot = captured.target, captured.selection
        identity = snapshot.identity
        if (type(identity) is not FieldIdentity or not identity.valid() or type(for_write) is not bool
                or target.focus != identity.window or target.process_id != identity.process_id
                or target.field_id != identity.runtime_id or target.control_type != snapshot.control_type
                or target.selection != snapshot.text or target.uia_status != "ok"
                or not target.selection_known or target.selection_truncated or target.is_password):
            self.cancel_selection(captured)
            return "field_unavailable"
        reason = "field_unavailable"
        try:
            api = self._native()
            if api.foreground() != target.focus or api.window_pid(target.focus) != target.process_id:
                reason = "focus_changed"
            else:
                reason = self._uia.verify_selection(snapshot, for_write=for_write)
                if not reason and (self._closed or api.foreground() != target.focus
                                   or api.window_pid(target.focus) != target.process_id):
                    reason = "focus_changed"
        except Exception:
            pass
        if reason:
            self.cancel_selection(captured)
        return reason

    def _capture(self, *, include_text):
        if self._closed:
            return TargetContext()
        api = self._native()
        if api is None:
            return TargetContext()
        try:
            window = api.foreground()
            if not window:
                return TargetContext()
            pid = api.window_pid(window)
            title = api.title(window, pid)
            try:
                exe = api.executable(pid)
            except OSError:
                exe = ""  # A protected process may still have a usable HWND/title.
            field = self._field(window, include_text=include_text)
            if self._closed:
                return TargetContext()
            if api.foreground() != window or api.window_pid(window) != pid:
                return TargetContext()
            site = browser_site(exe, title)
            return TargetContext(focus=int(window), app_title=title or None, app_exe=exe,
                app_group=app_group(exe, site, self.profiles), app_site=site, process_id=pid,
                is_password=field.is_password, before_caret=field.before_caret, selection=field.selection,
                uia_status=field.status, control_type=field.control_type, field_id=field.runtime_id,
                selection_truncated=field.selection_truncated, before_caret_known=field.before_caret_known,
                selection_known=field.selection_known, after_caret=field.after_caret,
                after_caret_known=field.after_caret_known)
        except OSError:
            return TargetContext()

    def verify(self, target):
        """Fresh metadata-only check for the captured field, with no caret/selection read."""
        if self._closed:
            return "field_unavailable"
        if target.is_password:
            return "password_field"
        if target.uia_status == "not_requested" and not self._use_uia:
            return ""
        if target.uia_status != "ok" or not target.field_id:
            return "focus_changed" if target.uia_status == "changed" else "field_unavailable"
        try:
            api = self._native()
            if api.foreground() != target.focus or api.window_pid(target.focus) != target.process_id:
                return "focus_changed"
            field = self._field(target.focus, include_text=False)
            if self._closed:
                return "field_unavailable"
            if field.is_password:
                return "password_field"
            if field.status != "ok":
                return "focus_changed" if field.status == "changed" else "field_unavailable"
            if (field.runtime_id != target.field_id or api.foreground() != target.focus
                    or api.window_pid(target.focus) != target.process_id):
                return "focus_changed"
            return ""
        except Exception:
            return "field_unavailable"
