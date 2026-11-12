"""Replay bundled audio through native ASR, cleanup, SQLite and checked stub insertion.

Warm 3/8/20-second fixture replays; no microphone, global hooks or OS keys.
Capture is instantaneous replay with the minimum-recording guard disabled only
in this probe. All recognition occurs after release; background ASR is disabled.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf

from saydraft.asr.language_id import AudioLanguageIdentifier
from saydraft.asr.router import AsrRouter
from saydraft.asr.sherpa_parakeet import ParakeetEngine
from saydraft.cleanup.llm.bakeoff import latency
from saydraft.cleanup.llm.candidates import ROOT, candidate_directory, candidate_weight, get_candidate
from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.config import default_config
from saydraft.core.container import Services
from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.core.session import DictationSession, SessionState
from saydraft.core.worker import SessionWorker
from saydraft.dictation import DictationConfig, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.history import DictationHistoryStore
from saydraft.insert.inserter import InsertionResult
from saydraft.models.benchmark import fixture_path
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter


def summary(rows, mode):
    groups = {str(seconds): {**latency([row["seconds"] for row in rows if row["audio_seconds"] == seconds]),
        "decisions": dict(Counter(row["decision"] for row in rows if row["audio_seconds"] == seconds))}
        for seconds in (3, 8, 20)}
    median, tail = (.6, 1.2) if mode == "rules" else (1.2, 2.0)
    return {"groups": groups, "p50_target_seconds": median, "p95_target_seconds": tail,
        "targets_met": all(group["n"] >= 20 and group["p50_seconds"] <= median
                           and group["p95_seconds"] <= tail for group in groups.values()),
        "accepted_replies": sum(row["decision"] == "accepted" for row in rows)}


def wait_for(predicate, seconds=120):
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError("Fixture replay did not settle")
        time.sleep(.002)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("parakeet-dir", "lid-dir", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("models-dir", "runtime-dir"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--candidate")
    parser.add_argument("--mode", choices=("rules", "llm"), default="llm")
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device")
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args(argv)
    if (os.name != "nt" or not 20 <= args.repeats <= 100 or args.mode == "llm" and not all(
            (args.candidate, args.models_dir, args.runtime_dir)) or args.device and (
                args.backend != "vulkan" or not re.fullmatch(r"Vulkan\d+", args.device))):
        parser.error("Windows, 20–100 repeats, installed LLM paths and a matching Vulkan device are required")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        parser.error("use a clean immutable source checkout")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "mode": args.mode, "candidate": args.candidate, "backend": args.backend, "device": args.device,
        "repeats_per_duration": args.repeats, "source_fixture_sha256": hashlib.sha256(fixture_path().read_bytes()).hexdigest(),
        "delivery": "fixture replay; SQLite History and stub insertion; no microphone, hooks or OS keys",
        "background_transcription": False, "capture_guard_disabled_for_replay": True,
        "scope": "warm repeated public fixture; no owner accuracy or tier acceptance", "cases": []}
    meter, worker, local, pipeline = NativeMeter(), None, None, None
    released_at, inserted = None, []
    NetworkGuard.install()
    try:
        report["stage"] = "setup"
        audio, rate = sf.read(fixture_path(), dtype="float32")
        if rate != 16000 or audio.shape != (128000,) or not np.isfinite(audio).all():
            raise ValueError("Invalid bundled speech fixture")
        config = default_config()
        config["stt"]["background_transcription"] = False
        config["dictation"]["mode"] = "aggressive" if args.mode == "llm" else "balanced"
        cfg = LocalLLMConfig()
        if args.mode == "llm":
            model = get_candidate(args.candidate)
            weight = candidate_weight(model, candidate_directory(args.models_dir, model))
            def spawn(values, **kwargs):
                return meter.spawn([*values, "--device", args.device] if args.device else values, **kwargs)
            cfg = LocalLLMConfig(enabled=True, model_path=str(weight), backend=args.backend, n_threads=4)
            local = LocalLLMCleaner(cfg, manager_factory=lambda settings: SidecarManager(settings,
                resolver=lambda name: args.runtime_dir.resolve(), process_factory=spawn))
        pipeline = DictationPipeline(DictationConfig(llm=cfg), **({"llm_cleaner": local} if local else {}))
        history = DictationHistoryStore(args.output / "history.db")
        def insert(text, **kwargs):
            assert released_at is not None and history.list_recent()[0].cleaned_text == text
            inserted.append(time.perf_counter())
            return InsertionResult("inserted", "fixture")
        capture = SimpleNamespace(sample_rate=rate, audio=audio, start=lambda: None, stop=lambda: capture.audio.copy())
        primary = ParakeetEngine(model_dir=args.parakeet_dir)
        router = AsrRouter(config, engine_factory=lambda settings, route: primary, installed=lambda model: False,
            language_identifier=AudioLanguageIdentifier(model_dir=args.lid_dir))
        formatter, inserter = IdentityFormatter(), SimpleNamespace(insert_text=insert)
        processor = TranscriptProcessor(cleaner=pipeline, formatter=formatter, history=history, inserter=inserter)
        services = Services(config, capture, router, pipeline, formatter, inserter,
            SimpleNamespace(capture=lambda: TargetContext("fixture", "Fixture QA")), history, processor, [])
        worker = SessionWorker(services, session=DictationSession(minimum_recording_seconds=0))
        if local is not None:
            report["stage"] = "prefix_preparation"
            from tools.bench_cleanup import prepare_policy_case
            from saydraft.eval import EvalCase
            report["background_preparation"] = prepare_policy_case(
                EvalCase("setup", "", "", "aggressive", "general", app_title="Fixture QA"), local)
        with (args.output / "cases.jsonl").open("x", encoding="utf-8") as journal:
            for seconds in (3, 8, 20):
                capture.audio = np.tile(audio, int(np.ceil(seconds / 8)))[:seconds * rate]
                for repeat in range(args.repeats):
                    report["stage"] = "arming"
                    released_at = None
                    before = len(inserted)
                    if not worker.start_recording():
                        raise RuntimeError("Replay capture refused")
                    wait_for(lambda: worker.session.state != SessionState.ARMING)
                    if worker.session.state != SessionState.LISTENING or len(inserted) != before:
                        raise RuntimeError("Replay capture failed to arm safely")
                    released_at = time.perf_counter()
                    report["stage"] = "release_processing"
                    worker.stop_recording()
                    wait_for(lambda: not worker.busy, 30)
                    row = history.list_recent()[0]
                    if len(inserted) != before + 1 or not row.raw_text or row.id != before + 1:
                        raise RuntimeError("Replay did not persist before checked delivery")
                    item = {"audio_seconds": seconds, "repeat": repeat, "seconds": inserted[-1] - released_at,
                        "decision": row.llm_decision, "asr_model": row.model, "timings": json.loads(row.timings_json),
                        "cleanup_gate": local.last_gate_info if local else None,
                        "release_deadline_present": worker._context.cleanup_deadline is not None}
                    report["cases"].append(item)
                    report["stage"] = "delivered"
                    journal.write(json.dumps(item, allow_nan=False) + "\n")
                    journal.flush()
                print(json.dumps({"audio_seconds": seconds, "completed": len(report["cases"])}), flush=True)
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        report["peak_native_working_set_bytes"] = meter.peaks()
        if worker is not None:
            worker.shutdown()
            worker.executor.shutdown(wait=True)
        elif pipeline is not None:
            pipeline.close()
        elif local is not None:
            local.close()
        report["native_exit_observed"] = meter.finish()
        NetworkGuard.uninstall()
        report.update(summary(report["cases"], args.mode))
        report["measurement_complete"] = (len(report["cases"]) == args.repeats * 3 and not report.get("error_type")
            and all(row["release_deadline_present"] for row in report["cases"])
            and all(report["native_exit_observed"]) and (args.mode == "rules" or bool(report["native_exit_observed"])))
        report["latency_target_met"] = (report["measurement_complete"] and report["targets_met"]
            and (args.mode == "rules" or report["accepted_replies"] > 0))
        with (args.output / "report.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
        print(json.dumps({key: report[key] for key in ("measurement_complete", "latency_target_met", "accepted_replies")}), flush=True)
    return 0 if report["measurement_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
