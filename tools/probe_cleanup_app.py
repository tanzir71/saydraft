"""Compatibility entry point for native cleanup soak; no microphone or OS input.

The canonical tools.soak runner combines owned sidecars, RSS, real persistence
and Inserter logic with an in-memory clipboard/keyboard. Model/runtime paths and
a fresh QA folder remain explicit. The one-token developer fixture makes no
cleanup-quality claim.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.soak import main as soak_main  # noqa: E402
from tools.soak_native import expected_outcomes  # noqa: E402,F401


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-dir', 'model', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--backend', choices=('cpu', 'vulkan'), default='cpu')
    parser.add_argument('--device')
    parser.add_argument('--cycles', type=int, default=10)
    parser.add_argument('--fixture-context-override', action='store_true')
    parser.add_argument('--isolated', action='store_true')
    args = parser.parse_args(argv)
    forwarded = ['--cleanup-runtime-dir', str(args.runtime_dir), '--cleanup-model', str(args.model),
        '--output', str(args.output), '--cleanup-backend', args.backend, '--cycles', str(args.cycles), '--json']
    if args.device:
        forwarded += ['--device', args.device]
    if args.fixture_context_override:
        forwarded.append('--fixture-context-override')
    if args.isolated:
        forwarded.append('--isolated')
    return soak_main(forwarded)


if __name__ == '__main__':
    raise SystemExit(main())
