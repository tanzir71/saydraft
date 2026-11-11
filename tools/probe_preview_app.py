"""Verify native preview through the real worker, queued Qt signals and local History.

Feeds the bundled fixture in real time; never opens a microphone or OS insertion
port. Explicit installed paths only, with networking blocked. Keeps QA artifacts.
"""

import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace

import soundfile as sf
from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.app import SaydraftApp, WorkerController, create_worker_signals
from saydraft.asr.language_id import AudioLanguageIdentifier
from saydraft.asr.model_ids import PREVIEW_MODEL
from saydraft.asr.router import AsrRouter
from saydraft.asr.sherpa_parakeet import ParakeetEngine
from saydraft.asr.sherpa_stream import NemotronPreviewModel
from saydraft.config import default_config
from saydraft.core.container import Services
from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.core.worker import SessionWorker
from saydraft.history import DictationHistoryStore
from saydraft.insert.inserter import InsertionResult
from saydraft.models.benchmark import fixture_path
from saydraft.privacy.netguard import NetworkGuard
from saydraft.ui.pill import SaydraftPill


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preview-dir", "parakeet-dir", "lid-dir", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--streaming-result", action="store_true")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("choose a fresh QA output directory")
    args.output.mkdir(parents=True)
    qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if Path("C:/Windows/Fonts/segoeui.ttf").exists():
        for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{font}")
        qt_app.setFont(QtGui.QFont("Segoe UI", 10))
    audio, rate = sf.read(fixture_path(), dtype="float32")
    assert rate == 16000
    capture = SimpleNamespace(sample_rate=rate, chunk_callback=None, start=lambda: None, stop=lambda: audio.copy())
    config = default_config()
    config["labs"].update(live_preview=True, use_streaming_result=args.streaming_result)
    primary = ParakeetEngine(model_dir=args.parakeet_dir)
    router = AsrRouter(config, engine_factory=lambda config, route: primary, installed=lambda model: False,
        language_identifier=AudioLanguageIdentifier(model_dir=args.lid_dir))
    history = DictationHistoryStore(args.output / "history.db")
    inserted, notifications, callbacks, changes = [], [], [], []
    released = False

    def insert(text, **kwargs):
        assert released and history.list_recent(), "Insertion must follow release and History persistence"
        inserted.append(text)
        return InsertionResult("inserted", "fixture")

    cleaner = SimpleNamespace(process_transcript=lambda text, context: text)
    inserter = SimpleNamespace(insert_text=insert)
    formatter = IdentityFormatter()
    processor = TranscriptProcessor(cleaner=cleaner, formatter=formatter, history=history, inserter=inserter)
    services = Services(config, capture, router, cleaner, formatter, inserter,
        SimpleNamespace(capture=lambda: TargetContext("fixture-only", "Fixture QA")), history, processor, [],
        preview=NemotronPreviewModel(model_dir=args.preview_dir))
    signals = create_worker_signals(QtCore)
    worker = SessionWorker(services, emit=lambda name, *values: getattr(signals, name).emit(*values))
    app = SaydraftApp(qt_modules=SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets))
    app.controller = WorkerController(signals)
    app.controller.core = worker
    app.tray = SimpleNamespace(show_notification=notifications.append)
    app.pill = SaydraftPill(focus_point_provider=lambda: None)
    signals.recording_started.connect(app.pill.show_recording)
    signals.processing_started.connect(app.pill.show_processing)
    signals.preview_text_changed.connect(app._show_preview)
    signals.preview_unavailable.connect(app._preview_unavailable)
    signals.notification_requested.connect(notifications.append)
    previous = ""
    started = 0.0

    def update(generation, text):
        nonlocal previous
        if worker.is_current_preview(generation):
            callbacks.append(time.perf_counter() - started)
            if text != previous:
                changes.append(text)
                previous = text

    signals.preview_text_changed.connect(update)

    def pump_until(predicate, timeout=30):
        deadline = time.perf_counter() + timeout
        while not predicate():
            qt_app.processEvents()
            if time.perf_counter() > deadline:
                raise TimeoutError("Fixture app verification did not finish")
            time.sleep(0.005)

    NetworkGuard.install()
    try:
        worker.start_recording()
        pump_until(lambda: app.pill.isVisible() or not worker.busy)
        assert app.pill.isVisible(), "Recording did not arm"
        started = time.perf_counter()
        for offset in range(0, len(audio), 1600):
            capture.chunk_callback(audio[offset:offset + 1600])
            deadline = started + (offset + 1600) / rate
            pump_until(lambda: time.perf_counter() >= deadline)
            assert not inserted and not history.list_recent(), "Partials cannot reach History/insertion before release"
        app.pill.grab().save(str(args.output / "bar.png"))
        strip_visible = app.pill.preview_label.isVisible()
        released = True
        release_started = time.perf_counter()
        worker.stop_recording()
        pump_until(lambda: not worker.busy)
        rows = history.list_recent()
        row = rows[0]
        counts = [sum(second <= value < second + 1 for value in callbacks) for second in range(8)]
        report = {"offline": True, "fixture_seconds": 8, "microphone_used": False, "os_insertion_used": False,
            "streaming_requested": args.streaming_result, "preview_callbacks": len(callbacks),
            "minimum_steady_callbacks_per_second": min(counts[1:-1]), "callbacks_per_second": counts,
            "actual_text_changes": len(changes), "bar_strip_visible": strip_visible, "history_rows": len(rows),
            "selected_model": row.model, "raw_nonempty": bool(row.raw_text),
            "alternative_preserved": any(edit["type"] == "asr_alternative" for edit in json.loads(row.edits_json)),
            "release_to_history_and_stub_insertion_seconds": time.perf_counter() - release_started,
            "stub_insertions": len(inserted), "notification_count": len(notifications),
            "preview_thread_joined": worker._preview is None}
        report["passed"] = (min(counts[1:-1]) >= 4 and strip_visible and len(inserted) == 1 and len(rows) == 1
            and bool(row.raw_text) and ((row.model == PREVIEW_MODEL) == args.streaming_result)
            and (not args.streaming_result or report["alternative_preserved"]))
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    finally:
        worker.shutdown()
        worker.executor.shutdown(wait=True)
        app.pill.hide()
        NetworkGuard.uninstall()


if __name__ == "__main__":
    raise SystemExit(main())
