"""Cache-only native spoken-text translation smoke; no audio, desktop, clipboard or OS input."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.config import default_config
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.models.command import installed_command_config, translation_choice
from saydraft.models.downloader import installation_ready
from saydraft.models.layout import model_directories
from saydraft.models.manifest import get_model
from saydraft.models.native_devices import select_device
from saydraft.privacy.netguard import NetworkGuard
from saydraft.translation import translate
from tools.bench_cleanup import NativeMeter

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'tests/translation_cases.jsonl'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-dir', type=Path, required=True)
    parser.add_argument('--backend', choices=('cpu', 'vulkan'), default='vulkan')
    parser.add_argument('--device')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    files = [*(ROOT / 'saydraft').rglob('*.py'), ROOT / 'saydraft/models/manifest.json', Path(__file__).resolve(), CASES]
    fingerprints = {str(p.relative_to(ROOT)): digest(p) for p in files}
    report = {'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
        'source_fingerprints': fingerprints, 'verified': {}, 'backend': args.backend, 'rows': [],
        'scope': 'authored source text -> actual exclusive model session/translation wrapper; no ASR, recording, clipboard, foreground or input'}
    meter, cleaner, session, watchdog = NativeMeter(), None, None, None
    verified_paths = {}
    def resolve(identifier, *, check_hashes=False):
        model = get_model(identifier)
        for directory in model_directories(args.models_dir.resolve(), model):
            if installation_ready(model, directory, check_hashes=check_hashes):
                if check_hashes:
                    report['verified'][identifier] = {f['path']: f['sha256'] for f in model['files']}
                    verified_paths[identifier] = directory
                return directory
        return None
    def factory(config):
        return SidecarManager(config, resolver=resolve, process_factory=meter.spawn,
            device_selector=lambda *a, **kw: select_device(*a, **{**kw, 'requested': args.device}, process_factory=meter.spawn))
    cases = [json.loads(line) for line in CASES.read_text(encoding='utf-8').splitlines() if line.strip()]
    NetworkGuard.install()
    try:
        cfg = default_config()
        cfg['app']['tier'], cfg['labs']['translate_mode'], cfg['command']['backend'] = 'pro', True, args.backend
        choice = translation_choice(cfg)
        config = installed_command_config(choice, resolver=resolve)
        if config is None:
            raise RuntimeError('Explicit verified translation cache is incomplete')
        cleaner = LocalLLMCleaner(LocalLLMConfig(enabled=False), manager_factory=factory)
        session = cleaner.command_session(config, choice.model_id)
        watchdog = threading.Timer(600, session.close)
        watchdog.daemon = True
        watchdog.start()
        report['prepared'] = session.prepare() == 'ready'
        if not report['prepared']:
            raise RuntimeError('Native translation owner unavailable')
        with (args.output / 'cases.jsonl').open('x', encoding='utf-8', newline='\n') as journal:
            for case in cases:
                started = time.perf_counter()
                reply = translate(session, case['selection'], case['target_language'], source_language=case['source_language'])
                text = reply.text or ''
                anchors = all(any(option.casefold() in text.casefold() for option in group) for group in case['required'])
                unwanted = any(x.casefold() in text.casefold() for x in case.get('forbidden', []))
                row = {'id': case['id'], 'source_language': case['source_language'], 'target_language': case['target_language'],
                    'text': reply.text, 'reason': reply.reason, 'stream_complete': reply.stream_complete,
                    'input_tokens': reply.input_tokens, 'output_limit': reply.output_limit,
                    'anchors_pass': anchors and not unwanted, 'seconds': time.perf_counter() - started}
                report['rows'].append(row)
                journal.write(json.dumps(row, ensure_ascii=False) + '\n')
                journal.flush()
                print(json.dumps({'id': row['id'], 'reason': row['reason'], 'anchors': row['anchors_pass']}), flush=True)
    except Exception as error:
        report['error_type'] = type(error).__name__
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if session is not None:
            session.close()
        if cleaner is not None:
            cleaner.close()
        report['native_exit_observed'] = meter.finish()
        report['pins_unchanged'] = all(installation_ready(get_model(identifier), directory, check_hashes=True)
                                       for identifier, directory in verified_paths.items())
        report['source_unchanged'] = all(digest(ROOT / p) == sha for p, sha in fingerprints.items())
        NetworkGuard.uninstall()
        report['passed'] = sum(r['reason'] == 'ok' and r['stream_complete'] and r['anchors_pass'] for r in report['rows'])
        report['complete'] = (len(report['rows']) == len(cases) and report['source_unchanged'] and report['pins_unchanged']
            and bool(report['native_exit_observed']) and all(report['native_exit_observed']) and not report.get('error_type'))
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'complete': report['complete'], 'passed': report['passed'], 'cases': len(cases)}))
    return 0 if report['complete'] and report['passed'] == len(cases) else 1


if __name__ == '__main__':
    raise SystemExit(main())
