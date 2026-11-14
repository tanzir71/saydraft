"""Held gesture -> instruction ASR -> real SQLite -> guarded memory paste.

All input/audio/selection/model transports are explicit fakes. No owner desktop,
clipboard, audio devices, network or native keyboard hooks are accessed.
"""

from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.edit import EditReply
from saydraft.cleanup.llm.sidecar import SidecarConfig
from saydraft.context.foreground import SelectedContext
from saydraft.context.selection import SelectionSnapshot
from saydraft.core.interfaces import TargetContext
from saydraft.core.session import SessionState as State
from saydraft.history import DictationHistoryStore
from saydraft.insert.inserter import Inserter
from tests.test_hotkeys import FakeKeyboard as GestureKeyboard
from tests.test_inserter import FakeClipboard, FakeKeyboard
from tests.test_session_worker import make_worker


def fixture(tmp_path, *, tier='pro', enabled=True):
    w, clock, executor, events, signals, _ = make_worker(queued=True)
    config = w.services.config
    config['app']['tier'] = tier
    config['labs'].update(command_mode=enabled, live_preview=True, use_streaming_result=True)
    config['dictation']['voice_enter_enabled'] = True
    config['llm']['enabled'] = False
    target = TargetContext(15, 'Owned fixture', app_exe='fixture.exe', app_group='docs')
    captured = SelectedContext(target, SelectionSnapshot(status='ready', text='I wanted to say the file arrived.'))
    calls, bars, lease_cancels = [], [], []
    reason, confirmation = [''], ['']
    def capture(**kwargs):
        calls.append('selection')
        return captured
    def verify(value, **kwargs):
        assert value is captured
        calls.append('verify')
        return reason[0]
    context = SimpleNamespace(capture=lambda: target, capture_selection=capture, verify_selection=verify,
        confirm_replacement=lambda *a: confirmation[0], cancel_selection=lease_cancels.append)
    w.services.context = context
    history = DictationHistoryStore(tmp_path / 'history.db')
    w.services.history = history
    clipboard, keyboard = FakeClipboard(), FakeKeyboard()
    def send(key):
        assert history.list_recent()[0].mode == 'command'
        calls.append(('send', key))
    keyboard.send = send
    w.services.inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 15, sleep=lambda _: None)
    instruction = ['Make shorter.']
    w.services.asr = SimpleNamespace(transcribe=lambda audio: calls.append('asr') or instruction[0],
        prepare=lambda: calls.append('speech_prepare'), model_id='fixture-asr', last_language='en', last_timings={'stt': .1})
    editors = []
    reply = [EditReply('The file arrived.', 'ok', 200, 768, True)]
    def create(model_config, model_id):
        assert w.services.recorder.stopped >= w.services.recorder.started
        calls.append('command_owner')
        editor = SimpleNamespace(model_id=model_id, closed=False)
        def prepare(**kwargs):
            calls.append('edit_prepare')
            return 'cancelled' if kwargs['cancelled']() else 'ready'
        def edit(selection, command, **kwargs):
            calls.append(('edit', selection, command))
            assert selection == captured.selection.text and command == instruction[0]
            return reply[0]
        def close():
            editor.closed = True
        editor.prepare, editor.edit_selection, editor.close = prepare, edit, close
        editors.append(editor)
        return editor
    w.services.cleaner.llm = SimpleNamespace(command_session=create)
    w.services.processor.process = lambda *a, **kw: pytest.fail('Instruction passed through ordinary dictation')
    def resolve(choice, **kwargs):
        calls.append('resolve')
        return SidecarConfig(tmp_path / 'public-fixture.gguf')
    w.command.config_resolver = resolve
    w.command.report_loader = lambda: pytest.fail('Manual tier must not discover hardware')
    w.bar_status.callback = bars.append
    gestures = GestureKeyboard()
    w.hotkeys.keyboard = gestures
    w.hotkeys.configure(config)
    w.hotkeys._controller.clock = lambda: clock.now
    w.hotkeys.start()
    return SimpleNamespace(w=w, clock=clock, executor=executor, calls=calls, signals=signals, bars=bars,
        gestures=gestures, history=history, clipboard=clipboard, keyboard=keyboard, captured=captured,
        editors=editors, reason=reason, confirmation=confirmation, reply=reply, instruction=instruction,
        lease_cancels=lease_cancels)


def record(f):
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    assert f.w.session.state == State.LISTENING
    f.clock.now += 1
    f.gestures.release('ctrl+win+alt')
    f.executor.drain()


def test_full_held_flow_persists_before_paste_without_dictation_cleanup_preview_snippets_or_enter(tmp_path):
    f = fixture(tmp_path)
    record(f)
    assert f.w.session.state == State.DONE and not f.w.busy and f.w.command.active is None
    row = f.history.list_recent()[0]
    assert row.raw_text == f.captured.selection.text and row.cleaned_text == 'The file arrived.'
    assert row.asr_model == 'fixture-asr' and row.llm_model == 'qwen35-4b-q4-k-m'
    assert row.duration_seconds == 1 and row.language == 'en' and 'Make shorter.' in row.edits_json
    edit = ('edit', f.captured.selection.text, 'Make shorter.')
    assert f.calls.index('resolve') < f.calls.index('edit_prepare') < f.calls.index('speech_prepare')
    assert f.calls.index('speech_prepare') < f.calls.index('asr') < f.calls.index(edit) < f.calls.index(('send', 'ctrl+v'))
    assert f.calls.count(('send', 'ctrl+v')) == 1
    assert f.clipboard.value == 'original' and f.editors[0].closed and not f.w._background and not f.w._preview
    assert any(b.reason == 'command' and b.phase == 'listening' for b in f.bars)
    assert f.w.last_result is None and f.w.last_command_result.reason == 'ok'
    assert f.history.weekly_stats().dictations == 0 and f.history.last_transcript() is None


def test_legitimate_normal_prefix_is_cancelled_and_its_capture_finishes_before_command_arms(tmp_path):
    f = fixture(tmp_path)
    f.gestures.press('ctrl+win')
    f.executor.drain()
    assert f.w.services.recorder.started == 1
    f.gestures.press('ctrl+win+alt')
    assert f.w.session.state == State.CANCELLED and f.w.command.pending is not None
    assert f.w.services.recorder.started == 1 and not f.editors
    f.executor.drain()
    assert f.w.services.recorder.stopped == 1 and f.w.services.recorder.started == 2
    assert f.w.session.session_id == 2 and not f.history.list_recent()
    f.clock.now += 1
    f.gestures.release('ctrl+win+alt')
    f.executor.drain()
    assert f.w.session.state == State.DONE and len(f.history.list_recent()) == 1


@pytest.mark.parametrize('tier,enabled,message', [('standard', True, 'Needs Pro tier'), ('pro', False, 'Enable experimental')])
def test_admission_happens_before_command_context_cache_or_audio_access(tmp_path, tier, enabled, message):
    f = fixture(tmp_path, tier=tier, enabled=enabled)
    assert not f.w.command.start(lambda: True, lambda _: True)
    assert not f.calls and not f.editors and f.w.services.recorder.started == 0 and not f.history.list_recent()
    assert any(s[0] == 'notification_requested' and message in s[1] for s in f.signals)


def test_pending_release_never_opens_model_or_microphone_or_creates_a_session(tmp_path):
    f = fixture(tmp_path)
    f.gestures.press('ctrl+win+alt')
    assert f.w.command.pending is not None
    f.gestures.release('ctrl+win+alt')
    f.executor.drain()
    assert f.w.services.recorder.started == 0 and not f.editors and f.w.session.session_id == 0
    assert not f.w.busy and f.calls == ['selection', 'verify'] and f.lease_cancels


def test_release_during_model_preparation_retires_late_readiness_before_any_more_target_or_audio_access(tmp_path):
    f = fixture(tmp_path)
    factory = f.w.services.cleaner.llm.command_session
    def create(*args):
        editor = factory(*args)
        def prepare(**kwargs):
            f.gestures.release('ctrl+win+alt')
            assert kwargs['cancelled']()
            return 'ready'  # A deliberately late result cannot open the mic.
        editor.prepare = prepare
        return editor
    f.w.services.cleaner.llm.command_session = create
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    assert f.w.services.recorder.started == 0 and f.editors[0].closed and not f.w.busy
    assert f.calls.count('verify') == 1 and 'speech_prepare' not in f.calls and not f.history.list_recent()


def test_missing_installed_command_model_requires_explicit_setup_before_audio(tmp_path):
    f = fixture(tmp_path)
    f.w.command.config_resolver = lambda *a, **kw: None
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    assert f.w.services.recorder.started == 0 and not f.editors and not f.history.list_recent()
    assert any(s[0] == 'notification_requested' and 'Download or resume' in s[1] for s in f.signals)


@pytest.mark.parametrize('when', ['asr', 'edit'])
def test_cancel_during_recognition_or_edit_discards_late_instruction_result_and_input(tmp_path, when):
    f = fixture(tmp_path)
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    if when == 'asr':
        f.w.services.asr.transcribe = lambda audio: f.w.cancel() or 'Make shorter.'
    else:
        f.editors[0].edit_selection = lambda *a, **kw: f.w.cancel() or f.reply[0]
    f.clock.now += 1
    f.gestures.release('ctrl+win+alt')
    f.executor.drain()
    assert not f.history.list_recent() and not f.clipboard.ops and not f.w.busy
    assert not any(s[0] == 'command_recovery_requested' for s in f.signals)
    assert f.editors[0].closed


@pytest.mark.parametrize('reason', ['unavailable', 'context_limit', 'incomplete'])
def test_failed_generation_keeps_the_spoken_instruction_in_history_without_document_or_input(tmp_path, reason):
    f = fixture(tmp_path)
    f.reply[0] = EditReply(None, reason)
    record(f)
    row = f.history.list_recent()[0]
    assert row.raw_text == 'Make shorter.' and not row.cleaned_text
    assert row.llm_decision == 'edit_failed:' + reason and row.asr_model == 'fixture-asr'
    assert not f.clipboard.ops and not any(isinstance(c, tuple) and c[0] == 'send' for c in f.calls)
    assert f.w.session.state == State.NOT_INSERTED and f.editors[0].closed


def test_unconfirmed_delivery_queues_a_current_independent_recovery_and_never_retries(tmp_path):
    f = fixture(tmp_path)
    f.confirmation[0] = 'field_unavailable'
    record(f)
    requests = [s[1] for s in f.signals if s[0] == 'command_recovery_requested']
    assert len(requests) == 1 and requests[0].result.reason == 'insertion_unconfirmed'
    assert f.w.is_current_command_request(requests[0])
    assert f.calls.count(('send', 'ctrl+v')) == 1 and f.clipboard.value == 'original'
    assert f.w.session.state == State.NOT_INSERTED


def test_history_failure_after_failed_generation_recovers_only_labelled_instruction_words(tmp_path):
    f = fixture(tmp_path)
    f.reply[0] = EditReply(None, 'unavailable')
    def failed(entry):
        raise OSError('owned fixture storage failure')
    f.history.append = failed
    record(f)
    request = next(s[1] for s in f.signals if s[0] == 'command_recovery_requested')
    assert request.result.text == 'Make shorter.' and request.result.reason == 'instruction_history_unavailable'
    assert f.w.is_current_command_request(request) and not f.clipboard.ops


def test_cancellation_after_a_durable_write_keeps_that_row_and_cannot_send_paste_or_recovery(tmp_path):
    f = fixture(tmp_path)
    append = f.history.append
    def saved(entry):
        identifier = append(entry)
        f.w.cancel()
        return identifier
    f.history.append = saved
    record(f)
    assert len(f.history.list_recent()) == 1 and not f.clipboard.ops
    assert not any(s[0] == 'command_recovery_requested' for s in f.signals) and not f.w.busy


@pytest.mark.parametrize('when', ['pending', 'listening'])
def test_settings_can_defer_without_leaving_a_command_session_or_busy_reservation_stuck(tmp_path, when):
    from copy import deepcopy
    from dataclasses import replace
    f = fixture(tmp_path)
    f.gestures.press('ctrl+win+alt')
    if when == 'listening':
        f.executor.drain()
    config = deepcopy(f.w.services.config)
    config['app']['end_sound'] = True
    replacement = replace(f.w.services, config=config)
    f.w.services_factory = lambda *a, **kw: replacement
    f.w.configure(config)
    if when == 'listening':
        assert f.w.services is not replacement
        f.clock.now += 1
        f.gestures.release('ctrl+win+alt')
    f.executor.drain()
    assert f.w.services is replacement and not f.w.busy and f.w._pending_config is None
    assert f.w.services.recorder.started == (1 if when == 'listening' else 0)


def test_worker_cancel_also_retires_an_unacknowledged_controller_gesture(tmp_path):
    f = fixture(tmp_path)
    f.gestures.press('ctrl+win+alt')
    f.w.cancel()
    f.executor.drain()
    assert not f.w.hotkeys._controller.is_recording and not f.w.busy
    assert f.w.services.recorder.started == 0 and not f.history.list_recent()


@pytest.mark.parametrize('reason', ['password_field', 'selection_changed'])
def test_initial_native_guard_failure_does_not_prepare_a_command_model_or_microphone(tmp_path, reason):
    f = fixture(tmp_path)
    f.reason[0] = reason
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    assert not f.editors and 'resolve' not in f.calls and f.w.services.recorder.started == 0
    assert not f.w.busy and not f.history.list_recent()


def test_readable_read_only_selection_produces_a_copy_result_without_any_clipboard_or_key_input(tmp_path):
    f = fixture(tmp_path)
    f.w.services.context.verify_selection = lambda value, *, for_write=True: 'read_only' if for_write else ''
    record(f)
    row = f.history.list_recent()[0]
    request = next(s[1] for s in f.signals if s[0] == 'command_recovery_requested')
    assert row.cleaned_text == request.result.text == 'The file arrived.' and request.result.reason == 'read_only'
    assert f.w.is_current_command_request(request) and not f.clipboard.ops
    assert not any(isinstance(call, tuple) and call[0] == 'send' for call in f.calls)


def test_changed_target_after_model_preparation_refuses_audio_and_does_not_redirect(tmp_path):
    f = fixture(tmp_path)
    factory = f.w.services.cleaner.llm.command_session
    def create(*args):
        editor = factory(*args)
        editor.prepare = lambda **kwargs: f.reason.__setitem__(0, 'focus_changed') or 'ready'
        return editor
    f.w.services.cleaner.llm.command_session = create
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    assert f.w.services.recorder.started == 0 and not f.w.busy and f.editors[0].closed
    assert not f.history.list_recent() and 'asr' not in f.calls


def test_retention_failure_does_not_discard_the_instruction_or_block_successful_editing(tmp_path):
    f = fixture(tmp_path)
    f.w.services.config['recording']['retain_audio'] = True
    def failed(*args):
        raise OSError('owned fixture disk failure')
    f.w.services.audio_store = SimpleNamespace(save=failed)
    record(f)
    assert f.w.last_command_result.reason == 'ok' and len(f.history.list_recent()) == 1
    assert any(s[0] == 'notification_requested' and 'recognition will continue' in s[1] for s in f.signals)


def test_saved_command_audio_never_enters_the_ordinary_dictation_retry_route(tmp_path):
    f = fixture(tmp_path)
    f.w.services.config['recording']['retain_audio'] = True
    f.w.services.audio_store = SimpleNamespace(save=lambda *a: tmp_path / 'public-instruction.wav')
    f.w.services.retry_asr = object()
    record(f)
    row = f.history.list_recent()[0]
    assert row.audio_path and row.mode == 'command'
    assert not f.w.retry_history(row) and not f.executor.jobs


def test_empty_recognition_indexes_retained_command_audio_without_paste_or_dictation_stats(tmp_path):
    f = fixture(tmp_path)
    f.w.services.config['recording']['retain_audio'] = True
    f.w.services.audio_store = SimpleNamespace(save=lambda *a: tmp_path / 'public-empty.wav')
    f.instruction[0] = ''
    record(f)
    row = f.history.list_recent()[0]
    assert row.audio_path and row.mode == 'command' and not row.raw_text and not row.cleaned_text
    assert 'asr_empty' in row.edits_json and not f.clipboard.ops
    assert f.w.session.state == State.CANCELLED and not f.w.busy and f.history.weekly_stats().dictations == 0
