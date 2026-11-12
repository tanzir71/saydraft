"""Verified, owned, offline native device inventory; IDs never come from Windows order."""

import os
import math
import re
import threading
import time
from pathlib import Path

from saydraft.cleanup.llm.windows_process import WindowsJobProcess
from .downloader import installation_ready
from .manifest import get_model
from .runtime_ids import runtime_model_id

_ROW = re.compile(r"\s*(Vulkan\d+): (.+) \((\d+) MiB, (\d+) MiB free\)\s*")


def parse_devices(output):
    if len(output) > 65536:
        raise ValueError("Native inventory exceeds byte bound")
    text = output.replace(b"\r\n", b"\n").decode("utf-8")
    if text.count("Available devices:\n") != 1:
        raise ValueError("Native inventory header missing or repeated")
    rows, seen = [], set()
    for line in text.split("Available devices:\n", 1)[1].splitlines():
        match = _ROW.fullmatch(line)
        if match:
            identifier, name, total, free = match.groups()
            total, free = int(total), int(free)
            if identifier in seen or int(identifier[6:]) >= 64 or not 0 < total <= 1024**3 or not 0 <= free <= total:
                raise ValueError("Invalid native device metadata")
            seen.add(identifier)
            rows.append({"id": identifier, "name": name, "total_mb": total, "free_mb": free})
        elif line.strip().startswith("Vulkan"):
            raise ValueError("Unsupported native Vulkan device row")
    if len(rows) > 64:
        raise ValueError("Native device inventory exceeds bound")
    return rows


def probe_devices(directory, *, process_factory=WindowsJobProcess, verify=installation_ready,
                  cancel=None, timeout=5, clock=time.monotonic):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("Native inventory timeout must be finite and bounded")
    directory = Path(directory).resolve()
    if not verify(get_model(runtime_model_id("vulkan")), directory, check_hashes=True):
        raise ValueError("Native Vulkan runtime verification failed")
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise RuntimeError("Native inventory cancelled")
    deadline = clock() + timeout
    env = {key: value for key, value in os.environ.items() if key.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")}
    env.update(HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    with process_factory([str(directory / "llama-server.exe"), "--offline", "--list-devices"],
                         env=env, capture_output=True, max_output_bytes=65536) as process:
        while (code := process.poll()) is None:
            if cancel.is_set():
                raise RuntimeError("Native inventory cancelled")
            remaining = deadline - clock()
            if remaining <= 0:
                raise TimeoutError("Native inventory deadline expired")
            cancel.wait(min(.01, remaining))
        if code != 0:
            raise OSError("Native inventory failed")
        if cancel.is_set():
            raise RuntimeError("Native inventory cancelled")
        output = process.read_output(timeout=max(0, deadline - clock()))
    return parse_devices(output)


def choose_device(native, windows, *, required_bytes=0):
    """Prefer matched discrete devices, then virtual/integrated, with enough free memory."""
    if type(required_bytes) is not int or required_bytes < 0:
        raise ValueError("Required device memory must be nonnegative")
    candidates = []
    for device in native:
        kinds = {row["device_type"] for row in windows
                 if row["name"].strip().casefold() == device["name"].strip().casefold()}
        if len(kinds) != 1:
            continue  # No ordinal guesses or ambiguous name-to-type matches.
        kind = next(iter(kinds))
        rank = {2: 3, 3: 2, 1: 1}.get(kind)
        if rank is not None and device["free_mb"] * 1024**2 >= required_bytes:
            candidates.append((rank, device["free_mb"], device["total_mb"], device["id"], device))
    return max(candidates, key=lambda row: row[:4])[-1] if candidates else None
