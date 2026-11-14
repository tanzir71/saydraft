"""Real browser selection -> actual Ask flow, restricted to disposable Windows CI.

The model and explicit Copy port are scripted. No audio, hook, OS input,
clipboard transaction or document insertion is allowed. Actual pinned-model
answers are measured by the separate cache-only tools.probe_ask runner.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace as NS
import uuid


def load_request(path):
    if (sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        raise RuntimeError('Browser Ask probe requires disposable GitHub-hosted Windows; owner desktop refused')
    temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    path = Path(path).absolute()
    if (path.resolve(strict=True) != path or path.parent.parent != temp
            or path.name != 'request.json' or path.is_symlink()):
        raise ValueError('Choose an owned request inside a fresh direct RUNNER_TEMP child')
    request = json.loads(path.read_text(encoding='utf-8'))
    if (set(request) != {'title', 'browser_pid', 'source'} or type(request['browser_pid']) is not int
            or not 0 < request['browser_pid'] < 2**32
            or type(request['title']) is not str or not request['title'].startswith('Saydraft read-only Ask ')
            or type(request['source']) is not str or not 0 < len(request['source']) < 8192):
        raise ValueError('Invalid owned browser request')
    return request


def run(path):
    request = load_request(path)  # Admission before any Qt, native UIA or foreground import.
    from PySide6 import QtCore, QtWidgets
    from saydraft.app import SaydraftApp, WorkerController, create_worker_signals
    from saydraft.cleanup.llm.ask import AskReply
    from saydraft.config import default_config
    from saydraft.context.foreground import ForegroundContextProvider, NativeForegroundApi
    from saydraft.context.uia_native import NativeUIAReader
    from saydraft.context.uia_worker import BoundedUIA
    from saydraft.core.container import Services
    from saydraft.core.processing import IdentityFormatter
    from saydraft.core.worker import SessionWorker
    from saydraft.data.notes import NoteStore
    from saydraft.history import DictationHistoryStore
    from saydraft.privacy.netguard import NetworkGuard

    output, worker, owner, app, executor = Path(path).parent, None, None, None, None
    report = {'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain']).strip()),
        'scope': __doc__, 'stages': [], 'native_reads': 0, 'native_metadata': [], 'model_calls': [], 'copies': [], 'complete': False}
    def source_hash(text):
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    report['expected_source_sha256'] = source_hash(request['source'])
    api, ready = NativeForegroundApi(), threading.Event()
    def owned_foreground():
        window = api.foreground()
        if not window or api.window_pid(window) != request['browser_pid']:
            raise RuntimeError('The fresh Chromium instance is not foreground')
        if request['title'] not in api.title(window, request['browser_pid']):
            raise RuntimeError('Fresh browser title changed')
        return window
    def factory():
        native = NativeUIAReader()
        client = native.client
        report['document_ancestors'] = []
        class Walker:
            def __init__(self, walker):
                self.walker = walker
            def GetParentElementBuildCache(self, element, cache):
                parent = self.walker.GetParentElementBuildCache(element, cache)
                if parent and len(report['document_ancestors']) < 32:
                    report['document_ancestors'].append({'type': native.control_type(parent),
                        'password': native.password(parent), 'native_handle': native.field_handle(parent)})
                return parent
        class Client:
            @property
            def RawViewWalker(self):
                return Walker(client.RawViewWalker)
            def __getattr__(self, name):
                return getattr(client, name)
        native.client = Client()  # Delegates unchanged calls, retaining cached ancestry metadata only.
        ranges_for = native._focused_selection
        report['native_range_queries'] = []
        def ranges(element):
            diagnostic = {'type': native.control_type(element)}
            try:
                value = ranges_for(element)
                diagnostic['count'] = value.Length
                return value
            except Exception as error:
                diagnostic.update(error_type=type(error).__name__, hresult=getattr(error, 'hresult', None))
                raise
            finally:
                if len(report['native_range_queries']) < 32:
                    report['native_range_queries'].append(diagnostic)
        native._focused_selection = ranges
        original = native.selection_text
        def read(*args):
            report['native_reads'] += 1
            return original(*args)
        native.selection_text = read
        focus = native.focused_element
        def element():
            value = focus()
            if len(report['native_metadata']) < 24:
                report['native_metadata'].append({'type': native.control_type(value), 'password': native.password(value),
                    'focused': native.keyboard_focus_snapshot(value)})
            return value
        native.focused_element = element  # Only diagnostics; no policy or focus overrides.
        ready.set()
        return native
    def forbidden(*args, **kwargs):
        raise AssertionError('Audio, ordinary processing, clipboard and insertion are forbidden in this probe')
    def settle(predicate, seconds=8):
        deadline = time.monotonic() + seconds
        while not predicate() and time.monotonic() < deadline:
            QtWidgets.QApplication.processEvents()
            time.sleep(.005)
        QtWidgets.QApplication.processEvents()
        assert predicate(), 'Owned Ask UI did not reach its expected state'
    NetworkGuard.install()
    try:
        report['browser_window'] = owned_foreground()
        qt = QtWidgets.QApplication([])
        assert qt.platformName() == 'offscreen'
        qt.setQuitOnLastWindowClosed(False)
        owner = BoundedUIA(factory=factory, capture_timeout=.5)
        assert ready.wait(5), 'Native UIA owner did not initialize'
        context = ForegroundContextProvider(api=api, uia=owner)
        capture = context.capture_selection
        report['native_captures'] = []
        def capture_selection(**options):
            value = capture(**options)
            report['native_captures'].append({'status': value.selection.status,
                'read_only': value.selection.read_only, 'control_type': value.selection.control_type,
                'source_sha256': source_hash(value.selection.text), 'allow_copy': options.get('allow_copy')})
            return value
        context.capture_selection = capture_selection
        config = default_config()
        config['app']['tier'], config['labs']['ask_mode'], config['command']['backend'] = 'pro', True, 'cpu'
        history = DictationHistoryStore(output / 'public-history.db')
        note_store = NoteStore(history.db_path)
        primary = note_store.save(uuid.uuid4().hex, 'Primary public note remains active')
        editor = NS(model_id='scripted-no-native-model', closed=False, prepare=lambda **kwargs: 'ready')
        answer = 'The library opens on Saturday at 10:00.'
        def ask(source, question, **kwargs):
            assert source == request['source'] and question == 'When does the library open?'
            report['model_calls'].append({'source_sha256': source_hash(source), 'question': question})
            return AskReply(answer, 'ok', 200, 768, True)
        editor.ask_about, editor.close = ask, lambda: setattr(editor, 'closed', True)
        cleaner = NS(llm=NS(command_session=lambda *args: editor), close=lambda: None)
        signals = create_worker_signals(QtCore)
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Saydraft-browser-Ask')
        services = Services(config, NS(start=forbidden, stop=forbidden), NS(transcribe=forbidden), cleaner,
            IdentityFormatter(), NS(insert=forbidden), context, history, NS(process=forbidden, pending_results=[]), [])
        worker = SessionWorker(services, emit=lambda name, *args: getattr(signals, name).emit(*args), executor=executor)
        worker.ask.config_resolver = lambda *args, **kwargs: object()  # Explicit scripted model, no download or cache scan.
        worker.ask.report_loader = lambda: None
        app = SaydraftApp(argv=[])
        app.qt_app, app.controller = qt, WorkerController.__new__(WorkerController)
        app.controller.core = worker
        app.history_window = NS(clipboard=NS(setText=report['copies'].append))
        app.hub_window = NS(notes_page=NS(store=note_store, refresh=lambda: None))
        app._ensure_hub = forbidden
        def present_answer(value):
            row = history.get_row(value.result.history_id)
            assert row is not None and row.cleaned_text == value.result.text
            report['history_before_presentation'] = True
            app._ask_answer_requested(value)
        for name, callback in (('ask_review_requested', app._ask_review_requested), ('ask_retired', app._ask_retired),
                ('ask_status_changed', app._ask_status_changed), ('ask_answer_requested', present_answer)):
            getattr(signals, name).connect(callback, QtCore.Qt.QueuedConnection)
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='Saydraft-browser-action') as action:
            assert action.submit(worker.ask.request, lambda: True).result(timeout=5)
        settle(lambda: app.ask_window is not None and app.ask_window.isVisible() and not worker.busy)
        assert app.ask_window.source_editor.isReadOnly() and app.ask_window.source.text == request['source']
        report['stages'].append('native-read-only-article-reviewed')
        captured_reads = report['native_reads']
        assert captured_reads >= 2
        app.ask_window.question.setPlainText('When does the library open?')
        app.ask_window.ask_button.click()
        settle(lambda: app.ask_answers is not None and bool(app.ask_answers.windows) and not worker.busy)
        result = app.ask_answers.windows[0]
        settle(lambda: not result.draft.snapshot().dirty and not result.draft.snapshot().saving)
        rows = history.list_recent()
        assert len(rows) == 1 and rows[0].mode == 'ask' and rows[0].cleaned_text == answer
        assert result.editor.toPlainText() == answer and note_store.active() == primary and len(note_store.list()) == 2
        assert history.last_transcript() is None and not report['copies'] and editor.closed
        assert report['native_reads'] == captured_reads  # Frozen source; no browser re-read after review presentation.
        result.copy_button.click()
        assert report['copies'] == [answer]
        report['stages'].append('history-and-independent-answer-note-before-explicit-memory-copy')
        for name, widget in (('question.png', app.ask_window), ('answer.png', result)):
            assert widget.grab().save(str(output / name))
        report['complete'] = True
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        if app is not None:
            if app.ask_window is not None:
                app.ask_window.retire()
            if app.ask_answers is not None:
                for window in app.ask_answers.windows:
                    window.shutdown()
                    window.draft.executor.shutdown(wait=True)
        if worker is not None:
            worker.shutdown()
        if executor is not None:
            executor.shutdown(wait=True)
        if owner is not None:
            owner.close()
            report['uia_closed'] = owner.wait_closed(2)
        else:
            report['uia_closed'] = False
        report['no_audio_module_loaded'] = 'sounddevice' not in sys.modules
        report['complete'] &= report['uia_closed'] and report['no_audio_module_loaded']
        NetworkGuard.uninstall()
        (output / 'native-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if report['complete'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.request)


if __name__ == '__main__':
    raise SystemExit(main())
