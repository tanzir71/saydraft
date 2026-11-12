"""Read only this probe's invisible EDIT controls through a windowless MTA client."""

import argparse
import ctypes as ct
import json
import subprocess
import threading
import time
from ctypes import wintypes as wt
from pathlib import Path

from saydraft.context.focused_edit import read_focused_edit
from saydraft.context.uia_native import NativeUIAReader
from saydraft.insert._clipboard_win32 import NativeClipboardApi


def probe(report):
    api = NativeClipboardApi()  # Window allocation only: never opens the clipboard.
    for name, args, result in (
        ("PeekMessageW", [ct.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT], wt.BOOL),
        ("TranslateMessage", [ct.POINTER(wt.MSG)], wt.BOOL),
        ("DispatchMessageW", [ct.POINTER(wt.MSG)], ct.c_ssize_t)):
        function = getattr(api.user, name)
        function.argtypes, function.restype = args, result
    report["results"], report["failures"] = [], []
    with api.window() as parent:
        for password in (True, False):
            child = api.user.CreateWindowExW(0, "EDIT", "Public UIA fixture",
                0x40000000 | (0x20 if password else 0), 0, 0, 100, 20, parent, None, None, None)
            assert child
            def run():
                reader, element = None, None
                reads = []
                try:
                    reader = NativeUIAReader()
                    element = reader.client.ElementFromHandle(child)
                    reader.focused_element = lambda: element
                    reader.same_focus = lambda value: bool(reader.client.CompareElements(value, element))
                    if password:
                        def forbidden(*args):
                            reads.append(True)
                            raise AssertionError("Password read")
                        reader.text_context = forbidden
                    result = read_focused_edit(reader, child)
                    assert not reads
                    assert result.is_password == password and result.status == ("password" if password else "ok")
                    assert password or result.control_type == 50004
                    report["results"].append({"is_password": result.is_password, "status": result.status,
                                              "control_type": result.control_type})
                except Exception as error:
                    report["failures"].append(type(error).__name__)
                finally:
                    element = None
                    if reader is not None:
                        try:
                            reader.close()
                            reader.close()  # Idempotent; no second CoUninitialize.
                        except Exception as error:
                            report["failures"].append(type(error).__name__)
            thread = threading.Thread(target=run, daemon=True)
            try:
                thread.start()
                deadline, message = time.monotonic() + 10, wt.MSG()
                while thread.is_alive() and time.monotonic() < deadline:
                    while api.user.PeekMessageW(ct.byref(message), None, 0, 0, 1):
                        api.user.TranslateMessage(ct.byref(message))
                        api.user.DispatchMessageW(ct.byref(message))
                    thread.join(.005)
                assert not thread.is_alive()
            finally:
                assert api.user.DestroyWindow(child)
    report["own_windows_closed"] = True
    assert len(report["results"]) == 2 and not report["failures"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "input_injected": False, "owner_clipboard_accessed": False, "active_application_read": False}
    try:
        probe(report)
        report["probe_complete"] = True
    except Exception as error:
        report["error_type"], report["probe_complete"] = type(error).__name__, False
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
