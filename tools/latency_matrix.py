"""Serial, process-cold/warm release latency matrix using installed models only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DURATIONS = (3, 10, 30, 90)
PHASES = ("cold", "warm")
RECIPES = {
    "lite": {"candidate": None, "backend": "cpu", "decode_target_tps": None},
    "standard": {"candidate": "qwen35-08b-q4-k-m", "backend": "cpu", "decode_target_tps": 25},
    "pro": {"candidate": "qwen35-2b-q4-k-m", "backend": "vulkan", "decode_target_tps": 40},
}


def write_json(path, value):
    """Atomically publish metadata; journals retain completed individual cases."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_receipt():
    names = sorted([*ROOT.joinpath("saydraft").rglob("*.py"),
        *[ROOT / "tools" / name for name in ("bench.py", "latency_matrix.py", "latency_trial.py",
            "probe_cleanup_latency.py", "soak_runner.py", "bench_cleanup.py")],
        ROOT / "saydraft" / "models" / "manifest.json", ROOT / "eval" / "cleanup" / "candidates.json"])
    return {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "source_fingerprints": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in names}}


def summarize(rows, tier):
    """All eight cells must be sampled independently; missing data never passes."""
    p50_limit, p95_limit = (.6, 1.2) if tier == "lite" else (1.2, 2.0)
    groups = {}
    for phase in PHASES:
        for seconds in DURATIONS:
            matching = [row for row in rows if row["phase"] == phase and row["audio_seconds"] == seconds]
            values = sorted(row["release_to_paste_seconds"] for row in matching)
            if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
                raise ValueError("Latency samples must be finite and nonnegative")
            groups[f"{phase}-{seconds}"] = {"n": len(values),
                "p50_seconds": values[math.ceil(len(values) * .5) - 1] if values else None,
                "p95_seconds": values[math.ceil(len(values) * .95) - 1] if values else None,
                "max_seconds": max(values) if values else None,
                "decisions": dict(Counter(row["decision"] for row in matching))}
    accepted = {phase: sum(row["decision"] == "accepted" for row in rows if row["phase"] == phase)
                for phase in PHASES}
    return {"groups": groups, "p50_target_seconds": p50_limit, "p95_target_seconds": p95_limit,
        "latency_targets_met": all(group["n"] >= 20 and group["p50_seconds"] <= p50_limit
                                   and group["p95_seconds"] <= p95_limit for group in groups.values()),
        "accepted_by_phase": accepted,
        "actual_model_use": tier == "lite" or all(accepted.values())}


def validate_pair(pair, *, seconds, repeat, commit):
    """Refuse a stale, duplicate, incomplete or mismatched child receipt."""
    if (not pair.get("complete") or pair.get("git_commit") != commit
            or pair.get("audio_seconds") != seconds or pair.get("repeat") != repeat
            or len(pair.get("cases", [])) != 2):
        raise ValueError("Child pair did not complete against this source and request")
    for phase, row in zip(PHASES, pair["cases"], strict=True):
        if (row.get("phase") != phase or row.get("audio_seconds") != seconds or row.get("repeat") != repeat
                or not row.get("history_before_paste") or not row.get("clipboard_restored")
                or not row.get("release_deadline_present") or not row.get("no_early_delivery")
                or row.get("fed_samples") != seconds * 16000):
            raise ValueError("Child pair lacks checked worker delivery evidence")
    if any(value is not True for value in pair.get("native_exits", [])):
        raise ValueError("Child native exit was not independently observed")


def child_environment(output):
    # No provider credentials/proxies, inherited hooks, or owner model cache lookup.
    allowed = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "PROCESSOR_ARCHITECTURE",
               "NUMBER_OF_PROCESSORS", "VIRTUAL_ENV")
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    private = output / "profile"
    for name in ("temp", "local", "roaming", "home"):
        (private / name).mkdir(parents=True, exist_ok=False)
    environment.update({"TEMP": str(private / "temp"), "TMP": str(private / "temp"),
        "LOCALAPPDATA": str(private / "local"), "APPDATA": str(private / "roaming"),
        "USERPROFILE": str(private / "home"), "HF_HOME": str(private / "home" / "hf"),
        "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "QT_QPA_PLATFORM": "offscreen",
        "PYTHONNOUSERSITE": "1",
        # This venv may use system/user-installed packages. Preserve its explicit
        # module search paths while redirecting all application/cache state.
        "PYTHONPATH": os.pathsep.join(str(Path(p).resolve()) for p in sys.path if p and Path(p).is_dir())})
    return environment


def run_pair(spec, output, *, process_factory=None):
    from saydraft.cleanup.llm.windows_process import WindowsJobProcess

    write_json(output / "request.json", spec)
    process = (process_factory or WindowsJobProcess)([str(Path(sys.executable).resolve()),
        "-m", "tools.latency_trial", "--request", str(output / "request.json")],
        env=child_environment(output), cwd=ROOT, capture_output=True, max_output_bytes=65536)
    try:
        # An observation timeout never launches a second copy. This is a trial
        # watchdog, far above two real-time captures, startup and shutdown limits.
        deadline = time.monotonic() + 2 * spec["audio_seconds"] + 360
        while process.poll() is None:
            if time.monotonic() >= deadline:
                process.terminate()
                process.wait(timeout=5)
                raise TimeoutError("Latency pair exceeded its bounded trial watchdog")
            time.sleep(.1)
        code = process.poll()
        # Do not publish native stdout, transcripts, keys or diagnostic tracebacks.
        output_bytes = process.read_output(timeout=3)
        error_types = re.findall(rb"(?m)^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):", output_bytes)
        write_json(output / "process.json", {"exit_code": code, "output_bytes": len(output_bytes),
            "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
            "uncaught_error_types": sorted({value.decode("ascii") for value in error_types})})
        pair_path = output / "report.json"
        if not pair_path.is_file():
            raise RuntimeError("Latency child did not publish a report")
        pair = json.loads(pair_path.read_text(encoding="utf-8"))
        if code != 0:
            raise RuntimeError("Latency child failed; retained its report and process receipt")
        return pair
    finally:
        process.close()  # Kill-on-close job also owns every nested native child.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=RECIPES, required=True)
    for name in ("parakeet-dir", "lid-dir", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("models-dir", "runtime-dir"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--vad-dir", type=Path, help="installed pinned Silero bundle; required for full runs")
    parser.add_argument("--device", help="explicit verified Pro adapter, e.g. Vulkan1")
    parser.add_argument("--repeats", type=int, default=20, help="independent fresh-process pairs per duration")
    parser.add_argument("--durations", nargs="+", type=int, default=list(DURATIONS))
    parser.add_argument("--debug", action="store_true", help="allow a partial/dirty diagnostic; cannot qualify")
    parser.add_argument("--isolated", action="store_true", help="declare competing local QA/model workloads stopped")
    args = parser.parse_args(argv)
    if os.name != "nt" or not 1 <= args.repeats <= 100:
        parser.error("Windows and 1–100 repeats are required")
    if (len(set(args.durations)) != len(args.durations) or not args.durations
            or any(seconds not in DURATIONS for seconds in args.durations)):
        parser.error("durations must be distinct members of 3 10 30 90")
    if not args.debug and (not args.isolated or args.repeats < 20 or tuple(args.durations) != DURATIONS or not args.vad_dir):
        parser.error("full runs require --isolated, --vad-dir, all four durations in order and at least 20 repeats")
    recipe = RECIPES[args.tier]
    if (args.tier != "lite" and not all((args.models_dir, args.runtime_dir)) or
            args.tier == "pro" and not re.fullmatch(r"Vulkan\d+", args.device or "") or
            args.tier != "pro" and args.device is not None):
        parser.error("Standard/Pro require installed model/runtime paths; only Pro requires an explicit Vulkan device")
    for path in (args.parakeet_dir, args.lid_dir, args.models_dir, args.runtime_dir, args.vad_dir):
        if path is not None and not path.is_dir():
            parser.error("an installed model/runtime directory is unavailable")
    source = source_receipt()
    if not args.debug and source["source_dirty"]:
        parser.error("full runs require a clean immutable source checkout")
    args.output = args.output.resolve()
    if not args.debug and args.output.is_relative_to(ROOT):
        parser.error("full-run artifacts must be outside the immutable source checkout")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"schema": 1, **source, "measured_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(), "tier_recipe": args.tier,
        **recipe, "device": args.device, "repeats_per_cell": args.repeats, "durations": args.durations,
        "isolation_declared": args.isolated, "debug": args.debug, "cases": [], "pairs": [],
        "cold_definition": "first utterance in a fresh worker/ASR/native process; OS disk caches may be warm",
        "warm_definition": "second utterance in the same process; no explicit priming or readiness wait",
        "scope": "bundled public audio; real-time synthetic capture, real worker/History/Inserter, memory input",
        "owner_accuracy_accepted": False, "physical_windows_input_measured": False, "complete": False}
    write_json(args.output / "report.json", report)
    try:
        for seconds in args.durations:
            for repeat in range(args.repeats):
                if (args.output / "STOP_AFTER_CURRENT").exists():
                    report["stopped_at_pair_boundary"] = True
                    return 1
                pair_output = args.output / f"{seconds:02d}s-{repeat:03d}"
                pair_output.mkdir(exist_ok=False)
                spec = {"git_commit": source["git_commit"], "audio_seconds": seconds, "repeat": repeat,
                    "tier": args.tier, **recipe, "device": args.device, "output": str(pair_output),
                    **{name: str(getattr(args, name).resolve()) if getattr(args, name) else None
                       for name in ("parakeet_dir", "lid_dir", "models_dir", "runtime_dir", "vad_dir")}}
                report["active_pair"] = {"audio_seconds": seconds, "repeat": repeat}
                write_json(args.output / "report.json", report)
                pair = run_pair(spec, pair_output)
                validate_pair(pair, seconds=seconds, repeat=repeat, commit=source["git_commit"])
                report["cases"].extend(pair["cases"])
                report["pairs"].append({"path": pair_output.name + "/report.json",
                    "sha256": hashlib.sha256((pair_output / "report.json").read_bytes()).hexdigest(),
                    "native_processes": len(pair["native_exits"]), "native_exits": pair["native_exits"]})
                write_json(args.output / "report.json", report)
        report["complete"] = len(report["cases"]) == len(args.durations) * args.repeats * 2
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["failed_pair"] = report.get("active_pair")
        return 1
    finally:
        report["summary"] = summarize(report["cases"], args.tier)
        report["source_unchanged"] = source_receipt() == source
        report["full_matrix"] = (report["complete"] and not args.debug and args.isolated
            and not source["source_dirty"] and report["source_unchanged"]
            and tuple(args.durations) == DURATIONS and args.repeats >= 20 and args.vad_dir is not None)
        target = recipe["decode_target_tps"]
        report["decoder_target_met"] = target is None or bool(report["cases"]) and all(
            row.get("cleanup_at_release", {}).get("decoder", {}).get("median_tps", 0) >= target
            for row in report["cases"])
        report["latency_target_met"] = bool(report["full_matrix"] and report["summary"]["latency_targets_met"]
            and report["summary"]["actual_model_use"])
        report["tier_recipe_target_met"] = report["latency_target_met"] and report["decoder_target_met"]
        report.pop("active_pair", None)
        write_json(args.output / "report.json", report)
        print(json.dumps({key: report[key] for key in ("complete", "full_matrix", "latency_target_met")}))
    return 0  # A completed measurement may honestly miss its targets.


if __name__ == "__main__":
    raise SystemExit(main())
