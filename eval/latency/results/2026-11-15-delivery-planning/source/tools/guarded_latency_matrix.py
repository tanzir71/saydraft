"""Run public-file latency measurement with owner I/O barred in parent/children."""

import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--guard-output", type=Path, required=True)
    parser.add_argument("--allow-gpu-metadata", action="store_true")
    args, remaining = parser.parse_known_args(argv)
    from tools.public_worker_guard import install

    install(args.guard_output, allow_gpu_metadata=args.allow_gpu_metadata)
    from tools.latency_matrix import main as measure

    return measure(remaining + (["--allow-gpu-metadata"] if args.allow_gpu_metadata else []))


if __name__ == "__main__":
    raise SystemExit(main())
