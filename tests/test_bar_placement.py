import ctypes
from ctypes import wintypes
from types import SimpleNamespace

import pytest

from saydraft.ui import bar_placement as placement
from tests.test_pill_ui import qt_modules


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def disconnect(self, callback):
        self.callbacks.remove(callback)

    def emit(self, *args):
        for callback in tuple(self.callbacks):
            callback(*args)


class Screen:
    def __init__(self, name, area):
        self._name, self.area = name, area
        self.availableGeometryChanged = Signal()
        self.geometryChanged = Signal()
        self.logicalDotsPerInchChanged = Signal()

    def name(self):
        return self._name

    def availableGeometry(self):
        return self.area


class Application:
    def __init__(self, screens):
        self.items = screens
        for name in ("screenAdded", "screenRemoved", "primaryScreenChanged", "focusWindowChanged", "aboutToQuit"):
            setattr(self, name, Signal())

    def screens(self):
        return list(self.items)

    def platformName(self):
        return "offscreen"


class Native:
    instances = None

    def __init__(self, notify):
        self.notify, self.starts, self.stops = notify, 0, 0
        self.instances.append(self)

    def start(self):
        self.starts += 1

    def stop(self):
        self.stops += 1


class Function:
    def __init__(self, callback=lambda *args: 1):
        self.callback, self.calls = callback, []

    def __call__(self, *args):
        self.calls.append(args)
        return self.callback(*args)


def dll_fixture(*, name=r"\\.\DISPLAY2", hwnd=0x1234567800000042):
    def info(_monitor, pointer):
        assert pointer._obj.cbSize == ctypes.sizeof(placement.MonitorInfo)
        pointer._obj.szDevice = name
        return 1

    return SimpleNamespace(GetForegroundWindow=Function(lambda: hwnd),
        MonitorFromWindow=Function(lambda *args: 0xABCDEF1200000011),
        GetMonitorInfoW=Function(info), SetWinEventHook=Function(), UnhookWinEvent=Function())


def test_native_monitor_lookup_uses_pointer_sized_handles_and_the_extended_device_name():
    dll = dll_fixture()
    api = placement.WindowsMonitorApi(dll)
    hwnd = api.foreground_window()
    assert api.monitor_name(hwnd) == r"\\.\DISPLAY2"
    assert dll.GetForegroundWindow.restype is wintypes.HWND
    assert dll.MonitorFromWindow.restype is wintypes.HANDLE
    assert dll.MonitorFromWindow.argtypes == [wintypes.HWND, wintypes.DWORD]
    assert dll.MonitorFromWindow.calls == [(0x1234567800000042, 2)]
    assert dll.GetMonitorInfoW.calls[0][0] == 0xABCDEF1200000011


@pytest.mark.parametrize("failure", ["window", "monitor", "info"])
def test_missing_native_window_or_monitor_returns_no_device(failure):
    dll = dll_fixture()
    if failure == "window":
        dll.GetForegroundWindow.callback = lambda: 0
    elif failure == "monitor":
        dll.MonitorFromWindow.callback = lambda *args: 0
    else:
        dll.GetMonitorInfoW.callback = lambda *args: 0
    api = placement.WindowsMonitorApi(dll)
    assert api.monitor_name(api.foreground_window()) is None


def test_device_identity_selects_logical_work_area_across_mixed_dpi_gaps():
    qt = qt_modules()
    # Windows physical center (2800, 1200) lies outside this scaled Qt screen.
    first = Screen(r"\\.\DISPLAY1", qt.QtCore.QRect(0, 0, 1920, 1040))
    second = Screen(r"\\.\DISPLAY2", qt.QtCore.QRect(1920, -300, 1280, 680))
    assert not second.area.contains(qt.QtCore.QPoint(2800, 1200))
    assert placement.screen_for_device([first, second], r"\\.\display2", first) is second
    assert placement.screen_for_device([first, second], "removed", first) is first
    assert placement.screen_for_device([second], None, first) is second
    assert placement.screen_for_device([], None, first) is None


def test_native_identity_distinguishes_duplicate_qt_friendly_names():
    qt = qt_modules()
    first = Screen("LG FULL HD", qt.QtCore.QRect(0, 0, 1920, 1040))
    second = Screen("LG FULL HD", qt.QtCore.QRect(-1280, -300, 1280, 680))
    first.nativeInterface = lambda: SimpleNamespace(handle=lambda: 101)
    second.nativeInterface = lambda: SimpleNamespace(handle=lambda: 202)
    identity = placement.MonitorIdentity(202, r"\\.\DISPLAY5")
    assert placement.screen_for_monitor([first, second], identity, first) is second
    second.nativeInterface = lambda: None
    assert placement.screen_for_monitor([first, second], identity, first) is first
    assert placement.screen_for_monitor([], identity, first) is None


def test_focused_screen_resolves_the_foreground_monitor_without_converting_its_pixels(monkeypatch):
    qt = qt_modules()
    first = Screen("same model", qt.QtCore.QRect(0, 0, 1920, 1040))
    second = Screen("same model", qt.QtCore.QRect(-1280, -300, 1280, 680))
    first.nativeInterface = lambda: SimpleNamespace(handle=lambda: 101)
    second.nativeInterface = lambda: SimpleNamespace(handle=lambda: 202)
    fake = Application([first, second])
    fake.primaryScreen = lambda: first
    fake.screenAt = lambda point: second
    calls = []
    api = SimpleNamespace(foreground_window=lambda: 0x1234567800000042,
        monitor_identity=lambda hwnd: calls.append(hwnd) or placement.MonitorIdentity(202, r"\\.\DISPLAY5"))
    monkeypatch.setattr(placement.QtGui.QGuiApplication, "instance", lambda: fake)
    monkeypatch.setattr(placement, "native_desktop_enabled", lambda *args: True)
    monkeypatch.setattr(placement, "WindowsMonitorApi", lambda: api)
    assert placement.focused_screen() is second
    assert calls == [0x1234567800000042]
    assert placement.focused_screen(lambda: qt.QtCore.QPoint(-500, 0)) is second
    assert placement.focused_screen(lambda: None) is first
    assert len(calls) == 1  # An injected point provider never touches native focus.


def test_native_hook_failure_keeps_qt_work_area_updates_and_stop_available():
    qt = qt_modules()
    fake = Application([Screen("fixture", qt.QtCore.QRect(0, 0, 800, 600))])
    calls, retired = [], []

    class MissingEvents:
        def __init__(self, notify):
            pass

        def start(self):
            raise OSError("fixture hook unavailable")

        def stop(self):
            retired.append(True)

    watcher = placement.PlacementWatcher(lambda: calls.append(True), application=fake, native_factory=MissingEvents)
    watcher.start()
    qt.QtWidgets.QApplication.processEvents()
    fake.items[0].availableGeometryChanged.emit()
    qt.QtWidgets.QApplication.processEvents()
    assert len(calls) == 2
    watcher.stop()
    assert retired == [True] and not watcher.running


def test_offscreen_lookup_and_default_watcher_never_open_a_native_desktop_api(monkeypatch):
    qt = qt_modules()
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Native desktop access from offscreen QA")

    monkeypatch.setattr(placement.ctypes, "WinDLL", forbidden, raising=False)
    assert placement.focused_screen() is qt.QtGui.QGuiApplication.primaryScreen()
    fake = Application([Screen("fixture", qt.QtCore.QRect(0, 0, 800, 600))])
    watcher = placement.PlacementWatcher(lambda: None, application=fake)
    watcher.start()
    assert watcher.native is None and not attempts
    watcher.stop()


def test_native_callbacks_filter_background_and_child_moves_and_stop_safely():
    dll = dll_fixture()
    handles = iter((101, 102, 103))
    dll.SetWinEventHook.callback = lambda *args: next(handles)
    api = placement.WindowsMonitorApi(dll)
    notifications = []
    events = placement.NativeMonitorEvents(lambda: notifications.append(True), api=api)
    events.start()
    events.start()
    assert len(dll.SetWinEventHook.calls) == 3
    for arguments, event in zip(dll.SetWinEventHook.calls,
            (placement.EVENT_FOREGROUND, placement.EVENT_MOVE_END, placement.EVENT_LOCATION)):
        assert arguments[:3] == (event, event, None)
        assert arguments[3] is events.callback and arguments[4:] == (0, 0, 2)
    events.callback(101, placement.EVENT_FOREGROUND, 7, 0, 0, 0, 0)
    events.callback(103, placement.EVENT_LOCATION, 0x1234567800000042, 0, 0, 0, 0)
    assert len(notifications) == 2
    events.callback(103, placement.EVENT_LOCATION, 7, 0, 0, 0, 0)
    events.callback(103, placement.EVENT_LOCATION, 0x1234567800000042, -4, 0, 0, 0)
    events.callback(103, placement.EVENT_LOCATION, 0x1234567800000042, 0, 1, 0, 0)
    assert len(notifications) == 2
    events.stop()
    events.callback(101, placement.EVENT_FOREGROUND, 7, 0, 0, 0, 0)
    events.stop()
    assert len(notifications) == 2
    assert [args[0] for args in dll.UnhookWinEvent.calls] == [101, 102, 103]


def test_partial_native_registration_is_retired_and_failed_unhook_pins_a_closed_callback():
    dll = dll_fixture()
    results = iter((101, 0))
    dll.SetWinEventHook.callback = lambda *args: next(results)
    dll.UnhookWinEvent.callback = lambda *args: 0
    events = placement.NativeMonitorEvents(lambda: pytest.fail("Closed callback used"),
        api=placement.WindowsMonitorApi(dll))
    try:
        with pytest.raises(OSError, match="unavailable"):
            events.start()
        assert events.closed and events in placement._RETIRED_EVENTS
        events.callback(101, placement.EVENT_FOREGROUND, 7, 0, 0, 0, 0)
    finally:
        dll.UnhookWinEvent.callback = lambda *args: 1
        events.stop()
    assert events not in placement._RETIRED_EVENTS


def test_watcher_coalesces_changes_rebinds_topology_and_quiesces_on_stop():
    qt = qt_modules()
    Native.instances = []
    first = Screen("first", qt.QtCore.QRect(0, 0, 1000, 800))
    fake = Application([first])
    calls = []
    watcher = placement.PlacementWatcher(lambda: calls.append(True), application=fake, native_factory=Native)
    watcher.start()
    for _ in range(10):
        first.geometryChanged.emit()
        first.availableGeometryChanged.emit()
        first.logicalDotsPerInchChanged.emit()
        fake.focusWindowChanged.emit()
        Native.instances[-1].notify()
    qt.QtWidgets.QApplication.processEvents()
    assert len(calls) == 1 and Native.instances[-1].starts == 1
    second = Screen("second", qt.QtCore.QRect(-1000, -200, 1000, 700))
    fake.items = [second]
    fake.screenRemoved.emit(first)
    assert not first.geometryChanged.callbacks and len(second.geometryChanged.callbacks) == 1
    watcher.stop()
    qt.QtWidgets.QApplication.processEvents()
    assert len(calls) == 1 and Native.instances[0].stops == 1
    assert not second.geometryChanged.callbacks and not fake.focusWindowChanged.callbacks
    watcher.request_refresh()
    qt.QtWidgets.QApplication.processEvents()
    assert len(calls) == 1
    watcher.start()
    qt.QtWidgets.QApplication.processEvents()
    assert len(calls) == 2 and len(Native.instances) == 2
    watcher.stop()


@pytest.mark.parametrize("state", ["idle", "preparing", "recording", "processing", "warning", "error"])
def test_relocation_preserves_state_deadlines_and_action_target(state):
    from saydraft.ui.pill import SaydraftPill

    qt = qt_modules()
    Native.instances = []
    area = [qt.QtCore.QRect(0, 0, 1920, 1040)]
    fake = Application([Screen("fixture", area[0])])
    scheduled = []
    bar = SaydraftPill(screen_geometry_provider=lambda: area[0],
        timer_single_shot=lambda ms, callback: scheduled.append((ms, callback)),
        placement_watcher_factory=lambda refresh, **kwargs: placement.PlacementWatcher(refresh,
            application=fake, native_factory=Native, **kwargs))
    if state == "idle":
        bar.show_idle()
    elif state == "preparing":
        bar.show_preparing(hands_free=True)
    elif state == "warning":
        bar.show_not_inserted("focus_changed", saved=True)
    elif state == "error":
        bar.show_error("No microphone")
    else:
        bar.show_recording(hands_free=True)
        if state == "processing":
            bar.show_processing()
    try:
        qt.QtWidgets.QApplication.processEvents()
        previous = bar.state, bar._visibility_generation, bar.status_label.text(), bar.elapsed_label.text(), len(scheduled)
        area[0] = qt.QtCore.QRect(-1280, -300, 1280, 680)
        Native.instances[-1].notify()
        qt.QtWidgets.QApplication.processEvents()
        assert (bar.state, bar._visibility_generation, bar.status_label.text(), bar.elapsed_label.text(), len(scheduled)) == previous
        assert bar.geometry().bottom() == area[0].y() + area[0].height() - 25
        assert abs(bar.geometry().center().x() - area[0].center().x()) <= 1
        if bar.target.isVisible() and bar.target.kind != "expand":
            assert bar.rect().contains(bar.mapFromGlobal(bar.target.geometry().center()))
        assert len(Native.instances) == 1
        Native.instances[0].notify()
        bar.hide()
        qt.QtWidgets.QApplication.processEvents()
        assert not bar.isVisible() and not bar.target.isVisible() and not bar._placement_watcher.running
    finally:
        bar.hide()
        bar.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def test_warning_width_recovers_after_a_small_monitor_and_hidden_refresh_does_nothing():
    from saydraft.ui.pill import SaydraftPill

    qt = qt_modules()
    area = [qt.QtCore.QRect(0, 0, 1920, 1040)]
    reads = []
    bar = SaydraftPill(screen_geometry_provider=lambda: reads.append(True) or area[0])
    bar.show_not_inserted("insertion_unconfirmed", saved=True)
    original = bar.width()
    area[0] = qt.QtCore.QRect(1920, 0, 400, 600)
    bar.refresh_placement()
    assert bar.width() == 368
    area[0] = qt.QtCore.QRect(0, 0, 1920, 1040)
    bar.refresh_placement()
    assert bar.width() == original
    bar.hide()
    previous = len(reads)
    bar.refresh_placement()
    assert len(reads) == previous and not bar.isVisible()
