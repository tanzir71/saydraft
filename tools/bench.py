"""Measure local dictation stages without inserting into the foreground app.

Run ``python -m tools.bench --audio tests/fixtures/hello.wav --iterations 20``.
Models are cache-only, reports contain no transcript text, and history is temporary.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import platform
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from voicetray.dictation import DictationConfig, DictationContext, DictationPipeline
from voicetray.history import DictationHistoryStore, HistoryEntry
from voicetray.insert.inserter import Inserter
from tools.soak import MemoryClipboard, MemoryKeyboard


def percentile(values: list[float], fraction: float) -> float:
    """Use nearest-rank percentiles, including the tail for small samples."""
    if not values or not 0 <= fraction <= 1:
        raise ValueError("expected samples and a percentile between 0 and 1")
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def current_rss_bytes() -> int | None:
    if os.name != "nt":
        return None  # ru_maxrss is peak RSS, not current RSS.
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in ("peak", "working", "ppq", "pq", "pnpq", "npq", "page", "peak_page")
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.working)


def summarize(samples: list[dict]) -> list[dict]:
    rows = []
    for phase in ("cold", "warm"):
        matching = [sample for sample in samples if sample["phase"] == phase]
        if not matching:
            continue
        for stage in ("vad", "stt", "rules", "llm", "cleanup", "history", "insert", "total"):
            values = [sample[stage] * 1000 for sample in matching if sample.get(stage) is not None]
            rows.append({
                "phase": phase, "stage": stage, "samples": len(values),
                "p50_ms": round(statistics.median(values), 3) if values else None,
                "p95_ms": round(percentile(values, 0.95), 3) if values else None,
            })
    return rows


def run_benchmark(*, audio_path: Path | None = None, model: str = "base", iterations: int = 20) -> dict:
    if iterations < 2:
        raise ValueError("iterations must be at least 2 (one cold, then warm)")
    from voicetray.privacy.netguard import NetworkGuard

    NetworkGuard.install()
    engine = None
    audio = None
    duration = None
    if audio_path is not None:
        import soundfile as sf
        from voicetray.stt.whisper_engine import WhisperEngine, WhisperEngineConfig

        audio, rate = sf.read(audio_path, dtype="float32")
        if rate != 16_000:
            raise ValueError("benchmark fixtures must be 16 kHz")
        duration = len(audio) / rate
        engine = WhisperEngine(WhisperEngineConfig(model_size=model, local_files_only=True))

    pipeline = DictationPipeline(DictationConfig())
    clipboard = MemoryClipboard()
    clipboard.copy("clipboard sentinel")
    inserter = Inserter(clipboard=clipboard, keyboard=MemoryKeyboard(), restore_delay=0.15)
    idle_rss = current_rss_bytes()
    samples = []
    with tempfile.TemporaryDirectory(prefix="saydraft-bench-") as temp:
        store = DictationHistoryStore(Path(temp) / "history.db")
        for index in range(iterations):
            started = time.perf_counter()
            sample = {"phase": "cold" if index == 0 else "warm", "vad": None, "stt": None}
            raw = "um hello hello world"
            if engine is not None:
                raw = engine.transcribe(audio)
                if not raw.strip():
                    raise RuntimeError("ASR returned no words; cannot count a successful dictation")
                sample.update(engine.last_timings)
            cleanup_started = time.perf_counter()
            cleaned = pipeline.process_transcript(raw, DictationContext())
            sample["cleanup"] = time.perf_counter() - cleanup_started
            sample.update(pipeline.last_timings)
            sample["llm"] = None  # This benchmark runs rules-only.
            history_started = time.perf_counter()
            store.append(HistoryEntry("Benchmark", raw, cleaned, "balanced", "general", duration, model))
            sample["history"] = time.perf_counter() - history_started
            insert_started = time.perf_counter()
            result = inserter.insert_text(cleaned)
            sample["insert"] = time.perf_counter() - insert_started
            if result.status != "inserted" or clipboard.paste() != "clipboard sentinel":
                raise RuntimeError("insertion or clipboard restoration failed")
            sample["total"] = time.perf_counter() - started
            samples.append(sample)
    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "processor": platform.processor(), "logical_cpus": os.cpu_count(),
        "mode": "cached ASR + rules" if engine else "synthetic text + rules (ASR not measured)",
        "model": model if engine else None, "audio_file": audio_path.name if audio_path else None,
        "audio_seconds": duration, "iterations": iterations,
        "idle_rss_bytes": idle_rss, "warm_rss_bytes": current_rss_bytes(),
        "insertion": "memory clipboard/keyboard with real restore delays; no foreground paste",
        "rows": summarize(samples),
    }


def to_markdown(report: dict) -> str:
    lines = ["# Dictation baseline", "", f"Measured: {report['measured_at']}", ""]
    for name in ("platform", "python", "processor", "logical_cpus", "mode", "model", "audio_file",
                 "audio_seconds", "iterations", "idle_rss_bytes", "warm_rss_bytes", "insertion"):
        lines.append(f"- {name}: {report[name]}")
    lines.extend(["", "| Phase | Stage | Samples | p50 (ms) | p95 (ms) |",
                  "|---|---|---:|---:|---:|"])
    for row in report["rows"]:
        p50 = row["p50_ms"] if row["p50_ms"] is not None else "not measured"
        p95 = row["p95_ms"] if row["p95_ms"] is not None else "not measured"
        lines.append(f"| {row['phase']} | {row['stage']} | {row['samples']} | {p50} | {p95} |")
    lines.extend(["", "Cold means first transcription in this process; disk caches may already be warm.",
                  "The first ASR sample includes model load. Warm samples reuse the same engine.",
                  "Total is release-to-simulated-insertion, including history and restore delays.",
                  "RAM is this benchmark process, excluding the Qt shell and any sidecars.",
                  "This fixture is a smoke measurement, not an owner-clip accuracy or hardware-tier result.",
                  "No models are downloaded, no foreground windows or user history are modified,",
                  "and reports contain no transcript text.", "",
                  "Reproduce: `python -m tools.bench --audio tests/fixtures/hello.wav --iterations 20`.",
                  "Run separate processes with 3/10/30/90-second owner fixtures for full latency evidence.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, help="16 kHz WAV; omit for synthetic text only")
    parser.add_argument("--model", default="base", help="cached Whisper model ID or local path")
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--output", type=Path, help="new Markdown report path (existing files are preserved)")
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error("output already exists; choose a new report filename")
    report = run_benchmark(audio_path=args.audio, model=args.model, iterations=args.iterations)
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(to_markdown(report))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
