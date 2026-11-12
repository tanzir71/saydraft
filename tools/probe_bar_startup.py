"""Measure synthetic dispatch → first offscreen Bar paint with target capture blocked.

This is not a physical keyboard or active-desktop test. No microphone is opened.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def measure(output: Path, iterations: int):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_STYLE_OVERRIDE"] = "Fusion"
    os.environ["QT_SCALE_FACTOR"] = "1"
    from PySide6 import QtCore, QtGui, QtWidgets
    from saydraft.app import SaydraftApp, WorkerController, create_worker_signals
    from saydraft.config import default_config
    from saydraft.core.container import Services
    from saydraft.core.interfaces import TargetContext
    from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
    from saydraft.core.worker import SessionWorker
    from saydraft.privacy.netguard import NetworkGuard
    from saydraft.ui.fonts import install_bundled_fonts
    from saydraft.ui.pill import PillState, SaydraftPill
    from saydraft.ui.theme import install_theme

    NetworkGuard.install()
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Startup fixture attempted desktop, clipboard or microphone access")

    class NoDesktop:
        def __getattr__(self, name):
            return forbidden(name)

    ctypes.windll = SimpleNamespace(user32=NoDesktop())
    QtWidgets.QApplication.clipboard = staticmethod(forbidden)
    application = QtWidgets.QApplication([])
    assert application.platformName() == "offscreen"
    assert len(install_bundled_fonts(application)) == 8
    theme = install_theme(application, mode="light")
    assert theme is not None

    class MeasuredBar(SaydraftPill):
        first_paint = None

        def paintEvent(self, event):
            super().paintEvent(event)
            if self.state == PillState.PREPARING and self.first_paint is None:
                self.first_paint = time.perf_counter_ns()

    entered, release = threading.Event(), threading.Event()

    def capture():
        entered.set()
        if not release.wait(3):
            raise TimeoutError("Fixture target capture was not released")
        return TargetContext("owned-fixture", "Public fixture")

    config = default_config()
    cleaner = SimpleNamespace(process_transcript=lambda text, context: text)
    history = SimpleNamespace(append=forbidden)
    recorder = SimpleNamespace(start=forbidden, stop=forbidden)
    asr = SimpleNamespace(prepare=forbidden, transcribe=forbidden)
    inserter = SimpleNamespace(insert_text=forbidden)
    processor = TranscriptProcessor(cleaner=cleaner, formatter=IdentityFormatter(), history=history, inserter=inserter)
    services = Services(config, recorder, asr, cleaner, IdentityFormatter(), inserter,
        SimpleNamespace(capture=capture), history, processor, [])
    signals = create_worker_signals(QtCore)
    controller = WorkerController(signals)
    worker = SessionWorker(services, bar_emit=signals.bar_updated.emit)
    controller.core = worker
    shell = SaydraftApp()
    shell.controller = controller
    shell.pill = bar = MeasuredBar(screen_geometry_provider=lambda: QtCore.QRect(0, 0, 1000, 800))
    signals.bar_updated.connect(shell._apply_bar_update, QtCore.Qt.QueuedConnection)
    samples = []
    try:
        for _ in range(iterations):
            entered.clear()
            release.clear()
            bar.first_paint = None
            started = time.perf_counter_ns()
            thread = threading.Thread(target=worker.start_recording)
            thread.start()
            try:
                deadline = time.monotonic() + 2
                while bar.first_paint is None and time.monotonic() < deadline:
                    application.processEvents()
                    threading.Event().wait(.001)
                assert bar.first_paint is not None and entered.is_set()
                assert bar.state == PillState.PREPARING and worker._capturing_context
                samples.append((bar.first_paint - started) / 1_000_000)
                worker.cancel()
            finally:
                release.set()
                thread.join(3)
            assert not thread.is_alive() and not attempts
            application.processEvents()
            assert bar.state == PillState.IDLE
        ordered = sorted(samples)
        report = {"source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
            "platform": application.platformName(), "qt": QtCore.qVersion(),
            "font": QtGui.QFontInfo(bar.caption_font).family(), "stimulus": "synthetic thread dispatch",
            "target_capture": "blocked public fixture", "measurement": "dispatch to first completed offscreen paint",
            "iterations": iterations, "samples_ms": samples, "median_ms": statistics.median(samples),
            "p95_ms": ordered[max(0, (95 * iterations + 99) // 100 - 1)], "maximum_ms": max(samples),
            "budget_ms": 50, "network_guard_enabled": bool(NetworkGuard._originals),
            "active_application_read": False, "owner_clipboard_accessed": False,
            "microphone_opened": False, "input_sent": False}
        report["synthetic_budget_passed"] = report["maximum_ms"] <= 50
        output.mkdir(parents=True, exist_ok=False)
        (output / "startup.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        assert report["synthetic_budget_passed"], report
        return report
    finally:
        signals.blockSignals(True)
        worker.shutdown()
        bar.hide()
        theme.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory for the measurement report")
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    if not 10 <= args.iterations <= 100:
        parser.error("--iterations must be between 10 and 100")
    report = measure(args.output, args.iterations)
    print(json.dumps({name: report[name] for name in ("iterations", "median_ms", "p95_ms", "maximum_ms", "synthetic_budget_passed")}))


if __name__ == "__main__":
    main()
