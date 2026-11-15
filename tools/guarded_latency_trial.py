"""Guard an owned public-file latency trial before importing worker services."""

import argparse
from pathlib import Path
import runpy
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guard-output", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(argv)
    from tools.public_worker_guard import install

    install(args.guard_output)
    sys.argv = ["tools.latency_trial", "--request", str(args.request)]
    runpy.run_module("tools.latency_trial", run_name="__main__")


if __name__ == "__main__":
    main()
