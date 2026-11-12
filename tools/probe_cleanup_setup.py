"""Verify cached model/runtime setup and owned inference in a fresh QA directory."""

import argparse
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from saydraft.cleanup.llm.candidates import ROOT, candidate_directory, candidate_ready, get_candidate
from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.model_download import model_relative_dir
from saydraft.models.cleanup import cleanup_bundle, download_cleanup_model
from saydraft.models.downloader import installation_ready
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), required=True)
    for name in ("candidate-cache", "runtime-cache", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    model, runtime = cleanup_bundle(args.model, args.backend)
    candidate = get_candidate(args.model)
    source = candidate_directory(args.candidate_cache, candidate)
    if not candidate_ready(candidate, source) or not installation_ready(runtime, args.runtime_cache, check_hashes=True):
        parser.error("Complete verified model/runtime caches are required")
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.output / "models"
    target = root / model_relative_dir(model)
    stage = target.with_name(target.name + ".download")
    runtime_target = root / model_relative_dir(runtime)
    stage.mkdir(parents=True)
    runtime_target.mkdir(parents=True)
    for file in model["files"]:
        if "url" in file:
            os.link(source / file["path"], stage / file["path"])
    for name in [file["path"] for file in runtime["files"]] + [".verified.json"]:
        os.link(args.runtime_cache / name, runtime_target / name)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "model": model["id"], "revision": model["revision"], "backend": args.backend,
        "delivery": "no microphone, history, insertion or user settings", "tier_acceptance_performed": False}
    meter, local = NativeMeter(), None
    NetworkGuard.install()
    try:
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Unexpected network request")) as network:
            path = download_cleanup_model(args.model, args.backend, models_dir=root)
            assert download_cleanup_model(args.model, args.backend, models_dir=root) == path
            report["network_requests"] = network.call_count
        report["complete_installation"] = (installation_ready(model, target, check_hashes=True)
            and installation_ready(runtime, runtime_target, check_hashes=True) and not stage.exists())
        cfg = LocalLLMConfig(enabled=True, model_path=str(path), backend=args.backend)
        local = LocalLLMCleaner(cfg, manager_factory=lambda config: SidecarManager(config,
            resolver=lambda _name: runtime_target.resolve(), process_factory=meter.spawn,
            device_selector=lambda *a, **kw: _select(meter, *a, **kw)))
        local.warm()
        assert local._preparation.wait(185)
        report["cleanup_samples"] = local.benchmark()
        report["prefix_restored"] = (local._preparation.wait(185)
            and local._preparation.status["state"] == "prepared")
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        if local is not None:
            local.close()
        report["native_exit_observed"] = meter.finish()
        NetworkGuard.uninstall()
        report["probe_complete"] = (report.get("complete_installation") and report.get("network_requests") == 0
            and len(report.get("cleanup_samples", [])) == 3 and report.get("prefix_restored")
            and bool(report["native_exit_observed"]) and all(report["native_exit_observed"])
            and not report.get("error_type"))
        with (args.output / "report.json").open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, allow_nan=False)
        print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


def _select(meter, *args, **kwargs):
    from saydraft.models.native_devices import select_device
    return select_device(*args, **kwargs, process_factory=meter.spawn)


if __name__ == "__main__":
    raise SystemExit(main())
