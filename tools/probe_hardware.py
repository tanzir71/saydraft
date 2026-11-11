"""Save a local hardware snapshot. This does not benchmark models or download files."""

import argparse
import json
from pathlib import Path

from saydraft.models.hardware import assess_tier, probe_hardware, save_report
from saydraft.privacy.netguard import NetworkGuard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    NetworkGuard.install()
    try:
        report = probe_hardware()
        report["assessment"] = assess_tier(report)
        path = save_report(report, args.output_dir)
        print(json.dumps({"report": str(path), **report}))
    finally:
        NetworkGuard.uninstall()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
