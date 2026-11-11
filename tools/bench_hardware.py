"""Benchmark installed speech weights locally and append a hardware report."""

import argparse
import json
from pathlib import Path

from saydraft.models.benchmark import run_benchmark
from saydraft.privacy.netguard import NetworkGuard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parakeet-dir", type=Path, required=True)
    parser.add_argument("--lid-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    NetworkGuard.install()
    try:
        from saydraft.asr.sherpa_parakeet import ParakeetEngine

        engine = ParakeetEngine(model_dir=args.parakeet_dir)
        if args.lid_dir:
            from saydraft.asr.language_id import AudioLanguageIdentifier
            from saydraft.asr.router import AsrRouter
            from saydraft.config import default_config

            engine = AsrRouter(default_config(), engine_factory=lambda _config, _route, primary=engine: primary,
                               language_identifier=AudioLanguageIdentifier(model_dir=args.lid_dir))
        report = run_benchmark(engine, directory=args.output_dir)
        print(json.dumps({key: report[key] for key in ("assessment", "measurements")}))
        return 0 if report["measurements"]["asr_status"] == "ok" else 1
    finally:
        NetworkGuard.uninstall()


if __name__ == "__main__":
    raise SystemExit(main())
