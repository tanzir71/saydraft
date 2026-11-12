"""Own invisible fields → bounded native context → session/rules/SQLite → memory delivery."""

import argparse
import ctypes as ct
import json
import subprocess
import threading
import time
from ctypes import wintypes as wt
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np

from saydraft.config import default_config
from saydraft.context.foreground import ForegroundContextProvider, NativeForegroundApi
from saydraft.context.uia_native import NativeUIAReader
from saydraft.context.uia_worker import BoundedUIA
from saydraft.core.container import Services
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.core.session import DictationSession
from saydraft.core.worker import SessionWorker
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.history import DictationHistoryStore
from saydraft.insert._clipboard_win32 import NativeClipboardApi
from saydraft.insert.inserter import Inserter
from saydraft.privacy.netguard import NetworkGuard


def replay(parent, child, output, password, row):
    ready, listening, finished = threading.Event(), threading.Event(), threading.Event()
    reads, delivered, errors = [], [], []
    row["native_calls"] = []
    def factory():
        try:
            reader = NativeUIAReader()
            anchor = reader.client.ElementFromHandleBuildCache(child, reader.cache)
            row["focus_property_supported"] = type(anchor.GetCurrentPropertyValueEx(
                reader.lib.UIA_HasKeyboardFocusPropertyId, True)) is bool
            row["unfocused_fixture_refused"] = not reader.same_focus(anchor)
            reader.focused_element = lambda: reader.client.ElementFromHandleBuildCache(child, reader.cache)
            reader.same_focus = lambda element: bool(reader.client.CompareElements(element, anchor))
            close = reader.close
            def retire():
                nonlocal anchor
                anchor = None
                close()
            reader.close = retire
            text = reader.text_context
            def observed(*args):
                reads.append(True)
                return text(*args)
            reader.text_context = observed
            for name in ("focused_element", "belongs", "password", "fresh_password", "control_type", "runtime_id",
                         "same_focus", "text_context"):
                method = getattr(reader, name)
                def timed(*args, _method=method, _name=name):
                    started = time.monotonic()
                    call = {"method": _name}
                    try:
                        return _method(*args)
                    except Exception as error:
                        call["error_type"] = type(error).__name__
                        raise
                    finally:
                        call["seconds"] = time.monotonic() - started
                        row["native_calls"].append(call)
                setattr(reader, name, timed)
            return reader
        finally:
            ready.set()
    class OwnForeground(NativeForegroundApi):
        def foreground(self):
            return parent  # Deliberately never queries the active application's HWND.
    owner = BoundedUIA(factory=factory, capture_timeout=.5)
    worker = None
    try:
        row["stage"] = "prepare"
        assert ready.wait(10)
        history = DictationHistoryStore(output / ("password.db" if password else "plain.db"))
        cleaner, formatter = DictationPipeline(DictationConfig()), IdentityFormatter()
        raw = "public dictation fixture"
        expected = cleaner.process_transcript(raw, DictationContext())
        memory = NS(value="Public original clipboard fixture")
        clipboard = NS(paste=lambda: memory.value, copy=lambda text: setattr(memory, "value", text))
        def send(key):
            assert key == "ctrl+v"
            rows = history.list_recent(limit=2)
            assert len(rows) == 1 and rows[0].raw_text == raw and rows[0].cleaned_text == expected
            assert memory.value == expected
            delivered.append(True)
        def no_typing(*args):
            raise AssertionError("Unexpected typing")
        context = ForegroundContextProvider(api=OwnForeground(), uia=owner)
        inserter = Inserter(clipboard=clipboard, keyboard=NS(send=send, write=no_typing),
                            focus_provider=context.focus)
        processor = TranscriptProcessor(cleaner=cleaner, formatter=formatter, history=history, inserter=inserter)
        recorder = NS(sample_rate=16000, start=lambda: None, stop=lambda: np.ones(16000, dtype=np.float32))
        asr = NS(model_id="authored-transcript-stub", transcribe=lambda audio: raw, last_timings={})
        services = Services(default_config(), recorder, asr, cleaner, formatter, inserter, context, history, processor, [])
        def emit(name, *args):
            if name == "recording_started":
                listening.set()
            if name == "processing_finished":
                finished.set()
            if name == "error":
                errors.append(name)
        clock = NS(now=0)
        worker = SessionWorker(services, emit=emit, session=DictationSession(clock=lambda: clock.now),
                               keyboard_module=NS())  # Hooks are never started.
        row["stage"] = "record"
        assert worker.start_recording() and listening.wait(5)
        clock.now = 1
        row["stage"] = "process"
        worker.stop_recording()
        assert finished.wait(10)
        worker.shutdown()
        worker.executor.shutdown(wait=True)
        assert owner.wait_closed(2)
        owner._thread.join(1)
        rows, result = history.list_recent(limit=2), worker.last_result
        row.update(captured_status=worker._target.uia_status, history_rows=len(rows),
            raw_clean_exact=len(rows) == 1 and rows[0].raw_text == raw and rows[0].cleaned_text == expected,
            status=result.insertion.status, reason=result.insertion.reason, deliveries=len(delivered),
            text_read_attempts=len(reads), memory_clipboard_restored=memory.value == "Public original clipboard fixture",
            serial_closed=not any(thread.is_alive() for thread in worker.executor._threads),
            mta_closed=not owner._thread.is_alive(), worker_busy=worker.busy, errors=len(errors))
        assert row["raw_clean_exact"] and row["memory_clipboard_restored"] and not errors
        assert row["serial_closed"] and row["mta_closed"] and not worker.busy
        assert row["focus_property_supported"] and row["unfocused_fixture_refused"]
        assert row["captured_status"] == ("password" if password else "ok")
        assert result.insertion.reason == ("password_field" if password else "")
        assert len(delivered) == (0 if password else 1) and (not password or not reads)
        row["stage"], row["complete"] = "complete", True
    finally:
        if worker is not None:
            worker.shutdown()
            worker.executor.shutdown(wait=True)
        owner.close()
        assert owner.wait_closed(2)


def probe(output, report):
    api = NativeClipboardApi()  # Only its window bindings; never opens the clipboard.
    for name, args, result in (
        ("PeekMessageW", [ct.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT], wt.BOOL),
        ("TranslateMessage", [ct.POINTER(wt.MSG)], wt.BOOL),
        ("DispatchMessageW", [ct.POINTER(wt.MSG)], ct.c_ssize_t)):
        function = getattr(api.user, name)
        function.argtypes, function.restype = args, result
    report["cases"] = []
    for password in (True, False):
        row = {"password_case": password}
        report["cases"].append(row)
        parent = api.user.CreateWindowExW(0, "STATIC", "Public UIA fixture", 0x00C80000,
                                         0, 0, 400, 120, None, None, None, None)  # Invisible captioned window.
        assert parent
        child = None
        def run():
            try:
                replay(parent, child, output, password, row)
            except Exception as error:
                row["error_type"] = type(error).__name__
        try:
            child = api.user.CreateWindowExW(0, "EDIT", "Public UIA field fixture",
                0x40000000 | (0x20 if password else 0), 0, 0, 100, 20, parent, None, None, None)
            assert child
            thread = threading.Thread(target=run, name="UIA-QA-caller", daemon=True)
            thread.start()
            deadline, message = time.monotonic() + 25, wt.MSG()
            while thread.is_alive() and time.monotonic() < deadline:
                while api.user.PeekMessageW(ct.byref(message), None, 0, 0, 1):
                    api.user.TranslateMessage(ct.byref(message))
                    api.user.DispatchMessageW(ct.byref(message))
                thread.join(.005)
            assert not thread.is_alive() and row.get("complete")
        finally:
            child_closed = not child or bool(api.user.DestroyWindow(child))
            parent_closed = bool(api.user.DestroyWindow(parent))
            assert child_closed and parent_closed
    report["own_windows_closed"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "active_application_read": False, "input_injected": False, "owner_clipboard_accessed": False,
        "asr_performed": False, "microphone_used": False, "hooks_started": False,
        "delivery": "checked in-memory clipboard/keyboard stub; authored transcript"}
    NetworkGuard.install()
    try:
        probe(args.output, report)
        report["probe_complete"] = True
    except Exception as error:
        report["error_type"], report["probe_complete"] = type(error).__name__, False
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
