"""Exercise the explicit installed-model performance check offline, without capture."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from saydraft.cleanup.llm.candidates import ROOT, candidate_directory, candidate_weight, get_candidate
from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.dictation import DictationConfig, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.models.benchmark import run_benchmark
from saydraft.models.native_devices import select_device
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("parakeet-dir", "lid-dir", "models-dir", "runtime-dir", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), required=True)
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("Windows is required")
    candidate = get_candidate(args.candidate)
    weight = candidate_weight(candidate, candidate_directory(args.models_dir, candidate))
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "candidate": candidate["id"], "revision": candidate["revision"], "backend": args.backend,
        "device_override": None, "delivery": "no microphone, history or insertion",
        "selection_performed": False, "tier_acceptance_performed": False}
    meter, pipeline, local = NativeMeter(), None, None
    NetworkGuard.install()
    try:
        from saydraft.asr.language_id import AudioLanguageIdentifier
        from saydraft.asr.router import AsrRouter
        from saydraft.asr.sherpa_parakeet import ParakeetEngine
        from saydraft.config import default_config

        primary = ParakeetEngine(model_dir=args.parakeet_dir)
        asr = AsrRouter(default_config(), engine_factory=lambda _cfg, _route: primary,
            language_identifier=AudioLanguageIdentifier(model_dir=args.lid_dir))
        cfg = LocalLLMConfig(enabled=True, model_path=str(weight), backend=args.backend)
        local = LocalLLMCleaner(cfg, manager_factory=lambda config: SidecarManager(config,
            resolver=lambda _name: args.runtime_dir.resolve(), process_factory=meter.spawn,
            device_selector=lambda *a, **kw: select_device(*a, **kw, process_factory=meter.spawn)))
        pipeline = DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=local)
        pipeline.warm()  # Match application startup before the serial explicit check.
        report["hardware"] = run_benchmark(asr, directory=args.output / "hardware",
                                           cleanup_benchmark=pipeline.benchmark)
        report["decoder_calibration"] = (local._client.decoder.current.metadata()
            if local._client is not None and local._client.decoder.current is not None else None)
        report["prefix_restored"] = bool(local._preparation.wait(185)
            and local._preparation.status["state"] == "prepared")
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        report["peak_native_working_set_bytes"] = meter.peaks()
        report["selected_device"] = (local._manager.selected_device
            if local is not None and local._manager is not None else None)
        if pipeline is not None:
            pipeline.close()
        report["native_exit_observed"] = meter.finish()
        NetworkGuard.uninstall()
        measured = report.get("hardware", {}).get("measurements", {})
        report["probe_complete"] = (measured.get("asr_status") == "ok" and measured.get("cleanup_status") == "ok"
            and len(measured.get("cleanup", [])) == 3 and report.get("prefix_restored")
            and bool(report["native_exit_observed"]) and all(report["native_exit_observed"])
            and not report.get("error_type"))
        with (args.output / "report.json").open("x", encoding="utf-8") as target:
            json.dump(report, target, indent=2, allow_nan=False)
        print(json.dumps({"probe_complete": report["probe_complete"], "measurements": measured}), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
