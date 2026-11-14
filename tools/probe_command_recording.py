"""Synthetic held chords through the actual worker and an owned invisible EDIT.

Actual UIA ranges, SQLite and bounded own-control messages. Instruction audio,
ASR, edit model, native key transport and clipboard are explicit fixture ports.
No owner foreground, OS keys, clipboard, audio devices or playback are used.
"""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np

from saydraft.cleanup.llm.edit import EditReply
from saydraft.cleanup.llm.sidecar import SidecarConfig
from saydraft.config import default_config
from saydraft.core.container import Services
from saydraft.core.processing import IdentityFormatter
from saydraft.core.session import DictationSession, SessionState as State
from saydraft.core.worker import SessionWorker
from saydraft.history import DictationHistoryStore
from saydraft.hotkeys.chords import ChordMatcher
from saydraft.insert.inserter import Inserter
from tools.probe_selection import main as selection_main


class FixtureTimer:
    def __init__(self, seconds, callback):
        self.seconds, self.callback, self.daemon = seconds, callback, False
    def start(self):
        pass
    def cancel(self):
        pass


class FixtureHooks:
    def __init__(self, bindings, *, on_action, on_failure):
        self.matcher, self.action = ChordMatcher(bindings), on_action
        self.status, self.completion_thread = {'state': 'idle'}, None
    def start(self):
        self.status['state'] = 'running'
    def close(self):
        self.status['state'] = 'stopped'
        return True
    def post_action(self, callback):
        callback()
        return True
    def feed(self, key, down, when):
        for transition in self.matcher.feed(key, down).transitions:
            self.action(transition, when)


def exercise(fixture, report, *, modes=('prefix_replace', 'ignored_paste', 'read_only_copy', 'failed_edit', 'release_during_prepare')):
    context, output = fixture.context, fixture.output
    report['command_scope'] = ('compiled synthetic chords -> actual session worker -> scripted instruction ASR/edit '
        '-> actual SQLite and UIA target -> bounded own-EDIT message and confirmation; memory clipboard only')
    report['asr_performed'] = report['native_edit_model_used'] = False
    for mode in modes:
        fallback = mode.startswith('fallback_')
        fixture.set_selection_supported(not fallback)
        fixture.set_password(False)
        reads_before = report['reads']
        original, replacement = 'I wanted to say the parcel arrived.', 'The parcel arrived.'
        prefix, suffix = 'Own prefix ', ' own suffix'
        fixture.set_text(prefix + original + suffix, len(prefix), len(prefix + original))
        fixture.set_read_only(mode == 'read_only_copy')
        clock = SimpleNamespace(now=0.)
        recorder = SimpleNamespace(started=0, stopped=0)
        def start():
            recorder.started += 1
        def stop():
            recorder.stopped += 1
            return np.ones(16000, dtype=np.float32)
        recorder.start, recorder.stop = start, stop
        config = default_config()
        config['app']['tier'] = 'pro'
        config['labs']['command_mode'] = True
        config['command']['clipboard_fallback'] = fallback
        config['dictation']['voice_enter_enabled'] = True
        config['llm']['enabled'] = False
        store = DictationHistoryStore(output / (mode + '.db'))
        memory, sent, signals, owners, editors = ['Before Command'], [], [], [], []
        clipboard = SimpleNamespace(paste=lambda: memory[0], copy=lambda text: memory.__setitem__(0, text))
        def capture_copy(**options):
            # Deliberately scripted clipboard port, not the native transaction
            # probe. Native field identity/password and MTA sealing are real.
            before = memory[0]
            reason, text = options['guard'](), ''
            try:
                if not reason:
                    options['send_copy']()
                    if mode == 'fallback_cancel':
                        worker.cancel()
                    reason = options['guard']() if options['current']() else 'cancelled'
                    if not reason:
                        text = memory[0]
            finally:
                memory[0] = before
            return SimpleNamespace(text=text, reason=reason or 'ok', restore_status='restored')
        clipboard.capture_selection = capture_copy
        def send(key):
            if key == 'ctrl+c':
                assert fallback and not store.list_recent()
                sent.append(key)
                memory[0] = original
                return
            assert key == 'ctrl+v' and store.list_recent()[0].raw_text == original
            sent.append(key)
            if mode == 'prefix_replace':
                fixture.replace_text(memory[0])
        def no_typing(text):
            raise AssertionError('Command must never type a fallback')
        inserter = Inserter(clipboard=clipboard, keyboard=SimpleNamespace(send=send, write=no_typing),
                            focus_provider=context.focus, sleep=lambda _: None,
                            delivery_guard=(lambda _: '') if fallback else None)
        port = SimpleNamespace(**{name: getattr(context, name) for name in (
            'capture', 'capture_selection', 'verify_selection', 'seal_copy', 'confirm_replacement', 'cancel_selection', 'focus', 'prepare')},
            close=lambda: None)  # The outer owned fixture retires the one shared MTA.
        def editor_factory(model_config, model_id):
            assert recorder.stopped >= recorder.started
            editor = SimpleNamespace(model_id='fixture-no-llm', closed=False)
            def prepare(**kwargs):
                if mode == 'release_during_prepare':
                    owners[0].feed('left_alt', False, clock.now)
                return 'ready'  # Includes a deliberately late readiness result.
            def edit(*args, **kwargs):
                return EditReply(None, 'unavailable') if mode == 'failed_edit' else EditReply(replacement, 'ok')
            editor.prepare, editor.edit_selection = prepare, edit
            editor.close = lambda: setattr(editor, 'closed', True)
            editors.append(editor)
            return editor
        cleaner = SimpleNamespace(llm=SimpleNamespace(command_session=editor_factory), warm=lambda: False, close=lambda: None)
        def no_dictation(*args, **kwargs):
            raise AssertionError('Instruction cannot enter ordinary dictation processing')
        processor = SimpleNamespace(process=no_dictation, pending_results=[])
        asr = SimpleNamespace(transcribe=lambda audio: 'Make shorter.', model_id='fixture-no-asr',
                              last_language='en', last_timings={'stt': 0.})
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Saydraft-own-command')
        worker = SessionWorker(Services(config, recorder, asr, cleaner, IdentityFormatter(), inserter,
            port, store, processor, []), executor=executor, session=DictationSession(clock=lambda: clock.now),
            emit=lambda *args: signals.append(args), timer_factory=FixtureTimer)
        worker.command.config_resolver = lambda *a, **kw: SidecarConfig((output / 'not-a-real-model.gguf').resolve())
        worker.command.report_loader = lambda: None
        def native_factory(*args, **kwargs):
            owner = FixtureHooks(*args, **kwargs)
            owners.append(owner)
            return owner
        worker.hotkeys.native_factory = native_factory
        worker.hotkeys.configure(config)
        worker.hotkeys._controller.clock = lambda: clock.now
        def press(keys):
            for key in keys:
                owners[0].feed(key, True, clock.now)
        try:
            fixture.call(worker.hotkeys.start)
            if mode == 'prefix_replace':
                fixture.call(lambda: press(('left_ctrl', 'left_win')))
                fixture.pump_until(lambda: worker.session.state == State.LISTENING and worker._inflight == 0, 5)
                assert recorder.started == 1
                fixture.call(lambda: press(('left_alt',)))
            else:
                fixture.call(lambda: press(('left_ctrl', 'left_alt', 'left_win')))
            if mode == 'release_during_prepare':
                fixture.pump_until(lambda: not worker.busy, 5)
                assert recorder.started == 0 and not sent and not store.list_recent()
            else:
                fixture.pump_until(lambda: worker.session.state == State.LISTENING and worker._inflight == 0, 5)
                if mode == 'fallback_sensitive':
                    fixture.set_password(True)
                clock.now = 1.
                fixture.call(lambda: owners[0].feed('left_alt', False, clock.now))
                fixture.pump_until(lambda: not worker.busy, 5)
                rows = store.list_recent()
                assert len(rows) == (0 if mode == 'fallback_cancel' else 1)
                assert all(row.mode == 'command' for row in rows) and store.weekly_stats().dictations == 0
                assert store.last_transcript() is None
                if mode == 'fallback_cancel':
                    assert sent == ['ctrl+c'] and not any(s[0] == 'command_recovery_requested' for s in signals)
                elif mode in ('failed_edit', 'fallback_sensitive'):
                    assert rows[0].raw_text == 'Make shorter.' and not rows[0].cleaned_text and not sent
                elif mode in ('read_only_copy', 'fallback_copy'):
                    assert rows[0].cleaned_text == replacement and sent == (['ctrl+c'] if fallback else [])
                else:
                    assert sent == ['ctrl+v'] and rows[0].cleaned_text == replacement
                    assert 'Make shorter.' in rows[0].edits_json
            expected_text = prefix + (replacement if mode == 'prefix_replace' else original) + suffix
            assert fixture.field_text() == expected_text and memory[0] == 'Before Command'
            requests = [s[1] for s in signals if s[0] == 'command_recovery_requested']
            assert len(requests) == (1 if mode in ('ignored_paste', 'read_only_copy', 'fallback_copy') else 0)
            assert all(worker.is_current_command_request(request) for request in requests)
            assert all(editor.closed for editor in editors)
            report['cases'].append({'case': 'held_command_worker', 'mode': mode,
                'outcome': worker.last_command_result.reason if worker.last_command_result else
                    'cancelled_during_copy' if mode == 'fallback_cancel' else 'released_before_capture',
                'capture_starts': recorder.started, 'capture_stops': recorder.stopped,
                'fixture_direct_message_writes': len(sent) if mode == 'prefix_replace' else 0,
                'paste_attempts': sent.count('ctrl+v'), 'copy_attempts': sent.count('ctrl+c'),
                'recovery_requests': len(requests), 'memory_clipboard_restored': True,
                'own_field_exact': True, 'history_rows': len(store.list_recent()), 'all_editors_retired': True,
                'history_before_input': bool(sent.count('ctrl+v')), 'ordinary_processor_called': False,
                'selection_pattern_suppressed': fallback, 'selection_text_reads': report['reads'] - reads_before,
                'prefix_retired_before_command_owner': True, 'scripted_asr_and_model': True, 'serial_closed': False})
        finally:
            fixture.call(worker.shutdown)
            executor.shutdown(wait=True)
            assert not any(thread.is_alive() for thread in executor._threads)
            assert owners[0].status['state'] == 'stopped'
            if report['cases'][-1].get('mode') == mode:
                report['cases'][-1]['serial_closed'] = True
            fixture.set_selection_supported(True)
            fixture.set_password(False)


def main(argv=None):
    return selection_main(argv, exercise=exercise)


if __name__ == '__main__':
    raise SystemExit(main())
