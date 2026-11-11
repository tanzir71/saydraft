"""Benchmark only installed models using the bundled eight-second speech fixture."""

from __future__ import annotations

import hashlib
import statistics
import time
from pathlib import Path
from types import SimpleNamespace

from .hardware import assess_tier, probe_hardware, save_report


def fixture_path():
    return Path(__file__).resolve().parents[2] / "assets" / "audio" / "benchmark.wav"


def run_benchmark(asr, *, directory=None, hardware_probe=probe_hardware,
                  cleanup_benchmark=None, clock=time.perf_counter):
    import numpy as np
    import soundfile as sf

    path = fixture_path()
    audio, rate = sf.read(path, dtype="float32")
    if rate != 16000 or audio.shape != (128000,) or not np.isfinite(audio).all() or not np.any(audio):
        raise ValueError("The benchmark fixture must contain eight seconds of mono 16 kHz speech")
    report = hardware_probe()
    measurement = {"fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "fixture_seconds": 8, "fixture_kind": "repeated_bundled_hello",
                   "asr_seconds": None, "asr_status": "pending", "cleanup_status": "not_available",
                   "cleanup": [], "llm_08_tps": None, "llm_2_tps": None}
    report["measurements"] = measurement
    try:
        context = getattr(asr, "set_context", None)
        if context is not None:
            context(SimpleNamespace(app_group="general"))
        started = clock()
        prepare = getattr(asr, "prepare", None)
        if prepare is not None:
            prepare()
        measurement["prepare_seconds"] = clock() - started
        if not asr.transcribe(audio).strip():
            raise ValueError("Speech benchmark returned empty output")
        costs = []
        for _ in range(3):
            started = clock()
            if not asr.transcribe(audio).strip():
                raise ValueError("Speech benchmark returned empty output")
            costs.append(clock() - started)
        measurement.update(asr_seconds=statistics.median(costs), asr_runs=costs, asr_status="ok")
    except FileNotFoundError:
        measurement["asr_status"] = "model_missing"
    except Exception:
        measurement["asr_status"] = "failed"
    measurement["asr_model"] = getattr(asr, "model_id", "unknown")
    if cleanup_benchmark is not None:
        try:
            rows = cleanup_benchmark()
            # Only comparable 60-token measurements can inform the tier matrix.
            for row in rows:
                size = row["parameters_b"]
                seconds = row["seconds"]
                if (size not in (0.8, 2) or row["tokens"] != 60 or
                        not np.isfinite(seconds) or seconds <= 0):
                    raise ValueError("Invalid cleanup benchmark sample")
            measurement["cleanup"] = rows
            for row in rows:
                key = "llm_08_tps" if row["parameters_b"] == 0.8 else "llm_2_tps"
                measurement[key] = 60 / row["seconds"]
            measurement["cleanup_status"] = "ok" if rows else "not_available"
        except Exception:
            measurement["cleanup_status"] = "failed"
    report["assessment"] = assess_tier(report, **{key: measurement[key] for key in (
        "asr_seconds", "llm_08_tps", "llm_2_tps")})
    save_report(report, directory)
    return report  # No transcript, microphone access, history or insertion.
