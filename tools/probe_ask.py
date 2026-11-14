"""Cache-only native Ask -> History smoke; authored text, no desktop or audio."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.config import default_config
from saydraft.core.ask import AskProcessor, AskSource
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.history import DictationHistoryStore
from saydraft.models.command import ask_choice, installed_command_config
from saydraft.models.downloader import installation_ready
from saydraft.models.layout import model_directories
from saydraft.models.manifest import get_model
from saydraft.models.native_devices import select_device
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'tests/ask_cases.jsonl'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-dir', type=Path, required=True)
    parser.add_argument('--backend', choices=('cpu', 'vulkan'), default='vulkan')
    parser.add_argument('--device')
    parser.add_argument('--holdout', action='store_true', help='Use the separately frozen factual-question follow-up set')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    case_path = ROOT / 'tests/ask_holdout_cases.jsonl' if args.holdout else CASES
    paths = [*(ROOT / 'saydraft').rglob('*.py'), ROOT / 'saydraft/models/manifest.json', Path(__file__).resolve(), case_path]
    fingerprints = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    report = {'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()),
        'source_fingerprints': fingerprints, 'verified': {}, 'backend': args.backend, 'rows': [],
        'case_set': case_path.name,
        'scope': 'authored selected text -> actual exclusive model session -> AskProcessor -> owned SQLite History; '
                 'no UIA, browser, GUI, audio, clipboard, hooks or OS input; no broad factuality or latency qualification'}
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
    cases = [json.loads(line) for line in case_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    history = DictationHistoryStore(args.output / 'public-history.db')
    presentations = []
    def present(result):
        entry = history.get_row(result.history_id)
        presentations.append(entry is not None and entry.mode == 'ask' and entry.cleaned_text == result.text)
    NetworkGuard.install()
    try:
        cfg = default_config()
        cfg['app']['tier'], cfg['labs']['ask_mode'], cfg['command']['backend'] = 'pro', True, args.backend
        choice = ask_choice(cfg)
        config = installed_command_config(choice, resolver=resolve)
        if config is None:
            raise RuntimeError('Explicit verified editing cache is incomplete')
        cleaner = LocalLLMCleaner(LocalLLMConfig(enabled=False), manager_factory=factory)
        session = cleaner.command_session(config, choice.model_id)
        if session is None:
            raise RuntimeError('Exclusive Ask owner unavailable')
        watchdog = threading.Timer(600, session.close)
        watchdog.daemon = True
        watchdog.start()
        report['prepared'] = session.prepare() == 'ready'
        if not report['prepared']:
            raise RuntimeError('Native Ask owner unavailable')
        processor = AskProcessor(editor=session, history=history, present=present)
        with (args.output / 'cases.jsonl').open('x', encoding='utf-8', newline='\n') as journal:
            for case in cases:
                started = time.perf_counter()
                result = processor.process(AskSource(case['source']), case['question'], action=case['action'],
                    current=lambda: True, run_current=lambda operation: operation(), persist_current=lambda operation: operation())
                text = (result.text or '').casefold()
                anchors = (all(any(option.casefold() in text for option in group) for group in case['required'])
                    and not any(option.casefold() in text for option in case['forbidden']))
                row = {'id': case['id'], 'action': case['action'], 'text': result.text, 'reason': result.reason,
                    'history_id': result.history_id, 'anchors_pass': anchors, 'seconds': time.perf_counter() - started}
                report['rows'].append(row)
                journal.write(json.dumps(row, ensure_ascii=False) + '\n')
                journal.flush()
                print(json.dumps({k: row[k] for k in ('id', 'reason', 'anchors_pass')}), flush=True)
        report['history_before_presentation'] = len(presentations) == len(cases) and all(presentations)
        report['history_count'] = len(history.list_recent(limit=len(cases) + 1))
        report['excluded_from_paste_last'] = history.last_transcript() is None
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
        report['pins_unchanged'] = bool(verified_paths) and all(
            installation_ready(get_model(identifier), directory, check_hashes=True)
            for identifier, directory in verified_paths.items())
        report['source_unchanged'] = all(digest(ROOT / name) == sha for name, sha in fingerprints.items())
        NetworkGuard.uninstall()
        report['passed'] = sum(row['reason'] == 'ok' and row['anchors_pass'] for row in report['rows'])
        report['complete'] = (len(report['rows']) == len(cases) and report['source_unchanged'] and report['pins_unchanged']
            and bool(report['native_exit_observed']) and all(report['native_exit_observed']) and not report.get('error_type'))
        report['accepted'] = (report['complete'] and report['passed'] == len(cases)
            and report.get('history_before_presentation') and report.get('excluded_from_paste_last')
            and report.get('history_count') == len(cases))
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('complete', 'accepted', 'passed')}))
    return 0 if report['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
