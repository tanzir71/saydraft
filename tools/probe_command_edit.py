"""Serial cache-only native Command Mode generation on authored public text.

No hooks, microphone, clipboard, foreground reads or OS text input. This tests the
local editing boundary; it does not qualify the full held-recording/delivery flow.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

from saydraft.cleanup.llm.edit import EditClient
from saydraft.cleanup.llm.edit_eval import DEFAULT_CASES, check_case, load_cases
from saydraft.cleanup.llm.sidecar import SidecarConfig, SidecarManager
from saydraft.models.native_devices import select_device
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--runtime-dir', type=Path, required=True)
    parser.add_argument('--backend', choices=('cpu', 'vulkan'), default='vulkan')
    parser.add_argument('--device')
    parser.add_argument('--cases', type=Path, default=DEFAULT_CASES)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    sources = [*(ROOT / 'saydraft').rglob('*.py'), Path(__file__).resolve(), args.cases.resolve()]
    fingerprints = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    report = {'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()),
              'source_fingerprints': fingerprints, 'model_sha256': digest(args.model),
              'runtime_sha256': {p.name: digest(p) for p in args.runtime_dir.iterdir() if p.is_file()},
              'backend': args.backend, 'context_size': 4096, 'threads': 4, 'output_limit': 768,
              'request_timeout_seconds': 45, 'scope': 'native-generation-only; no desktop/audio integration',
              'rows': []}
    cases, meter, manager, watchdog = load_cases(args.cases), NativeMeter(), None, None
    NetworkGuard.install()
    try:
        manager = SidecarManager(SidecarConfig(args.model.resolve(), backend=args.backend,
            startup_seconds=60, max_restarts=0, device=args.device),
            resolver=lambda name: args.runtime_dir.resolve(), process_factory=meter.spawn,
            device_selector=lambda *a, **kw: select_device(*a, **kw, process_factory=meter.spawn))
        watchdog = threading.Timer(1500, manager.close)
        watchdog.daemon = True
        watchdog.start()
        started = time.perf_counter()
        report['prepared'] = manager.prepare()
        report['prepare_seconds'] = time.perf_counter() - started
        if not report['prepared']:
            raise RuntimeError('Installed local model is not ready')
        client = EditClient(manager)
        with (args.output / 'cases.jsonl').open('x', encoding='utf-8', newline='\n') as journal:
            for case in cases:
                started = time.perf_counter()
                reply = client.edit(case['selection'], case['instruction'])
                row = {'id': case['id'], 'kind': case['kind'], 'reason': reply.reason, 'text': reply.text,
                       'stream_complete': reply.stream_complete,
                       'input_tokens': reply.input_tokens, 'output_limit': reply.output_limit,
                       'seconds': time.perf_counter() - started,
                       'case_check': check_case(case, reply.text) if reply.text is not None else 'no_candidate'}
                report['rows'].append(row)
                journal.write(json.dumps(row, ensure_ascii=False) + '\n')
                journal.flush()
                print(json.dumps({k: row[k] for k in ('id', 'reason', 'case_check', 'seconds')}), flush=True)
    except BaseException as error:
        report['error_type'] = type(error).__name__
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if manager is not None:
            report['selected_device'], report['sidecar_status'] = manager.selected_device, manager.status
            manager.close()
        report['native_exit_observed'] = meter.finish()
        NetworkGuard.uninstall()
        report['source_unchanged'] = all(digest(ROOT / name) == value for name, value in fingerprints.items())
        report['model_unchanged'] = digest(args.model) == report['model_sha256']
        report['runtime_unchanged'] = all(digest(args.runtime_dir / name) == value
                                          for name, value in report['runtime_sha256'].items())
        report['attempts_complete'] = (len(report['rows']) == len(cases) and bool(report['native_exit_observed'])
            and all(report['native_exit_observed']) and not report.get('error_type')
            and report['source_unchanged'] and report['model_unchanged'] and report['runtime_unchanged'])
        report['complete'] = report['attempts_complete'] and all(row['stream_complete'] for row in report['rows'])
        report['passed'] = sum(row['reason'] == 'ok' and row['case_check'] == 'ok' for row in report['rows'])
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'complete': report['complete'], 'passed': report['passed'], 'cases': len(cases)}), flush=True)
    return 0 if report['complete'] and report['passed'] == len(cases) else 1


if __name__ == '__main__':
    raise SystemExit(main())
