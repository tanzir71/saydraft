"""Verify native device IDs and Windows type matching without loading model weights."""

import argparse
import json
import subprocess
from pathlib import Path

from saydraft.models.native_devices import choose_device, probe_devices
from saydraft.models.windows_hardware import vulkan_devices
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "weights_loaded": False, "inference_performed": False, "settings_changed": False}
    meter = NativeMeter()
    NetworkGuard.install()
    try:
        report["native"] = probe_devices(args.runtime_dir, process_factory=meter.spawn)
        report["windows"] = vulkan_devices()
        report["selected"] = choose_device(report["native"], report["windows"])
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        report["native_exit_observed"] = meter.finish()
        NetworkGuard.uninstall()
        report["passed"] = bool(report.get("selected") and report["native_exit_observed"]
                                and all(report["native_exit_observed"]) and not report.get("error_type"))
        with (args.output / "report.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
        print(json.dumps(report, allow_nan=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
