"""Run public-file latency measurement with owner I/O barred in parent/children."""

import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--guard-output", type=Path, required=True)
    args, remaining = parser.parse_known_args(argv)
    from tools.public_worker_guard import install

    install(args.guard_output)
    from tools.latency_matrix import main as measure

    return measure(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
