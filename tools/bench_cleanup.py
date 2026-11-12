"""Offline candidate measurements, with checkpointed strict scores and model-use evidence."""

import argparse
import ctypes as c
import hashlib
import json
import math
import os
import re
import subprocess
import time
from contextlib import closing
from ctypes import wintypes as w
from pathlib import Path

from saydraft.cleanup.llm.bakeoff import ObservedCleaner, corpus_digest, measure_cases, summarize
from saydraft.cleanup.llm.candidates import ROOT, candidate_directory, candidate_weight, get_candidate
from saydraft.cleanup.llm.eval_validation import DEFAULT_CORPUS, evaluate, load_cases
from saydraft.cleanup.llm.sidecar import SidecarConfig, SidecarManager
from saydraft.cleanup.llm.windows_process import WindowsJobProcess
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.cleanup.llm.prompts import PromptHints
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.eval import DEFAULT_CORPUS_PATH, load_eval_corpus
from saydraft.models.hardware import probe_hardware
from saydraft.models.runtime_ids import runtime_model_id
from saydraft.privacy.netguard import NetworkGuard


class NativeMeter:
    def __init__(self):
        self.handles, self.pids = [], []
        self.kernel, self.psapi = c.WinDLL("kernel32", use_last_error=True), c.WinDLL("psapi", use_last_error=True)
        for name, result, args in (("OpenProcess", w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
                ("WaitForSingleObject", w.DWORD, [w.HANDLE, w.DWORD]), ("CloseHandle", w.BOOL, [w.HANDLE])):
            function = getattr(self.kernel, name)
            function.restype, function.argtypes = result, args

    def spawn(self, argv, **kwargs):
        process = WindowsJobProcess(argv, **kwargs)
        handle = self.kernel.OpenProcess(0x100410, False, process.pid)
        if not handle:
            process.close()
            raise c.WinError(c.get_last_error())
        self.handles.append(handle)
        self.pids.append(process.pid)
        return process

    def peaks(self):
        class Counters(c.Structure):
            _fields_ = [("cb", w.DWORD), ("faults", w.DWORD)] + [(name, c.c_size_t) for name in
                ("peak", "working", "ppq", "pq", "pnpq", "npq", "page", "peak_page")]
        self.psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, c.POINTER(Counters), w.DWORD]
        self.psapi.GetProcessMemoryInfo.restype = w.BOOL
        result = []
        for handle in self.handles:
            counters = Counters()
            counters.cb = c.sizeof(counters)
            ok = self.psapi.GetProcessMemoryInfo(handle, c.byref(counters), counters.cb)
            result.append(int(counters.peak) if ok else None)
        return result

    def finish(self):
        exited = [self.kernel.WaitForSingleObject(handle, 3000) == 0 for handle in self.handles]
        for handle in self.handles:
            self.kernel.CloseHandle(handle)
        return exited


def throughput(manager, repeats, timeout):
    samples = []
    for _ in range(repeats):
        def operation(client, deadline):
            return client.request_json("/completion", payload={"prompt": "Continue with a short description of a quiet garden.",
                "n_predict": 60, "temperature": 0, "ignore_eos": True, "cache_prompt": False}, deadline=deadline)
        reply = manager.run(operation, timeout=timeout)
        timings = reply.value.get("timings", {}) if reply.value else {}
        tokens, tps = timings.get("predicted_n"), timings.get("predicted_per_second")
        valid = (reply.reason == "ok" and type(tokens) is int and tokens == 60
                 and type(tps) in (int, float) and math.isfinite(tps) and tps > 0)
        samples.append({"reason": reply.reason, "valid": valid, "tokens": timings.get("predicted_n"),
                        "tokens_per_second": timings.get("predicted_per_second"), "timings": timings})
    return samples


def prepare_policy_case(case, local):
    """Explicit test setup outside case timing; never a release-latency claim."""
    if case.mode == "raw" or case.profile == "code/comments" or case.app_group == "code":
        return {"bypassed": True}
    context = DictationContext(mode=case.mode, profile=case.profile, app_title=case.app_title,
                               app_group=case.app_group)
    started = time.perf_counter()
    requested = local.warm_for_context(context)
    preparation = local._preparation
    settled = requested and preparation is not None and preparation.wait(185)
    hints = PromptHints(style={"email": "formal", "chat": "casual"}.get(case.profile, "neutral"),
                        post_rules=True, app=case.app_title or "", group=case.app_group)
    if not settled or not preparation.ready(hints):
        raise RuntimeError("Interactive policy preparation unavailable")
    measurement = local._client.decoder.current
    if measurement is None:
        raise RuntimeError("Interactive decoder measurement unavailable")
    return {"prepared": True, "seconds": time.perf_counter() - started,
            "decoder_calibration": measurement.metadata()}


def policy_complete(rows, golden, adversarial):
    return (len(rows) == golden + adversarial and golden > 0 and adversarial > 0
        and sum(row["suite"] == "golden" for row in rows) == golden
        and all(row.get("policy_preparation", {}).get("prepared")
                or row.get("policy_preparation", {}).get("bypassed") for row in rows))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "models-dir", "runtime-dir", "output"):
        parser.add_argument("--" + name, required=True, type=str if name == "candidate" else Path)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device", help="explicit native device identifier, e.g. Vulkan1")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout-ms", type=int, help="default: 120000 for forced quality; 800 for interactive policy")
    parser.add_argument("--interactive-policy", action="store_true", help="production gate with explicit background setup")
    parser.add_argument("--golden", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--adversarial", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--limit", type=int, help="explicit debug subset; cannot establish full-corpus acceptance")
    parser.add_argument("--throughput-repeats", type=int, default=3)
    parser.add_argument("--include-text", action="store_true", help="explicitly retain case output text in the local journal")
    parser.add_argument("--isolated", action="store_true", help="declare no model transfers/other benchmarks are active")
    args = parser.parse_args(argv)
    if args.timeout_ms is None:
        args.timeout_ms = 800 if args.interactive_policy else 120000
    if args.interactive_policy and (args.timeout_ms != 800 or args.throughput_repeats != 3):
        parser.error("interactive policy uses the real 800 ms cap and three live decoder samples")
    if (os.name != "nt" or not 1 <= args.threads <= 64 or not 1 <= args.timeout_ms <= 120000
            or not 0 <= args.throughput_repeats <= 10 or args.limit is not None and args.limit < 1
            or args.device and (args.backend != "vulkan" or not re.fullmatch(r"Vulkan\d+", args.device))):
        parser.error("Windows, valid bounded measurements, and a matching Vulkan device are required")
    golden, adversarial = load_eval_corpus(args.golden), load_cases(args.adversarial)
    if not args.limit and (len(golden) < 432 or len(adversarial) < 100):
        parser.error("full runs require at least 432 golden/100 adversarial cases; use --limit for debug")
    if not args.limit and args.throughput_repeats < 3:
        parser.error("full runs require at least three 60-token throughput samples")
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal",
        "--", "saydraft", "tools", "eval", "tests", "assets"], cwd=ROOT, text=True)
    if status.strip() and not args.limit:
        parser.error("full runs require a clean source checkout; commit or use an immutable worktree")
    if args.limit:
        golden, adversarial = golden[:args.limit], adversarial[:args.limit]
    model = get_candidate(args.candidate)
    weight = candidate_weight(model, candidate_directory(args.models_dir, model))
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "candidate": model, "runtime": runtime_model_id(args.backend),
        "delivery": "simulated; no live OS keys or microphone", "latency_acceptance_evaluated": False,
        "measurement_kind": "interactive_policy" if args.interactive_policy else "forced_quality",
        "interactive_prompt_preparation": args.interactive_policy,
        "interactive_budget_gate": args.interactive_policy,
        "background_setup_excluded_from_case_latency": args.interactive_policy,
        "backend": args.backend, "device_override": args.device, "threads": args.threads,
        "quality_timeout_ms": args.timeout_ms, "decoding_temperature": 0, "context_size": 4096,
        "max_output_tokens": 256, "full_corpus": args.limit is None, "isolation_declared": args.isolated,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(status.strip()), "golden_sha256": corpus_digest(golden),
        "source_fingerprints": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [*(ROOT / "saydraft").rglob("*.py"), Path(__file__).resolve()]},
        "adversarial_sha256": hashlib.sha256(json.dumps(adversarial, sort_keys=True).encode()).hexdigest(),
        "prompt_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / "saydraft/cleanup/llm/prompts").iterdir() if p.suffix in (".txt", ".json", ".py")},
        "authored_validator": evaluate(adversarial), "selection_performed": False}
    meter, rows, manager, pipeline = NativeMeter(), [], None, None
    NetworkGuard.install()
    try:
        report["hardware"] = probe_hardware()
        def spawn(values, **kwargs):
            return meter.spawn([*values, "--device", args.device] if args.device else values, **kwargs)
        manager = SidecarManager(SidecarConfig(weight, backend=args.backend, threads=args.threads,
            startup_seconds=60, max_restarts=0), resolver=lambda name: args.runtime_dir.resolve(), process_factory=spawn)
        cfg = LocalLLMConfig(enabled=True, model_path=str(weight), backend=args.backend,
                             n_threads=args.threads, timeout_ms=args.timeout_ms, prepare_prompt=args.interactive_policy)
        observed = ObservedCleaner(lambda factory: LocalLLMCleaner(cfg,
            manager_factory=lambda config: manager, client_factory=factory))
        pipeline = DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=observed)
        started = time.perf_counter()
        report["prepared"] = manager.prepare()
        report["preparation_seconds"] = time.perf_counter() - started
        if not report["prepared"]:
            raise RuntimeError("Candidate sidecar did not become ready")
        with (args.output / "cases.jsonl").open("x", encoding="utf-8") as journal, closing(measure_cases(
                golden, adversarial, pipeline, observed, ready=lambda: manager.ready,
                include_text=args.include_text, prepare_case=(lambda case: prepare_policy_case(case, observed.delegate))
                if args.interactive_policy else None)) as measurements:
            for row in measurements:
                rows.append(row)
                journal.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                journal.flush()
                if len(rows) % 10 == 0:
                    print(json.dumps({"completed": len(rows), "decision": row["decision"]}), flush=True)
        if not args.interactive_policy:
            report["throughput_60_tokens"] = throughput(manager, args.throughput_repeats, args.timeout_ms / 1000)
    except BaseException as error:
        report["error_type"] = type(error).__name__  # Never log transcript/response/credential text.
    finally:
        report["peak_native_working_set_bytes"] = meter.peaks()
        if pipeline is not None:
            if args.interactive_policy:
                client = observed.delegate._client
                measurement = client.decoder.current if client is not None else None
                report["live_decoder_calibration"] = measurement.metadata() if measurement is not None else None
            pipeline.close()
        if manager is not None:
            report["last_sidecar_status"] = manager.status
            manager.close()
        report["native_exit_observed"] = meter.finish()
        NetworkGuard.uninstall()
        report.update(summarize(rows, requested_golden=len(golden), requested_adversarial=len(adversarial)))
        report["corpus_measurement_complete"] = report["measurement_complete"]
        samples = report.get("throughput_60_tokens", [])
        report["throughput_complete"] = len(samples) == args.throughput_repeats and all(sample["valid"] for sample in samples)
        report["measurement_complete"] = (report["measurement_complete"] and report["throughput_complete"]
            and bool(report["native_exit_observed"]) and all(report["native_exit_observed"]) and not report.get("error_type"))
        report["policy_measurement_complete"] = (args.interactive_policy and policy_complete(rows, len(golden), len(adversarial))
            and bool(report["native_exit_observed"]) and all(report["native_exit_observed"]) and not report.get("error_type"))
        target = args.output / "report.json"
        with target.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps({"report": str(target), "measurement_complete": report["measurement_complete"],
                          "policy_measurement_complete": report["policy_measurement_complete"],
                          "error_type": report.get("error_type")}), flush=True)
    complete = report["policy_measurement_complete"] if args.interactive_policy else report["measurement_complete"]
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
