"""External F9 taps in the public FieldProbe fixture; real focus/UIA, memory delivery only."""

import argparse
import json
import math
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np

from saydraft.config import default_config
from saydraft.context.foreground import ForegroundContextProvider, NativeForegroundApi
from saydraft.context.uia_native import NativeUIAReader
from saydraft.context.uia_worker import BoundedUIA
from saydraft.core.container import Services
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.core.worker import SessionWorker
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.history import DictationHistoryStore
from saydraft.insert.guards_win import WindowsDeliveryGuard
from saydraft.insert.inserter import Inserter
from saydraft.privacy.netguard import NetworkGuard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    if args.fixture_pid <= 0 or not math.isfinite(args.timeout) or not 10 <= args.timeout <= 300:
        raise ValueError("A live fixture PID and bounded timeout are required")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "fixture_pid": args.fixture_pid, "input": "external F9 taps only; observer injects no keys",
        "delivery": "checked in-memory clipboard/keyboard stub; authored transcript",
        "owner_clipboard_accessed": False, "microphone_used": False, "asr_performed": False,
        "actual_focus_used": True, "native_integrity_guard_used": True,
        "start_menu_acceptance_performed": False, "cases": [], "errors": []}
    lock, done, delivered, text_reads = threading.RLock(), threading.Event(), [], []
    worker, hooks, owner = None, None, None
    def publish():
        with lock:
            pending = args.output / "report.pending"
            pending.write_text(json.dumps(report, indent=2), encoding="utf-8")
            pending.replace(args.output / "report.json")
    class FixtureForeground(NativeForegroundApi):
        def foreground(self):
            window = super().foreground()
            if not window:
                return None
            try:
                pid = self.window_pid(window)
                return window if pid == args.fixture_pid and self.executable(pid) == "saydraft.fieldprobe.exe" else None
            except OSError:
                return None
    class ObservedUIA(NativeUIAReader):
        def text_context(self, *args, **kwargs):
            text_reads.append(True)
            return super().text_context(*args, **kwargs)
    NetworkGuard.install()
    try:
        cfg = default_config()
        cfg["hotkeys"].update(speech="f9", speech_alternative="", speech_mouse="", save="")
        owner = BoundedUIA(factory=ObservedUIA, capture_timeout=.5)
        context = ForegroundContextProvider(api=FixtureForeground(), uia=owner)
        history = DictationHistoryStore(args.output / "history.db")
        cleaner, formatter = DictationPipeline(DictationConfig()), IdentityFormatter()
        raw = "public dictation fixture"
        expected = cleaner.process_transcript(raw, DictationContext())
        memory = NS(value="Public memory clipboard fixture")
        clipboard = NS(paste=lambda: memory.value, copy=lambda text: setattr(memory, "value", text))
        def send(key):
            rows = history.list_recent(limit=3)
            assert key == "ctrl+v" and rows and rows[0].raw_text == raw and rows[0].cleaned_text == expected
            assert memory.value == expected
            delivered.append(True)
        def no_typing(*args):
            raise AssertionError("Unexpected typing")
        inserter = Inserter(clipboard=clipboard, keyboard=NS(send=send, write=no_typing),
            focus_provider=context.focus, delivery_guard=WindowsDeliveryGuard())
        processor = TranscriptProcessor(cleaner=cleaner, formatter=formatter, history=history, inserter=inserter)
        recorder = NS(sample_rate=16000, start=lambda: None, stop=lambda: np.ones(16000, dtype=np.float32))
        asr = NS(model_id="authored-transcript-stub", transcribe=lambda audio: raw, last_timings={})
        services = Services(cfg, recorder, asr, cleaner, formatter, inserter, context, history, processor, [])
        def emit(name, *values):
            with lock:
                if name == "error":
                    report["errors"].append(name)
                    done.set()
                if name == "recording_started":
                    target = worker._target
                    report["capture"] = {"status": target.uia_status, "is_password": target.is_password,
                        "control_type": target.control_type, "fixture_pid_matched": target.process_id == args.fixture_pid}
                if name == "processing_finished":
                    result, target = worker.last_result, worker._target
                    if result is None:
                        report["errors"].append("no_completed_result")
                        done.set()
                        publish()
                        return
                    rows = history.list_recent(limit=3)
                    report["cases"].append({"capture": report.get("capture"),
                        "status": result.insertion.status, "reason": result.insertion.reason,
                        "text_reads_total": len(text_reads),
                        "deliveries_total": len(delivered), "history_rows": len(rows),
                        "raw_clean_exact": bool(rows) and all(row.raw_text == raw and row.cleaned_text == expected for row in rows),
                        "memory_restored": memory.value == "Public memory clipboard fixture"})
                    if len(report["cases"]) >= 2:
                        done.set()
                publish()
        worker = SessionWorker(services, emit=emit)
        worker.hotkeys.start()
        hooks = worker.hotkeys._controller._native.owner
        report["ready"] = worker.hotkeys.enabled and hooks.status["state"] == "running"
        publish()
        print("Ready: use the public fixture's password field and plain field, tapping F9 twice in each.", flush=True)
        deadline = time.monotonic() + args.timeout
        while not done.wait(.1) and time.monotonic() < deadline and not (args.output / "stop.request").exists():
            pass
        report["completed_in_time"] = done.is_set()
    except Exception as error:
        report["error_type"] = type(error).__name__
    finally:
        if worker is not None:
            worker.shutdown()
            worker.executor.shutdown(wait=True)
            report["serial_closed"] = not any(thread.is_alive() for thread in worker.executor._threads)
            report["native_recoveries"] = worker.hotkeys._restarts
        if owner is not None:
            owner.close()
            report["mta_closed"] = owner.wait_closed(2)
            owner._thread.join(1)
            report["mta_closed"] = report["mta_closed"] and not owner._thread.is_alive()
        report["hooks_closed"] = bool(hooks and hooks.close() and not hooks._api.handles)
        report["native_status"] = hooks.status if hooks is not None else None
        cases = report["cases"]
        report["probe_complete"] = bool(report.get("completed_in_time") and not report.get("error_type")
            and not report["errors"] and report.get("mta_closed") and report.get("serial_closed")
            and report["hooks_closed"] and report.get("native_recoveries") == 0
            and len(cases) == 2 and cases[0]["capture"]["status"] == "password"
            and cases[0]["reason"] == "password_field" and cases[0]["deliveries_total"] == 0
            and cases[0]["text_reads_total"] == 0
            and cases[1]["capture"]["status"] == "ok" and cases[1]["capture"]["control_type"] == 50004
            and cases[1]["status"] == "inserted" and cases[1]["reason"] == ""
            and cases[1]["deliveries_total"] == 1 and cases[1]["history_rows"] == 2
            and cases[1]["text_reads_total"] == 1
            and all(case["capture"]["fixture_pid_matched"] and case["raw_clean_exact"] and case["memory_restored"] for case in cases))
        publish()
        print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
