"""Verify prepared-prefix cleanup using the real 800 ms app deadline, without capture or insertion."""

import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from saydraft.cleanup.llm.candidates import ROOT, candidate_directory, candidate_weight, get_candidate
from saydraft.cleanup.llm.prompts import PromptHints
from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.models.runtime_ids import runtime_model_id
from saydraft.models.native_devices import select_device
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "models-dir", "runtime-dir", "output"):
        parser.add_argument("--" + name, required=True, type=str if name == "candidate" else Path)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device")
    parser.add_argument("--budget-gate", action="store_true", help="exercise actual need/budget policy with five cases")
    args = parser.parse_args(argv)
    if os.name != "nt" or args.device and (args.backend != "vulkan" or not re.fullmatch(r"Vulkan\d+", args.device)):
        parser.error("Windows and a matching bounded Vulkan device are required")
    model = get_candidate(args.candidate)
    weight = candidate_weight(model, candidate_directory(args.models_dir, model))
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"candidate": model["id"], "revision": model["revision"], "runtime": runtime_model_id(args.backend),
        "device": args.device, "app_timeout_ms": 800, "interactive_prompt_preparation": True,
        "interactive_budget_gate": args.budget_gate,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "delivery": "no microphone, database or live insertion", "cases": [], "selection_performed": False}
    meter, pipeline, baseline = NativeMeter(), None, DictationPipeline(DictationConfig())
    NetworkGuard.install()
    try:
        cfg = LocalLLMConfig(enabled=True, model_path=str(weight), backend=args.backend,
                             n_threads=4, budget_gate=args.budget_gate)
        local = LocalLLMCleaner(cfg, manager_factory=lambda config: SidecarManager(replace(config, device=args.device),
            resolver=lambda name: args.runtime_dir.resolve(), process_factory=meter.spawn,
            device_selector=lambda *a, **kw: select_device(*a, **kw, process_factory=meter.spawn)))
        pipeline = DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=local)

        def measure(context, text, preparation, expected_decision):
            expected = baseline.process_transcript(text, context)
            started = time.perf_counter()
            actual = pipeline.process_transcript(text, context)
            row = {**preparation, "profile": context.profile, "expected_decision": expected_decision,
                "cleanup_seconds": time.perf_counter() - started, "decision": pipeline.last_llm_decision,
                "exact": actual == expected, "gate": local.last_gate_info}
            report["cases"].append(row)
            print(json.dumps(row), flush=True)
        for profile, title, group, text in (("general", "Eval Editor", "general", "send 2 files"),
                                             ("email", "Eval Mail", "email", "please review the draft")):
            context = DictationContext(profile=profile, app_title=title, app_group=group)
            started = time.perf_counter()
            requested = pipeline.warm_for_context(context)
            settled = requested and local._preparation.wait(185)
            hints = PromptHints(style="formal" if profile == "email" else "neutral", post_rules=True,
                                app=title, group=group)
            prepared = bool(settled and local._preparation.ready(hints))
            calibration = local._client.decoder.current
            row = {"profile": profile, "prepared": prepared, "preparation_seconds": time.perf_counter() - started,
                   "preparation_status": local._preparation.status,
                   "decoder_calibration": calibration.metadata() if calibration is not None else None}
            if prepared:
                measure(context, text, row, "skip_low_need" if args.budget_gate else "accepted")
                if args.budget_gate:
                    measure(context, "um " + text, row, "high_need")
            else:
                report["cases"].append(row)
            if not prepared:
                break
        if args.budget_gate and len(report["cases"]) == 4:
            expired = SimpleNamespace(**(vars(context) | {"cleanup_deadline": time.monotonic()}))
            measure(expired, "um " + text, row, "skip_budget")
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        report["peak_native_working_set_bytes"] = meter.peaks()
        if pipeline is not None:
            report["selected_device"] = local._manager.selected_device if local._manager is not None else None
            pipeline.close()
        baseline.close()
        report["native_exit_observed"] = meter.finish()
        NetworkGuard.uninstall()
        report["accepted_replies"] = sum(row.get("decision") == "accepted" for row in report["cases"])
        report["probe_complete"] = (len(report["cases"]) == (5 if args.budget_gate else 2)
            and all(row.get("exact") and row.get("decoder_calibration") and row["cleanup_seconds"] <= .8
                and (row.get("decision") in ("accepted", "skip_budget") if row.get("expected_decision") == "high_need"
                     else row.get("decision") == row.get("expected_decision")) for row in report["cases"])
            and bool(report["native_exit_observed"]) and all(report["native_exit_observed"]) and not report.get("error_type"))
        with (args.output / "report.json").open("x", encoding="utf-8") as target:
            json.dump(report, target, indent=2, allow_nan=False)
        print(json.dumps({"probe_complete": report["probe_complete"]}), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
