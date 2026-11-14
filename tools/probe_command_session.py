"""Cache-only native cleanup -> Command -> fresh cleanup ownership probe.

Authored text only. No audio, foreground, clipboard, hooks or OS text input.
This is a model-owner boundary check, not packaged Command Mode acceptance.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

from saydraft.cleanup.llm.edit_eval import check_case, load_cases
from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.config import default_config
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.dictation.types import DictationContext
from saydraft.models.command import command_choice, installed_command_config
from saydraft.models.downloader import installation_ready
from saydraft.models.layout import model_directories
from saydraft.models.manifest import get_model, load_manifest
from saydraft.models.native_devices import select_device
from saydraft.privacy.netguard import NetworkGuard
from tools.bench_cleanup import NativeMeter

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def prior_exits_observed(meter):
    # The owned process wrapper closes its original handle after retirement.
    # NativeMeter retains separate observation handles until final evidence.
    return all(meter.kernel.WaitForSingleObject(handle, 0) == 0 for handle in meter.handles)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-dir', type=Path, required=True)
    parser.add_argument('--backend', choices=('cpu', 'vulkan'), default='vulkan')
    parser.add_argument('--device')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [*(ROOT / 'saydraft').rglob('*.py'), ROOT / 'saydraft/models/manifest.json',
             Path(__file__).resolve(), ROOT / 'tests/command_edits.jsonl']
    fingerprints = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    report = {'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()),
              'source_fingerprints': fingerprints, 'backend': args.backend,
              'scope': 'native model-owner boundary, authored text only; no speech or desktop integration',
              'stages': [], 'rows': [], 'overlap_refused': True, 'verified': {}}
    cleaner = session = watchdog = None
    meter, processes = NativeMeter(), []

    def resolve(identifier, *, check_hashes=False):
        model = get_model(identifier)
        for directory in model_directories(args.models_dir.resolve(), model):
            if installation_ready(model, directory, check_hashes=check_hashes):
                if check_hashes:
                    report['verified'][identifier] = {f['path']: f['sha256'] for f in model['files']}
                return directory
        return None

    def spawn(argv, **kwargs):
        if not prior_exits_observed(meter):
            report['overlap_refused'] = False
            raise RuntimeError('Prior owned process exit was not observed')
        process = meter.spawn(argv, **kwargs)
        processes.append(process)
        return process

    def manager_factory(config):
        return SidecarManager(config, resolver=resolve, process_factory=spawn,
            device_selector=lambda *a, **kw: select_device(*a, **{**kw, 'requested': args.device},
                                                          process_factory=spawn))

    def stage(name, action):
        started = time.perf_counter()
        value = action()
        serial = value if type(value) in (str, bool, int, float, type(None)) else value is not None
        report['stages'].append({'name': name, 'result': serial, 'seconds': time.perf_counter() - started})
        print(json.dumps(report['stages'][-1]), flush=True)
        return value

    NetworkGuard.install()
    try:
        config = default_config()
        config['app']['tier'] = 'pro'
        config['labs']['command_mode'] = True
        config['command']['backend'] = args.backend
        choice = command_choice(config)
        command_config = stage('verify_command_cache', lambda: installed_command_config(choice, resolver=resolve))
        # Keep the report JSON-only, without local model paths or private handles.
        report['stages'][-1]['result'] = command_config is not None
        if command_config is None:
            raise ValueError('Command model/runtime must already be verified in the supplied cache')
        cleanup_model = get_model(load_manifest()['cleanup_defaults']['pro'])
        directory = resolve(cleanup_model['id'], check_hashes=True)
        if directory is None:
            raise ValueError('Pro cleanup model must already be verified in the supplied cache')
        weight = next(f['path'] for f in cleanup_model['files'] if f['path'].endswith('.gguf'))
        cleaner = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path=str(directory / weight),
            backend=args.backend), manager_factory=manager_factory)
        watchdog = threading.Timer(300, cleaner.close)
        watchdog.daemon = True
        watchdog.start()
        context = DictationContext()
        if stage('prepare_original_cleanup', lambda: cleaner.prepare_for_review(context)) is not True:
            raise RuntimeError('Initial cleanup prefix did not prepare')
        original, preparation = cleaner._manager, cleaner._preparation
        session = cleaner.command_session(command_config, choice.model_id)
        if session is None:
            raise RuntimeError('Command reservation refused')
        report['old_cleanup_closed'] = original.status['state'] == 'closed'
        report['old_preparation_closed'] = preparation.status['state'] == 'closed'
        report['normal_warm_refused'] = cleaner.warm() is False
        report['normal_clean_refused'] = cleaner.clean('Public fixture.')[1] == 'busy'
        if stage('prepare_command', session.prepare) != 'ready':
            raise RuntimeError('Command model did not prepare')
        command_manager = session._manager
        selected = []
        for kind in ('shorter', 'formal', 'bullets', 'spanish'):
            selected.append(next(case for case in load_cases() if case['kind'] == kind))
        for case in selected:
            started = time.perf_counter()
            reply = session.edit_selection(case['selection'], case['instruction'])
            report['rows'].append({'id': case['id'], 'reason': reply.reason, 'text': reply.text,
                'input_tokens': reply.input_tokens, 'output_limit': reply.output_limit,
                'stream_complete': reply.stream_complete, 'seconds': time.perf_counter() - started,
                'case_check': check_case(case, reply.text) if reply.text is not None else 'no_candidate'})
            print(json.dumps({k: report['rows'][-1][k] for k in ('id', 'reason', 'case_check')}), flush=True)
        session.close()
        report['command_closed'] = command_manager.status['state'] == 'closed'
        report['cleanup_lazy_after_command'] = cleaner._client is cleaner._preparation is None
        if stage('prepare_fresh_cleanup', lambda: cleaner.prepare_for_review(context)) is not True:
            raise RuntimeError('Fresh cleanup prefix did not prepare')
        report['fresh_cleanup_owner'] = cleaner._manager is not original and cleaner._manager is not command_manager
        report['fresh_cleanup_prefix'] = cleaner._preparation.status['state'] == 'prepared'
        report['restored_cleanup_model'] = cleaner.model_id
        session.close()
        report['old_session_cannot_close_successor'] = cleaner._manager.ready
    except BaseException as error:
        report['error_type'] = type(error).__name__
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if session is not None:
            session.close()
        if cleaner is not None:
            cleaner.close()
        report['native_exit_observed'] = meter.finish()
        report['source_unchanged'] = all(digest(ROOT / name) == value for name, value in fingerprints.items())
        report['pins_unchanged'] = all(resolve(identifier, check_hashes=True) is not None
                                       for identifier in tuple(report['verified']))
        report['passed'] = sum(row['reason'] == row['case_check'] == 'ok' for row in report['rows'])
        checks = ('old_cleanup_closed', 'old_preparation_closed', 'normal_warm_refused', 'normal_clean_refused',
                  'command_closed', 'cleanup_lazy_after_command', 'fresh_cleanup_owner', 'fresh_cleanup_prefix',
                  'old_session_cannot_close_successor', 'overlap_refused', 'source_unchanged', 'pins_unchanged')
        report['complete'] = (not report.get('error_type') and all(report.get(key) for key in checks)
            and len(report['rows']) == report['passed'] == 4 and len(processes) >= 3
            and all(report['native_exit_observed']) and len(report['native_exit_observed']) == len(processes))
        NetworkGuard.uninstall()
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'complete': report['complete'], 'passed': report['passed'],
                          'native_exits': report['native_exit_observed']}), flush=True)
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
