"""Isolated developer comparison of full and shorter Whisper encoder padding.

Never changes production policy or installed package files. Only bundled public
fixtures and synthetic silence are read; no microphone or OS input is used.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ("full", "min500", "min1000", "min1500")


def write_report(path, report):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def run(model_directory, output, repeats):
    import numpy as np
    import soundfile as sf
    from saydraft.privacy.netguard import NetworkGuard
    from saydraft.privacy.telemetry import configure_process_privacy
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model
    from saydraft.stt.whisper_engine import _default_model_factory
    from tools.latency_environment import runtime_environment

    if not 1 <= repeats <= 10:
        raise ValueError("Use one to ten diagnostic repeats")
    if importlib.metadata.version("faster-whisper") != "1.2.1":
        raise ValueError("Probe requires the reviewed faster-whisper 1.2.1")
    if output.exists() or output.resolve().is_relative_to(ROOT):
        raise ValueError("Choose a fresh output directory outside the checkout")
    if not installation_ready(get_model("whisper-base"), model_directory, check_hashes=True):
        raise ValueError("Pinned Whisper base bundle is incomplete")
    output.mkdir(parents=True)
    report = {"schema": 1, "complete": False, "production_qualification": False,
              "measured_at": datetime.now(timezone.utc).isoformat(),
              "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "runtime_environment": runtime_environment(), "model": "whisper-base",
              "model_revision": get_model("whisper-base")["revision"], "repeats": repeats,
              "decode": {"beam_size": 5, "language": "auto", "condition_on_previous_text": False,
                         "vad_filter": False, "cpu_threads": 4, "num_workers": 1},
              "scope": "warm decoder-only compatibility/timing diagnostic; full public audio retained, no production or timestamp/owner-accuracy qualification",
              "microphone_used": False, "audio_devices_enumerated": False,
              "input_injected": False, "owner_clipboard_accessed": False,
              "fixtures": {}, "cases": []}
    NetworkGuard.install()
    configure_process_privacy()
    module = model = original_pad = original_encode = None
    current = None
    try:
        fixtures = {}
        for name, relative in (("hello", "tests/fixtures/hello.wav"), ("benchmark", "assets/audio/benchmark.wav"),
                               ("bengali", "tests/fixtures/fleurs-bn.wav"), ("arabic", "tests/fixtures/fleurs-ar.wav")):
            path = ROOT / relative
            audio, rate = sf.read(path, dtype="float32")
            if rate != 16000 or audio.ndim != 1 or not np.isfinite(audio).all():
                raise ValueError("Invalid bundled fixture")
            fixtures[name] = audio
            report["fixtures"][name] = {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                         "samples": len(audio), "rate": rate}
        for seconds in (3, 8):
            name = f"silence{seconds}"
            fixtures[name] = np.zeros(seconds * 16000, dtype=np.float32)
            report["fixtures"][name] = {"synthetic": "zeros-float32", "samples": seconds * 16000, "rate": 16000}
        model = _default_model_factory(str(model_directory), device="cpu", compute_type="int8",
                                       cpu_threads=4, num_workers=1, local_files_only=True)
        module = importlib.import_module("faster_whisper.transcribe")
        original_pad, original_encode = module.pad_or_trim, model.encode
        report["reviewed_sources_sha256"] = {name: hashlib.sha256(Path(importlib.import_module("faster_whisper." + name).__file__).read_bytes()).hexdigest()
                                              for name in ("transcribe", "audio")}

        def pad(array, length=3000, *, axis=-1):
            frames = array.shape[axis]
            if frames > 3000 or length != 3000:
                raise ValueError("Feature padding contract changed")
            floor = 3000 if current["policy"] == "full" else int(current["policy"][3:])
            target = min(3000, max(floor, math.ceil(frames / 500) * 500))
            if target < frames:
                raise ValueError("Probe would discard features")
            current["padding"].append({"input_frames": frames, "output_frames": target})
            return original_pad(array, target, axis=axis)

        def encode(features):
            started = time.perf_counter()
            try:
                return original_encode(features)
            finally:
                current["encoding"].append({"shape": list(features.shape), "seconds": time.perf_counter() - started})

        # Explicit full-padding warm-up is excluded from every timing comparison.
        segments, _ = model.transcribe(fixtures["hello"], beam_size=5, language=None,
                                       vad_filter=False, condition_on_previous_text=False)
        list(segments)
        module.pad_or_trim, model.encode = pad, encode
        with (output / "cases.jsonl").open("x", encoding="utf-8") as journal:
            for repeat in range(repeats):
                names = list(fixtures) if repeat % 2 == 0 else list(reversed(fixtures))
                for name in names:
                    # Rotate policy order to reduce a fixed first-policy cache bias.
                    order = POLICIES[repeat % len(POLICIES):] + POLICIES[:repeat % len(POLICIES)]
                    for policy in order:
                        current = {"fixture": name, "repeat": repeat, "policy": policy, "padding": [], "encoding": []}
                        started = time.perf_counter()
                        try:
                            segments, info = model.transcribe(fixtures[name], beam_size=5, language=None,
                                                             vad_filter=False, condition_on_previous_text=False)
                            segments = list(segments)
                            text = " ".join(" ".join(segment.text.split()) for segment in segments).strip()
                            current.update(text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                           text_characters=len(text), language=info.language,
                                           language_probability=float(info.language_probability),
                                           segment_times=[{"start": float(segment.start), "end": float(segment.end)} for segment in segments],
                                           temperatures=[float(segment.temperature) for segment in segments])
                        except Exception as error:
                            current["error_type"] = type(error).__name__
                        current["seconds"] = time.perf_counter() - started
                        report["cases"].append(current)
                        journal.write(json.dumps(current, allow_nan=False) + "\n")
                        journal.flush()
                        write_report(output / "report.json", report)
        summary = {}
        for name in fixtures:
            controls = [row for row in report["cases"] if row["fixture"] == name and row["policy"] == "full"]
            control_identities = {(row.get("text_sha256"), row.get("language")) for row in controls}
            baseline_stable = len(control_identities) == 1 and not any(row.get("error_type") for row in controls)
            summary[name] = {"baseline_stable": baseline_stable, "policies": {}}
            for policy in POLICIES:
                rows = [row for row in report["cases"] if row["fixture"] == name and row["policy"] == policy]
                valid = [row for row in rows if not row.get("error_type")]
                matches = sum((row.get("text_sha256"), row.get("language")) in control_identities for row in valid)
                summary[name]["policies"][policy] = {"n": len(rows), "successful": len(valid),
                    "matches_baseline": matches, "all_match_stable_baseline": baseline_stable and matches == repeats,
                    "median_seconds": statistics.median(row["seconds"] for row in valid) if valid else None,
                    "all_empty": bool(valid) and all(row["text_characters"] == 0 for row in valid)}
        report["summary"] = summary
        report["complete"] = len(report["cases"]) == len(fixtures) * len(POLICIES) * repeats
    finally:
        if module is not None and original_pad is not None:
            module.pad_or_trim = original_pad
            model.encode = original_encode
            report["python_hooks_restored"] = module.pad_or_trim is original_pad and model.encode is original_encode
        report["capture_runtime_imported"] = "sounddevice" in sys.modules
        NetworkGuard.uninstall()
        write_report(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--isolated", action="store_true", help="declare other local native/model/test workloads stopped")
    args = parser.parse_args(argv)
    if not args.isolated:
        parser.error("--isolated is required")
    report = run(args.model_dir, args.output, args.repeats)
    print(json.dumps({"complete": report["complete"], "cases": len(report["cases"]),
                      "production_qualification": False, "python_hooks_restored": report.get("python_hooks_restored")}))
    return 0 if report["complete"] and report.get("python_hooks_restored") and not report["capture_runtime_imported"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
