"""Guard an owned public-file latency trial before importing worker services."""

import argparse
import json
from pathlib import Path
import runpy
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guard-output", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--allow-gpu-metadata", action="store_true")
    args = parser.parse_args(argv)
    from tools.public_worker_guard import install

    spec = json.loads(args.request.read_bytes())
    if (args.allow_gpu_metadata != spec.get("allow_gpu_metadata", False)
            or args.allow_gpu_metadata and spec.get("tier") != "pro"):
        parser.error("GPU metadata permission must match an explicit Pro request")
    install(args.guard_output, allow_gpu_metadata=args.allow_gpu_metadata)
    sys.argv = ["tools.latency_trial", "--request", str(args.request)]
    runpy.run_module("tools.latency_trial", run_name="__main__")


if __name__ == "__main__":
    main()
