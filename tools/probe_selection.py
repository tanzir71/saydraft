"""Native selection leases on this process's invisible EDIT; never owner focus/input."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
from ctypes import wintypes as wt
import json
from pathlib import Path
import subprocess
import threading
import time

from saydraft.context.foreground import ForegroundContextProvider, NativeForegroundApi
from saydraft.context.uia_native import NativeUIAReader
from saydraft.context.uia_worker import BoundedUIA
from saydraft.insert._clipboard_win32 import NativeClipboardApi
from tools.owned_uia import message_waiter, prepare_owned_element


def probe(report):
    api = NativeClipboardApi()  # Uses only window allocation; never opens the clipboard.
    user = api.user
    wait_messages = message_waiter(user)
    for name, args, result in (
        ("PeekMessageW", [ct.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT], wt.BOOL),
        ("TranslateMessage", [ct.POINTER(wt.MSG)], wt.BOOL),
        ("DispatchMessageW", [ct.POINTER(wt.MSG)], ct.c_ssize_t),
        ("SendMessageW", [wt.HWND, wt.UINT, ct.c_size_t, ct.c_ssize_t], ct.c_ssize_t)):
        function = getattr(user, name)
        function.argtypes, function.restype = args, result
    parent = user.CreateWindowExW(0, "STATIC", "Public selection fixture", 0x00C80000,
                                  0, 0, 400, 120, None, None, None, None)
    assert parent
    child = user.CreateWindowExW(0, "EDIT", "", 0x40000000 | 0x0004 | 0x0100,
                                 0, 0, 300, 100, parent, None, None, None)
    assert child
    owner = context = None
    ready = threading.Event()
    report["cases"], report["reads"] = [], 0

    def pump_until(done, seconds):
        deadline, message = time.monotonic() + seconds, wt.MSG()
        while not done() and time.monotonic() < deadline:
            while user.PeekMessageW(ct.byref(message), None, 0, 0, 1):
                user.TranslateMessage(ct.byref(message))
                user.DispatchMessageW(ct.byref(message))
            wait_messages()
        if not done():
            raise TimeoutError("Owned selection fixture did not retire")

    def call(action):
        with ThreadPoolExecutor(max_workers=1) as caller:
            future = caller.submit(action)
            pump_until(future.done, 3)
            return future.result()

    def set_text(text, start, end):
        # Direct messages to the two verified own handles; no SendInput/focus change.
        value = ct.create_unicode_buffer(text)
        user.SendMessageW(child, 0x000C, 0, ct.addressof(value))  # WM_SETTEXT
        user.SendMessageW(child, 0x00B1, start, end)  # EM_SETSEL, UTF-16 offsets

    def factory():
        native = NativeUIAReader()
        try:
            prepare_owned_element(native, child, report)
            native.focused_element = lambda: native.client.ElementFromHandleBuildCache(child, native.cache)
            native.same_focus = lambda element: True  # Owned invisible provider only; no global focus read.
            original = native.selection_text
            def read(*args):
                report["reads"] += 1
                return original(*args)
            native.selection_text = read
            ready.set()
            return native
        except Exception as error:
            report["factory_error"] = {"type": type(error).__name__, "hresult": getattr(error, "hresult", None)}
            native.close()
            raise

    class Foreground(NativeForegroundApi):
        def foreground(self):
            return child

    try:
        owner = BoundedUIA(factory=factory, capture_timeout=.5)
        context = ForegroundContextProvider(api=Foreground(), uia=owner)
        pump_until(lambda: ready.is_set() or owner.wait_closed(0), 5)
        assert ready.is_set()
        payload = "😀" * 600 + " Middle " + "x" * 200
        units = len(payload.encode("utf-16-le")) // 2
        set_text("prefix " + payload + " suffix", 7, 7 + units)
        captured = call(context.capture_selection)
        report["cases"].append({"case": "long_selection", "status": captured.selection.status,
            "selected_units": len(captured.target.selection.encode("utf-16-le")) // 2,
            "exact": captured.target.selection == payload})
        assert captured.selection.status == "ready" and captured.target.selection == payload
        assert not captured.target.before_caret_known and not captured.target.after_caret_known
        assert call(lambda: context.verify_selection(captured)) == ""
        set_text("same | same", 0, 4)
        captured = call(context.capture_selection)
        assert captured.selection.status == "ready" and captured.target.selection == "same"
        user.SendMessageW(child, 0x00B1, 7, 11)
        reason = call(lambda: context.verify_selection(captured))
        report["cases"].append({"case": "same_text_new_range", "reason": reason})
        assert reason == "selection_changed"
        set_text("alpha", 0, 5)
        captured = call(context.capture_selection)
        assert captured.selection.status == "ready"
        set_text("omega", 0, 5)
        reason = call(lambda: context.verify_selection(captured))
        report["cases"].append({"case": "changed_text", "reason": reason})
        assert reason
        set_text("Public", 0, 6)
        user.SendMessageW(child, 0x00CF, 1, 0)  # EM_SETREADONLY
        captured = call(context.capture_selection)
        assert captured.selection.status == "ready" and captured.selection.read_only is True
        assert call(lambda: context.verify_selection(captured, for_write=False)) == ""
        reason = call(lambda: context.verify_selection(captured))
        report["cases"].append({"case": "read_only", "reason": reason})
        assert reason == "read_only"
        user.SendMessageW(child, 0x00CC, ord("*"), 0)  # EM_SETPASSWORDCHAR
        before = report["reads"]
        captured = call(context.capture_selection)
        report["cases"].append({"case": "password", "status": captured.selection.status,
                                "no_text_read": report["reads"] == before})
        assert captured.selection.status == "password_field" and not captured.target.selection
        assert report["reads"] == before
        user.SendMessageW(child, 0x00CC, 0, 0)
        user.SendMessageW(child, 0x00CF, 0, 0)
        set_text("Public", 0, 6)
        captured = call(context.capture_selection)
        assert captured.selection.status == "ready"
        assert context.cancel_selection(captured)
        reason = call(lambda: context.verify_selection(captured))
        report["cases"].append({"case": "cancel", "reason": reason})
        assert reason == "selection_expired"
    finally:
        if context is not None:
            context.close()
        elif owner is not None:
            owner.close()
        if owner is not None:
            pump_until(lambda: owner.wait_closed(0), 3)
            report["mta_closed"] = True
        assert user.DestroyWindow(child)
        assert user.DestroyWindow(parent)
        report["own_windows_closed"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"probe_complete": False,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True)),
        "input_injected": False, "owner_clipboard_accessed": False, "active_application_read": False,
        "microphone_used": False, "scope": "invisible own EDIT, actual native ranges and bounded owner; fixture substitutes own focus; physical focus/insertion unmeasured"}
    try:
        probe(report)
        report["probe_complete"] = True
    except Exception as error:
        report["error_type"] = type(error).__name__
        trace = error.__traceback__
        while trace.tb_next is not None:
            trace = trace.tb_next
        report["error_location"] = {"file": Path(trace.tb_frame.f_code.co_filename).name, "line": trace.tb_lineno}
        report["hresult"] = getattr(error, "hresult", None)
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
