"""Benchmark only installed models using the bundled eight-second speech fixture."""

from __future__ import annotations

import hashlib
import math
import statistics
import time
from concurrent.futures import CancelledError
from pathlib import Path
from types import SimpleNamespace

from .hardware import assess_tier, probe_hardware, save_report


def fixture_path():
    return Path(__file__).resolve().parents[2] / "assets" / "audio" / "benchmark.wav"


def _cleanup_metrics(rows):
    # Accept complete triples atomically. Copy only numeric timing metadata.
    if not isinstance(rows, list) or len(rows) not in (0, 3, 6):
        raise ValueError("Cleanup measurements require three samples per model")
    clean, groups = [], {}
    for row in rows:
        size, seconds, tokens = row["parameters_b"], row["seconds"], row["tokens"]
        if (type(size) not in (int, float) or not math.isfinite(size) or not 0 < size <= 1000
                or type(tokens) is not int or tokens != 60 or type(seconds) not in (int, float)
                or not math.isfinite(seconds) or seconds <= 0 or not math.isfinite(60 / seconds)):
            raise ValueError("Invalid cleanup benchmark sample")
        clean.append({"parameters_b": float(size), "tokens": 60, "seconds": float(seconds)})
        groups.setdefault(size, []).append(60 / seconds)
    if any(len(rates) != 3 for rates in groups.values()):
        raise ValueError("Cleanup measurements require three samples per model")
    metrics = {"cleanup": clean, "cleanup_status": "ok" if clean else "not_available",
               "llm_08_tps": None, "llm_2_tps": None}
    for size, rates in groups.items():
        # Nominal matrix classes allow ±10% actual parameters; no filename inference.
        key = "llm_08_tps" if 0.72 <= size <= 0.88 else "llm_2_tps" if 1.8 <= size <= 2.2 else None
        if key is not None:
            if metrics[key] is not None:
                raise ValueError("Duplicate cleanup model class")
            metrics[key] = statistics.median(rates)
    return metrics


def run_benchmark(asr, *, directory=None, hardware_probe=probe_hardware,
                  cleanup_benchmark=None, clock=time.perf_counter, cancelled=lambda: False,
                  progress=lambda phase: None, persist=True):
    import numpy as np
    import soundfile as sf

    def checkpoint(phase=None):
        if cancelled():
            raise CancelledError()
        if phase is not None:
            progress(phase)
            if cancelled():
                raise CancelledError()

    checkpoint('hardware')
    path = fixture_path()
    audio, rate = sf.read(path, dtype="float32")
    if rate != 16000 or audio.shape != (128000,) or not np.isfinite(audio).all() or not np.any(audio):
        raise ValueError("The benchmark fixture must contain eight seconds of mono 16 kHz speech")
    report = hardware_probe()
    checkpoint()
    measurement = {"fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "fixture_seconds": 8, "fixture_kind": "repeated_bundled_hello",
                   "asr_seconds": None, "asr_status": "pending", "cleanup_status": "not_available",
                   "cleanup": [], "llm_08_tps": None, "llm_2_tps": None}
    report["measurements"] = measurement
    try:
        checkpoint('preparing')
        context = getattr(asr, "set_context", None)
        if context is not None:
            context(SimpleNamespace(app_group="general"))
        started = clock()
        prepare = getattr(asr, "prepare", None)
        if prepare is not None:
            prepare()
        measurement["prepare_seconds"] = clock() - started
        checkpoint('warmup')
        if not asr.transcribe(audio).strip():
            raise ValueError("Speech benchmark returned empty output")
        checkpoint()
        costs = []
        for sample in range(3):
            checkpoint(f'speech_{sample + 1}')
            started = clock()
            if not asr.transcribe(audio).strip():
                raise ValueError("Speech benchmark returned empty output")
            elapsed = clock() - started
            checkpoint()
            if not math.isfinite(elapsed) or elapsed <= 0:
                raise ValueError('Speech timings must be finite and positive')
            costs.append(elapsed)
        measurement.update(asr_seconds=statistics.median(costs), asr_runs=costs, asr_status="ok")
    except CancelledError:
        raise
    except FileNotFoundError:
        measurement["asr_status"] = "model_missing"
    except Exception:
        measurement["asr_status"] = "failed"
    measurement["asr_model"] = getattr(asr, "model_id", "unknown")
    checkpoint()
    if cleanup_benchmark is not None:
        try:
            checkpoint('cleanup')
            measurement.update(_cleanup_metrics(cleanup_benchmark()))
            checkpoint()
        except CancelledError:
            raise
        except Exception:
            measurement["cleanup_status"] = "failed"
    report["assessment"] = assess_tier(report, **{key: measurement[key] for key in (
        "asr_seconds", "llm_08_tps", "llm_2_tps")})
    checkpoint('saving')
    if persist:
        save_report(report, directory)
    return report  # No transcript, microphone access, history or insertion.
