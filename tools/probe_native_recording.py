"""Native key → session → bundled speech → private History → stub insertion."""

import argparse
import ctypes as c
import json
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import soundfile as sf

from saydraft.asr.sherpa_parakeet import ParakeetEngine
from saydraft.config import default_config
from saydraft.core.container import Services
from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.core.worker import SessionWorker
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.history import DictationHistoryStore
from saydraft.input_origin import SAYDRAFT_INPUT_TAG
from saydraft.insert.inserter import InsertionResult
from saydraft.insert.sendinput import _Input, _KeyboardInput
from saydraft.models.benchmark import fixture_path
from saydraft.privacy.netguard import NetworkGuard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parakeet-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "delivery": "vkE8 only; bundled audio, isolated SQLite, stub insertion; no microphone or OS paste",
        "start_menu_acceptance_performed": False}
    worker, hooks = None, None
    listening, finished, errors, inserts = threading.Event(), threading.Event(), [], []
    NetworkGuard.install()
    try:
        audio, rate = sf.read(fixture_path(), dtype="float32")
        asr, pipeline = ParakeetEngine(model_dir=args.parakeet_dir), DictationPipeline(DictationConfig())
        expected = pipeline.process_transcript(asr.transcribe(audio), DictationContext())
        if not expected.strip():
            raise ValueError("Bundled speech produced empty output")
        cfg = default_config()
        cfg["hotkeys"].update(speech="vkE8", speech_alternative="", cancel="", save="")
        history = DictationHistoryStore(args.output / "history.db")
        def row_count():
            with sqlite3.connect(history.db_path) as db:
                return db.execute("SELECT count(*) FROM dictations").fetchone()[0]
        def insert(text, **kwargs):
            assert row_count() == 1  # History must precede every delivery.
            inserts.append(text)
            return InsertionResult("inserted", "fixture")
        capture = SimpleNamespace(sample_rate=rate, start=lambda: None, stop=lambda: audio.copy())
        formatter, inserter = IdentityFormatter(), SimpleNamespace(insert_text=insert)
        processor = TranscriptProcessor(cleaner=pipeline, formatter=formatter, history=history, inserter=inserter)
        services = Services(cfg, capture, asr, pipeline, formatter, inserter,
            SimpleNamespace(capture=lambda: TargetContext("fixture", "Native Hotkey QA")), history, processor, [])
        def emit(name, *values):
            if name == "recording_started":
                listening.set()
            if name == "processing_finished":
                finished.set()
            if name == "error":
                errors.append(name)
        worker = SessionWorker(services, emit=emit)
        original_stop = worker.hotkeys.stop_timed
        def stop(when):
            report["native_release_timestamp"] = when
            original_stop(when)
        worker.hotkeys.stop_timed = stop
        worker.hotkeys.start()  # Default native route; no injected keyboard backend.
        hooks = worker.hotkeys._controller._native.owner
        def send(flags):
            value = _Input()
            value.type = 1
            value.data.ki = _KeyboardInput(0xE8, 0, flags, 0, SAYDRAFT_INPUT_TAG ^ 1)
            assert hooks._api.user.SendInput(1, (_Input * 1)(value), c.sizeof(_Input)) == 1
        send(0)
        assert listening.wait(5)
        time.sleep(.65)  # Preserve the production 0.5 s recording guard.
        started = time.monotonic()
        send(2)
        assert finished.wait(30)
        report["release_seconds"] = time.monotonic() - started
        report["history_rows"], report["insertions"] = row_count(), len(inserts)
        report["exact_fixture_result"] = inserts == [expected]
        report["native_release_budget"] = worker._context.cleanup_deadline == report["native_release_timestamp"] + 2
        report["asr_model"] = asr.model_id
        report["native_recoveries"] = worker.hotkeys._restarts
        report["hook_failure_reason"] = worker.hotkeys._failure_reason
        report["errors"] = errors
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        if worker is not None:
            worker.shutdown()
            worker.executor.shutdown(wait=True)
        report["closed"] = hooks.close() if hooks is not None else False
        report["remaining_hooks"] = len(hooks._api.handles) if hooks is not None else None
        report["status"] = hooks.status if hooks is not None else None
        NetworkGuard.uninstall()
        report["probe_complete"] = (report.get("history_rows") == report.get("insertions") == 1
            and report.get("exact_fixture_result") and report.get("native_release_budget") and not errors
            and report.get("native_recoveries") == 0 and report.get("hook_failure_reason") is None
            and report["closed"] and report["remaining_hooks"] == 0 and not report.get("error_type"))
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
