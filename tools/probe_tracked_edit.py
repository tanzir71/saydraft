"""Own invisible EDIT → native scoped observation → correction; no OS input/clipboard."""

import argparse
import ctypes as ct
import json
import os
import queue
import hashlib
import subprocess
import threading
import time
from contextlib import contextmanager
from ctypes import wintypes as wt
from pathlib import Path

from saydraft.context.tracked_edit import FieldIdentity, ObservedEdit, TrackedEditReader
from saydraft.context.observation_worker import ObservationWorker
from saydraft.context.focused_edit import read_focused_edit
from saydraft.context.uia_native import NativeUIAReader
from saydraft.dictionary.alignment import suggest_correction
from saydraft.insert._clipboard_win32 import NativeClipboardApi


def asynchronous_case(metadata, identity, mutate, child, row):
    now = [0]
    entered, release = threading.Event(), threading.Event()
    def factory():
        native = NativeUIAReader()
        row["observation_thread"] = threading.get_ident()
        native.focused_element = lambda: native.client.ElementFromHandleBuildCache(child, native.cache)
        native.keyboard_focus_snapshot = lambda element: True  # Own invisible fixture only.
        edges, read = native.insertion_edges, native._read_range
        def gated(*args):
            entered.set()
            assert release.wait(5)
            return edges(*args)
        def counted(*args):
            row["observation_reads"] = row.get("observation_reads", 0) + 1
            return read(*args)
        native.insertion_edges, native._read_range = gated, counted
        return native
    owner = ObservationWorker(factory=factory, clock=lambda: now[0])
    try:
        started = time.perf_counter()
        ticket = owner.prepare(identity)
        row["prepare_call_seconds"] = time.perf_counter() - started
        assert ticket is not None and entered.wait(5) and not ticket.ready.is_set()
        # The real critical reader on this separate MTA can verify its own field
        # while the background owner prepares. No proxy crosses between them.
        metadata.same_focus = lambda element: True  # Own fixture cannot receive desktop focus.
        row["async_stage"] = "critical_metadata"
        row["critical_status"] = read_focused_edit(metadata, identity.window, include_text=False).status
        assert row["critical_status"] == "ok"
        release.set()
        row["async_stage"] = "reserve"
        assert ticket.ready.wait(5) and owner.reserve(ticket)
        mutate("insert")
        started = time.perf_counter()
        assert owner.commit(ticket, "Kubernetis")
        row["commit_call_seconds"] = time.perf_counter() - started
        assert ticket.active.wait(5) and not ticket.done.is_set()
        mutate("correction")
        now[0] = 15
        owner._wake.set()
        assert ticket.done.wait(5)
        result = owner.take(ticket)
        assert result == ObservedEdit("Kubernetis", "Kubernetes")
        assert suggest_correction(result.original, result.current, "en").term == "Kubernetes"
        assert row["observation_thread"] != threading.get_ident()
        row["independent_critical_reader"] = True
    finally:
        release.set()
        owner.close()
        assert owner.wait_closed(5)
        row["observation_closed"] = True


def probe():
    api = NativeClipboardApi()  # Window bindings only; never open any clipboard.
    for name, args, result in (
        ("SendMessageW", [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM], ct.c_ssize_t),
        ("PeekMessageW", [ct.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT], wt.BOOL),
        ("TranslateMessage", [ct.POINTER(wt.MSG)], wt.BOOL),
        ("DispatchMessageW", [ct.POINTER(wt.MSG)], ct.c_ssize_t)):
        function = getattr(api.user, name)
        function.argtypes, function.restype = args, result
    report = {"active_application_read": False, "input_injected": False,
        "owner_clipboard_accessed": False, "cases": [], "failures": [], "fixture_actions": [],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "source_sha256": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (
            "saydraft/context/tracked_edit.py", "saydraft/context/uia_native.py",
            "saydraft/context/observation_worker.py", "tools/probe_tracked_edit.py")}}
    @contextmanager
    def fixture_window():
        parent = api.user.CreateWindowExW(0, "STATIC", "Public tracked-edit fixture", 0x00C80000,
            0, 0, 400, 120, None, None, None, None)
        assert parent
        try:
            yield parent
        finally:
            assert api.user.DestroyWindow(parent)
    with fixture_window() as parent:
        for case in ("correction", "runtime_lookup", "password", "becomes_password", "asynchronous"):
            child = api.user.CreateWindowExW(0, "EDIT", "Before 🙂 OLD after.",
                (0x00C80000 if case == "runtime_lookup" else 0x40000000) | (0x20 if case == "password" else 0),
                0, 0, 300, 40, None if case == "runtime_lookup" else parent, None, None, None)
            assert child
            prefix = len("Before 🙂 ".encode("utf-16-le")) // 2
            api.user.SendMessageW(child, 0xB1, prefix, prefix + 3)  # Select fixture OLD only.
            commands = queue.Queue()
            def mutate(operation):
                acknowledged = threading.Event()
                commands.put((operation, acknowledged))
                assert acknowledged.wait(5)
            def run():
                reader = observer = None
                row = {"case": case, "reads": 0}
                def timed(stage, call):
                    started = time.perf_counter()
                    value = call()
                    row[stage + "_seconds"] = time.perf_counter() - started
                    return value
                try:
                    reader = NativeUIAReader()
                    if case == "runtime_lookup":
                        reader.field_handle = lambda element: 0  # Exercise the HWND-less lookup route on an owned element.
                    reader.focused_element = lambda: reader.client.ElementFromHandleBuildCache(child, reader.cache)
                    reader.keyboard_focus_snapshot = lambda element: True  # Own invisible fixture cannot receive desktop focus.
                    identity = FieldIdentity(child if case == "runtime_lookup" else parent, os.getpid(),
                        reader.current_runtime_id(reader.focused_element()))
                    mutate("select")  # Establish the fixture selection after its UIA provider exists.
                    now = [0]
                    observer = TrackedEditReader(reader, clock=lambda: now[0])
                    read = reader._read_range
                    def counted(*args):
                        row["reads"] += 1
                        return read(*args)
                    reader._read_range = counted
                    row["stage"] = "capture"
                    if case == "asynchronous":
                        asynchronous_case(reader, identity, mutate, child, row)
                        row["complete"] = True
                        report["cases"].append(row)
                        return
                    ticket = timed("capture", lambda: observer.begin(identity, "Kubernetis"))
                    if case == "password":
                        assert ticket is None and row["reads"] == 0
                    else:
                        assert ticket is not None
                        mutate("insert")
                        row["stage"] = "confirm"
                        assert timed("confirm", lambda: observer.confirm(ticket))
                        def forbidden():
                            raise AssertionError("Never query another focused element")
                        reader.focused_element = forbidden
                        reads = row["reads"]
                        assert observer.check(ticket) is None and row["reads"] == reads
                        mutate(case)
                        now[0] = 15
                        row["stage"] = "read_correction"
                        result = timed("check", lambda: observer.check(ticket))
                        if case in ("correction", "runtime_lookup"):
                            assert result == ObservedEdit("Kubernetis", "Kubernetes")
                            assert suggest_correction(result.original, result.current, "en").term == "Kubernetes"
                        else:
                            assert result == ObservedEdit("", "") and row["reads"] == reads
                    row["complete"] = True
                    report["cases"].append(row)
                except Exception as error:
                    report["failures"].append({**row, "error_type": type(error).__name__})
                finally:
                    if observer is not None:
                        observer.clear()
                    if reader is not None:
                        reader.close()
            thread = threading.Thread(target=run, daemon=True)
            try:
                thread.start()
                deadline, message = time.monotonic() + 15, wt.MSG()
                while thread.is_alive() and time.monotonic() < deadline:
                    try:
                        requested, acknowledged = commands.get_nowait()
                    except queue.Empty:
                        requested = None
                    if requested is not None:
                        if requested == "select":
                            api.user.SendMessageW(child, 0xB1, prefix, prefix + 3)
                        elif requested == "becomes_password":
                            api.user.SendMessageW(child, 0xCC, ord("*"), 0)
                        else:
                            value = "Kubernetis" if requested == "insert" else "Kubernetes"
                            if requested != "insert":
                                api.user.SendMessageW(child, 0xB1, prefix, prefix + len("Kubernetis"))
                            buffer = ct.create_unicode_buffer(value)
                            api.user.SendMessageW(child, 0xC2, 0, ct.cast(buffer, ct.c_void_p).value)
                        report["fixture_actions"].append({"case": case, "action": requested})
                        acknowledged.set()
                    while api.user.PeekMessageW(ct.byref(message), None, 0, 0, 1):
                        api.user.TranslateMessage(ct.byref(message))
                        api.user.DispatchMessageW(ct.byref(message))
                    thread.join(.005)
                assert not thread.is_alive()
            finally:
                assert api.user.DestroyWindow(child)
    report["own_windows_closed"] = True
    report["probe_complete"] = len(report["cases"]) == 5 and not report["failures"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = probe()
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
