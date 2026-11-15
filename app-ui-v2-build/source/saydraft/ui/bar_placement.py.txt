"""Map native monitor identities to Qt logical work areas and watch for changes."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import logging
import sys

from PySide6 import QtCore, QtGui

logger = logging.getLogger(__name__)
EVENT_FOREGROUND = 0x0003
EVENT_MOVE_END = 0x000B
EVENT_LOCATION = 0x800B
_RETIRED_EVENTS = set()  # Pin callbacks if Windows cannot confirm unhooking.
_WIN_EVENT_PROC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(None,
    wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG, wintypes.LONG,
    wintypes.DWORD, wintypes.DWORD)


class MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


@dataclass(frozen=True)
class MonitorIdentity:
    handle: int
    device: str


class WindowsMonitorApi:
    def __init__(self, user32=None):
        self.user32 = user32 if user32 is not None else ctypes.WinDLL("user32", use_last_error=True)
        for name, result, arguments in (
            ("GetForegroundWindow", wintypes.HWND, []),
            ("MonitorFromWindow", wintypes.HANDLE, [wintypes.HWND, wintypes.DWORD]),
            ("GetMonitorInfoW", wintypes.BOOL, [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]),
            ("SetWinEventHook", wintypes.HANDLE, [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                _WIN_EVENT_PROC, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]),
            ("UnhookWinEvent", wintypes.BOOL, [wintypes.HANDLE]),
        ):
            function = getattr(self.user32, name)
            function.restype, function.argtypes = result, arguments

    def foreground_window(self):
        return self.user32.GetForegroundWindow()

    def monitor_identity(self, hwnd):
        if not hwnd:
            return None
        monitor = self.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST.
        if not monitor:
            return None
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        return MonitorIdentity(int(monitor), info.szDevice) if self.user32.GetMonitorInfoW(monitor, ctypes.byref(info)) else None

    def monitor_name(self, hwnd):
        identity = self.monitor_identity(hwnd)
        return identity.device if identity is not None else None


def native_desktop_enabled(application=None):
    application = application or QtGui.QGuiApplication.instance()
    return bool(sys.platform == "win32" and application is not None and application.platformName() == "windows")


def screen_for_device(screens, name, fallback=None):
    screens = list(screens)
    if name:
        for screen in screens:
            if screen.name().casefold() == name.casefold():
                return screen
    if any(screen is fallback for screen in screens):
        return fallback
    return screens[0] if screens else None


def screen_for_monitor(screens, monitor, fallback=None):
    screens = list(screens)
    if monitor is not None:
        for screen in screens:
            native_interface = getattr(screen, "nativeInterface", None)
            if native_interface is not None:
                try:
                    interface = native_interface()
                    if interface is not None and int(interface.handle()) == monitor.handle:
                        return screen
                except (RuntimeError, TypeError, AttributeError):
                    pass
    # Older Qt builds expose the GDI name. New Qt can expose duplicate friendly
    # model names, so those labels must never be used as a monitor identity.
    return screen_for_device(screens, monitor.device if monitor is not None else None, fallback)


def focused_screen(point_provider=None):
    application = QtGui.QGuiApplication.instance()
    if application is None:
        return None
    fallback = application.primaryScreen()
    if point_provider is not None:
        point = point_provider()
        return (application.screenAt(point) if point is not None else None) or fallback
    if not native_desktop_enabled(application):
        return fallback
    try:
        api = WindowsMonitorApi()
        monitor = api.monitor_identity(api.foreground_window())
        return screen_for_monitor(application.screens(), monitor, fallback)
    except (OSError, RuntimeError, AttributeError):
        logger.debug("Focused monitor unavailable; using the primary work area")
        return fallback


class NativeMonitorEvents:
    """Out-of-context hooks run on the Qt GUI message-pump thread."""

    def __init__(self, notify, *, api=None):
        self.notify = notify
        self.api = api if api is not None else WindowsMonitorApi()
        self.handles = []
        self.closed = True
        self.callback = _WIN_EVENT_PROC(self._event)

    def start(self):
        if not self.closed:
            return
        if self.handles:
            raise OSError("Previous monitor hooks are still retiring")
        self.closed = False
        for event in (EVENT_FOREGROUND, EVENT_MOVE_END, EVENT_LOCATION):
            handle = self.api.user32.SetWinEventHook(event, event, None, self.callback, 0, 0, 2)
            # WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS. Qt handles our Hub focus.
            if not handle:
                self.stop()
                raise OSError("Monitor event hook unavailable")
            self.handles.append(handle)

    def _event(self, _hook, event, hwnd, object_id, child_id, _thread, _time):
        if self.closed or not hwnd or event not in (EVENT_FOREGROUND, EVENT_MOVE_END, EVENT_LOCATION):
            return
        if event == EVENT_LOCATION and (object_id != 0 or child_id != 0):
            return
        try:
            if event != EVENT_FOREGROUND and hwnd != self.api.foreground_window():
                return
            self.notify()
        except Exception:
            logger.debug("Monitor event receiver unavailable")

    def stop(self):
        self.closed = True
        remaining = []
        for handle in self.handles:
            if not self.api.user32.UnhookWinEvent(handle):
                remaining.append(handle)
        self.handles = remaining
        if remaining:
            _RETIRED_EVENTS.add(self)
            logger.warning("Monitor hook retirement could not be confirmed; callback retained until exit")
        else:
            _RETIRED_EVENTS.discard(self)


class PlacementWatcher(QtCore.QObject):
    def __init__(self, refresh, *, parent=None, application=None, native_factory=NativeMonitorEvents):
        super().__init__(parent)
        self.refresh = refresh
        self.application = application or QtGui.QGuiApplication.instance()
        self.native_factory = native_factory
        self.running = False
        self.native = None
        self.connections = []
        self.screen_connections = []
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._refresh)

    def _connect(self, signal, callback, *, screen=False):
        signal.connect(callback)
        (self.screen_connections if screen else self.connections).append((signal, callback))

    @staticmethod
    def _disconnect(connections):
        for signal, callback in connections:
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass  # A removed QScreen may already have been destroyed by Qt.
        connections.clear()

    def _screens_changed(self, *_args):
        self._disconnect(self.screen_connections)
        for screen in self.application.screens():
            for name in ("availableGeometryChanged", "geometryChanged", "logicalDotsPerInchChanged"):
                self._connect(getattr(screen, name), self.request_refresh, screen=True)
        self.request_refresh()

    def start(self):
        if self.running:
            return
        self.running = True
        try:
            for name in ("screenAdded", "screenRemoved", "primaryScreenChanged"):
                self._connect(getattr(self.application, name), self._screens_changed)
            self._connect(self.application.focusWindowChanged, self.request_refresh)
            self._connect(self.application.aboutToQuit, self.stop)
            self._screens_changed()
            if self.native_factory is NativeMonitorEvents and not native_desktop_enabled(self.application):
                return
            try:
                self.native = self.native_factory(self.request_refresh)
                self.native.start()
            except OSError:
                logger.warning("Monitor event updates unavailable; work areas still refresh at dictation start")
        except Exception:
            self.stop()
            raise

    def request_refresh(self, *_args):
        if self.running and not self.timer.isActive():
            self.timer.start(0)

    def _refresh(self):
        if self.running:
            self.refresh()

    def stop(self, *_args):
        self.running = False
        self.timer.stop()
        if self.native is not None:
            self.native.stop()
            self.native = None
        self._disconnect(self.connections)
        self._disconnect(self.screen_connections)
