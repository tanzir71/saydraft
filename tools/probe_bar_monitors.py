"""Verify monitor identity and WinEvent ABI using only hidden owned windows."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def probe(output: Path):
    if sys.platform != "win32":
        raise OSError("The hidden native monitor probe requires Windows")
    os.environ["QT_QPA_PLATFORM"] = "windows"
    os.environ.pop("QT_SCALE_FACTOR", None)
    from PySide6 import QtCore, QtWidgets
    from saydraft.privacy.netguard import NetworkGuard
    from saydraft.ui.bar_placement import EVENT_LOCATION, MonitorInfo, NativeMonitorEvents, WindowsMonitorApi, screen_for_monitor
    from saydraft.ui.pill import SaydraftPill

    NetworkGuard.install()
    application = QtWidgets.QApplication([])
    assert application.platformName() == "windows"
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Hidden-window probe attempted foreground, clipboard or microphone access")

    QtWidgets.QApplication.clipboard = staticmethod(forbidden)
    sys.modules["sounddevice"] = SimpleNamespace(InputStream=forbidden, query_devices=forbidden)
    api = WindowsMonitorApi()
    api.foreground_window = forbidden
    visible = api.user32.IsWindowVisible
    visible.argtypes, visible.restype = [wintypes.HWND], wintypes.BOOL
    notify = api.user32.NotifyWinEvent
    notify.argtypes = [wintypes.DWORD, wintypes.HWND, wintypes.LONG, wintypes.LONG]
    notify.restype = None
    position = api.user32.SetWindowPos
    position.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT]
    position.restype = wintypes.BOOL
    screens = application.screens()
    assert screens
    # An injected area prevents the Bar from querying focus or starting global hooks.
    bar = SaydraftPill(screen_geometry_provider=lambda: screens[0].availableGeometry())
    bar.setFixedSize(164, 36)
    hwnd = int(bar.winId())
    assert hwnd and not visible(hwnd)
    rows, callbacks = [], []
    events = None
    try:
        for screen in screens:
            area = screen.availableGeometry()
            # QWidget defers moves while hidden. Place only our native HWND,
            # without showing/activating it, to test identity on every monitor.
            native = screen.nativeInterface()
            assert native is not None
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(info)
            assert api.user32.GetMonitorInfoW(int(native.handle()), ctypes.byref(info))
            assert position(hwnd, None, info.rcWork.left + (info.rcWork.right - info.rcWork.left - 164) // 2,
                info.rcWork.bottom - 36 - 24, 164, 36, 0x0010 | 0x0004 | 0x0200)
            application.processEvents()
            assert not visible(hwnd)
            monitor = api.monitor_identity(hwnd)
            selected = screen_for_monitor(screens, monitor, application.primaryScreen())
            assert selected is screen, (monitor, screen.name())
            rows.append({"device": monitor.device, "qt_screen_label": screen.name(),
                "logical_work_area": list(area.getRect()), "screen_dpr": screen.devicePixelRatio(),
                "window_dpr": bar.devicePixelRatioF(), "identity_matched": True, "visible": False})

        # Scope every native hook to this process; never subscribe to owner events.
        def set_owned_hook(first, last, module, callback, _process, thread, _flags):
            return api.user32.SetWinEventHook(first, last, module, callback, os.getpid(), thread, 0)

        owned_api = SimpleNamespace(user32=SimpleNamespace(SetWinEventHook=set_owned_hook,
            UnhookWinEvent=api.user32.UnhookWinEvent), foreground_window=lambda: hwnd)
        events = NativeMonitorEvents(lambda: callbacks.append(threading.get_ident()), api=owned_api)
        events.start()
        notify(EVENT_LOCATION, hwnd, 0, 0)
        deadline = time.monotonic() + 2
        while not callbacks and time.monotonic() < deadline:
            application.processEvents()
            threading.Event().wait(.005)
        assert callbacks and set(callbacks) == {threading.get_ident()}
        events.stop()
        assert not events.handles
        before = len(callbacks)
        notify(EVENT_LOCATION, hwnd, 0, 0)
        application.processEvents()
        assert len(callbacks) == before and not visible(hwnd) and not attempts
        report = {"source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
            "platform": application.platformName(), "qt": QtCore.qVersion(),
            "mode": "hidden owned windows; native hooks restricted to this process",
            "positioning": "native hidden HWND only; visible mixed-DPI Qt movement remains manual acceptance",
            "screens": rows, "owned_callbacks": len(callbacks), "callbacks_on_gui_thread": True,
            "native_hooks_retired": True, "network_guard_enabled": bool(NetworkGuard._originals),
            "active_application_read": False, "owner_clipboard_accessed": False,
            "microphone_opened": False, "input_sent": False, "global_hooks_installed": False}
        output.mkdir(parents=True, exist_ok=False)
        (output / "monitors.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        if events is not None:
            events.stop()
        bar.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New directory for the owned-window report")
    report = probe(parser.parse_args().output)
    print(json.dumps({"screens": len(report["screens"]), "owned_callbacks": report["owned_callbacks"],
        "callbacks_on_gui_thread": report["callbacks_on_gui_thread"], "native_hooks_retired": report["native_hooks_retired"]}))


if __name__ == "__main__":
    main()
