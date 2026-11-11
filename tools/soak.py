"""Synthetic Saydraft soak test harness."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


CycleRunner = Callable[[int], None]
RssReader = Callable[[], int]
Clock = Callable[[], float]


@dataclass(frozen=True)
class SoakResult:
    cycles: int
    failures: int
    ui_freezes: int
    start_rss_bytes: int
    end_rss_bytes: int
    rss_growth_ratio: float
    max_rss_growth_ratio: float

    @property
    def ok(self) -> bool:
        return (
            self.failures == 0
            and self.ui_freezes == 0
            and self.rss_growth_ratio <= self.max_rss_growth_ratio
        )

    def to_text(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        growth_percent = self.rss_growth_ratio * 100.0
        limit_percent = self.max_rss_growth_ratio * 100.0
        return (
            f"{status}: cycles={self.cycles} failures={self.failures} "
            f"ui_freezes={self.ui_freezes} rss_growth={growth_percent:.1f}% "
            f"limit={limit_percent:.1f}%"
        )


class MemoryClipboard:
    def __init__(self):
        self.value = ""

    def paste(self) -> str:
        return self.value

    def copy(self, text: str) -> None:
        self.value = str(text)


class MemoryKeyboard:
    def __init__(self):
        self.sent = []
        self.written = []

    def send(self, hotkey: str) -> None:
        self.sent.append(str(hotkey))

    def write(self, text: str) -> None:
        self.written.append(str(text))


class SyntheticCycleRunner:
    """Exercise the actual session, persistence and insertion services with fake devices."""

    def __init__(self):
        import tempfile
        from types import SimpleNamespace
        from saydraft.config import default_config
        from saydraft.core.container import Services
        from saydraft.core.interfaces import TargetContext
        from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
        from saydraft.core.session import DictationSession
        from saydraft.core.worker import SessionWorker
        from saydraft.dictation import DictationConfig, DictationPipeline
        from saydraft.history import DictationHistoryStore
        from saydraft.insert.inserter import Inserter

        class InlineExecutor:
            def submit(self, callback, *args):
                callback(*args)
            def shutdown(self, **kwargs):
                pass

        class Timer:
            def __init__(self, *args):
                pass
            def start(self):
                pass
            def cancel(self):
                pass

        self._temp = tempfile.TemporaryDirectory(prefix="saydraft-soak-")
        self._clock = 0.0
        self._raw = ""
        self.pipeline = DictationPipeline(DictationConfig())
        self.clipboard = MemoryClipboard()
        self.clipboard.copy("clipboard sentinel")
        self.keyboard = MemoryKeyboard()
        self.inserter = Inserter(clipboard=self.clipboard, keyboard=self.keyboard,
                                  focus_provider=lambda: "notepad", sleep=lambda seconds: None)
        self.history = DictationHistoryStore(Path(self._temp.name) / "history.db")
        formatter = IdentityFormatter()
        processor = TranscriptProcessor(cleaner=self.pipeline, formatter=formatter,
                                         history=self.history, inserter=self.inserter)
        services = Services(
            default_config(), SimpleNamespace(start=lambda: None, stop=lambda: [0.1]),
            SimpleNamespace(transcribe=lambda audio: self._raw), self.pipeline, formatter,
            self.inserter, SimpleNamespace(capture=lambda: TargetContext("notepad", "Notepad")),
            self.history, processor, [],
        )
        self.worker = SessionWorker(services, executor=InlineExecutor(), timer_factory=Timer,
                                     session=DictationSession(clock=lambda: self._clock))

    def __call__(self, index: int) -> None:
        self._raw = f"um soak cycle {index} item one item two"
        if not self.worker.start_recording():
            raise RuntimeError("session remained busy")
        self._clock += 1.0
        self.worker.stop_recording()
        result = self.worker.last_result
        if result is None or result.insertion.status != "inserted":
            raise RuntimeError("session failed to persist and insert")
        if self.clipboard.paste() != "clipboard sentinel":
            raise RuntimeError("clipboard was not restored")

    def close(self):
        self.worker.shutdown()
        self._temp.cleanup()

    def __del__(self):
        if hasattr(self, "_temp"):
            self._temp.cleanup()


class NotepadCycleRunner:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.synthetic = SyntheticCycleRunner()

    def __enter__(self):
        if sys.platform != "win32":
            raise RuntimeError("Notepad target is only available on Windows")
        self.process = subprocess.Popen(["notepad.exe"])
        time.sleep(1.0)
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        self.process = None

    def __call__(self, index: int) -> None:
        # The synthetic pipeline/insert cycle is still used so the soak remains deterministic.
        # Keeping Notepad open exercises the target-app lifetime during manual Windows runs.
        self.synthetic(index)


def run_soak(
    *,
    cycles: int = 50,
    rss_reader: RssReader | None = None,
    cycle_runner: CycleRunner | None = None,
    max_rss_growth_ratio: float = 0.10,
    freeze_timeout_seconds: float = 2.0,
    clock: Clock = time.monotonic,
) -> SoakResult:
    if cycles <= 0:
        raise ValueError("cycles must be positive")
    if max_rss_growth_ratio < 0:
        raise ValueError("max_rss_growth_ratio must be non-negative")
    if freeze_timeout_seconds <= 0:
        raise ValueError("freeze_timeout_seconds must be positive")

    rss = rss_reader or current_rss_bytes
    runner = cycle_runner or SyntheticCycleRunner()
    start_rss = int(rss())
    failures = 0
    ui_freezes = 0

    for index in range(1, int(cycles) + 1):
        started = clock()
        try:
            runner(index)
        except Exception:
            failures += 1
        elapsed = max(0.0, clock() - started)
        if elapsed > freeze_timeout_seconds:
            ui_freezes += 1

    end_rss = int(rss())
    growth_ratio = 0.0 if start_rss <= 0 else max(0.0, (end_rss - start_rss) / start_rss)
    return SoakResult(
        cycles=int(cycles),
        failures=failures,
        ui_freezes=ui_freezes,
        start_rss_bytes=start_rss,
        end_rss_bytes=end_rss,
        rss_growth_ratio=round(growth_ratio, 6),
        max_rss_growth_ratio=float(max_rss_growth_ratio),
    )


def current_rss_bytes() -> int:
    if os.name == "nt":
        return _windows_rss_bytes()
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        multiplier = 1024 if sys.platform != "darwin" else 1
        return int(usage.ru_maxrss * multiplier)
    except Exception:
        return 0


def _windows_rss_bytes() -> int:
    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD,
    ]
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        handle,
        ctypes.byref(counters),
        counters.cb,
    )
    if not ok:
        raise OSError("Could not measure Windows working set")
    return int(counters.WorkingSetSize)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Saydraft soak cycles")
    parser.add_argument("--cycles", type=int, default=50)
    parser.add_argument("--target", choices=("synthetic", "notepad"), default="synthetic")
    parser.add_argument("--max-rss-growth", type=float, default=0.10)
    parser.add_argument("--freeze-timeout", type=float, default=2.0)
    parser.add_argument("--json", action="store_true", help="emit machine-readable result")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.target == "notepad":
        with NotepadCycleRunner() as runner:
            result = run_soak(
                cycles=args.cycles,
                cycle_runner=runner,
                max_rss_growth_ratio=args.max_rss_growth,
                freeze_timeout_seconds=args.freeze_timeout,
            )
    else:
        result = run_soak(
            cycles=args.cycles,
            max_rss_growth_ratio=args.max_rss_growth,
            freeze_timeout_seconds=args.freeze_timeout,
        )

    if args.json:
        print(json.dumps(asdict(result) | {"ok": result.ok}, sort_keys=True))
    else:
        print(result.to_text())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
