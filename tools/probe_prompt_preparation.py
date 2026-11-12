"""Verify prepared-prefix cleanup using the real 800 ms app deadline, without capture or insertion."""

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

from saydraft.cleanup.llm.candidates import ROOT, candidate_directory, candidate_weight, get_candidate
from saydraft.cleanup.llm.prompts import PromptHints
from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.models.runtime_ids import runtime_model_id
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "models-dir", "runtime-dir", "output"):
        parser.add_argument("--" + name, required=True, type=str if name == "candidate" else Path)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device")
    args = parser.parse_args(argv)
    if os.name != "nt" or args.device and (args.backend != "vulkan" or not re.fullmatch(r"Vulkan\d+", args.device)):
        parser.error("Windows and a matching bounded Vulkan device are required")
    model = get_candidate(args.candidate)
    weight = candidate_weight(model, candidate_directory(args.models_dir, model))
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"candidate": model["id"], "revision": model["revision"], "runtime": runtime_model_id(args.backend),
        "device": args.device, "app_timeout_ms": 800, "interactive_prompt_preparation": True,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "delivery": "no microphone, database or live insertion", "cases": [], "selection_performed": False}
    meter, pipeline, baseline = NativeMeter(), None, DictationPipeline(DictationConfig())
    NetworkGuard.install()
    try:
        def spawn(values, **kwargs):
            return meter.spawn([*values, "--device", args.device] if args.device else values, **kwargs)
        cfg = LocalLLMConfig(enabled=True, model_path=str(weight), backend=args.backend, n_threads=4)
        local = LocalLLMCleaner(cfg, manager_factory=lambda config: SidecarManager(config,
            resolver=lambda name: args.runtime_dir.resolve(), process_factory=spawn))
        pipeline = DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=local)
        for profile, title, group, text in (("general", "Eval Editor", "general", "send 2 files"),
                                             ("email", "Eval Mail", "email", "please review the draft")):
            context = DictationContext(profile=profile, app_title=title, app_group=group)
            started = time.perf_counter()
            requested = pipeline.warm_for_context(context)
            settled = requested and local._preparation.wait(125)
            hints = PromptHints(style="formal" if profile == "email" else "neutral", post_rules=True,
                                app=title, group=group)
            prepared = bool(settled and local._preparation.ready(hints))
            row = {"profile": profile, "prepared": prepared, "preparation_seconds": time.perf_counter() - started,
                   "preparation_status": local._preparation.status}
            if prepared:
                expected = baseline.process_transcript(text, context)
                started = time.perf_counter()
                actual = pipeline.process_transcript(text, context)
                row.update(cleanup_seconds=time.perf_counter() - started, decision=pipeline.last_llm_decision,
                           exact=actual == expected)
            report["cases"].append(row)
            print(json.dumps(row), flush=True)
            if not prepared or row.get("decision") != "accepted":
                break
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        report["peak_native_working_set_bytes"] = meter.peaks()
        if pipeline is not None:
            pipeline.close()
        baseline.close()
        report["native_exit_observed"] = meter.finish()
        NetworkGuard.uninstall()
        report["probe_complete"] = (len(report["cases"]) == 2 and all(row.get("exact")
            and row.get("decision") == "accepted" and row["cleanup_seconds"] <= .8 for row in report["cases"])
            and bool(report["native_exit_observed"]) and all(report["native_exit_observed"]) and not report.get("error_type"))
        with (args.output / "report.json").open("x", encoding="utf-8") as target:
            json.dump(report, target, indent=2, allow_nan=False)
        print(json.dumps({"probe_complete": report["probe_complete"]}), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
