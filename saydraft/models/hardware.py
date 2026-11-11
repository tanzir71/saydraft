"""Local capability snapshots and measured tier decisions, independent of Qt."""

from __future__ import annotations

import json
import math
import os
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import windows_hardware


def probe_hardware(*, probes=None):
    probes = probes if probes is not None else {
        "cpu_features": windows_hardware.cpu_features, "ram_bytes": windows_hardware.physical_memory,
        "adapters": windows_hardware.dxgi_adapters, "vulkan": windows_hardware.vulkan_devices,
        "cuda": windows_hardware.cuda_devices}
    report = {"schema_version": 1, "measured_at": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "processor": platform.processor(),
              "logical_cores": os.cpu_count(), "errors": {}}
    for name, probe in probes.items():
        try:
            report[name] = probe()
        except (OSError, ValueError, AttributeError) as error:
            report[name] = None  # Missing drivers/API data do not imply measured performance.
            report["errors"][name] = type(error).__name__
    return report


def assess_tier(hardware, *, asr_seconds=None, llm_08_tps=None, llm_2_tps=None):
    for value in (asr_seconds, llm_08_tps, llm_2_tps):
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("Benchmark measurements must be finite and nonnegative")
    ram = hardware.get("ram_bytes")
    if ram is not None and ram < 8 * 1024**3:
        return {"tier": "lite", "reason": "ram_below_8_gib"}
    if asr_seconds is not None and asr_seconds > 1.2:
        return {"tier": "lite", "reason": "asr_over_budget"}
    if ram is None or asr_seconds is None:
        return {"tier": "pending", "reason": "benchmark_incomplete"}
    if hardware.get("vulkan") or hardware.get("cuda"):
        return {"tier": "pro", "reason": "gpu_available"}
    if llm_2_tps is not None and llm_2_tps >= 40:
        return {"tier": "pro", "reason": "llm_2b_measured"}
    if llm_08_tps is not None and llm_08_tps >= 25:
        return {"tier": "standard", "reason": "llm_08b_measured"}
    if llm_08_tps is None:
        return {"tier": "pending", "reason": "cleanup_benchmark_missing"}
    return {"tier": "lite", "reason": "cleanup_below_budget"}


def reports_directory():
    from saydraft.compat.migrate import profile_root

    return profile_root() / "Saydraft" / "hardware-benchmarks"


def save_report(report, directory=None):
    """Append a complete JSON snapshot atomically; previous reports remain intact."""
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    directory = Path(directory) if directory is not None else reports_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid.uuid4().hex}.json"
    temporary = target.with_suffix(".json.part")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)
    return target


def latest_report(directory=None):
    directory = Path(directory) if directory is not None else reports_directory()
    candidates = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
    for path in candidates:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(report, dict) and report.get("schema_version") == 1:
                return report
        except (OSError, ValueError):
            continue  # Keep corrupt/incomplete files for diagnosis, then try an older snapshot.
    return None
