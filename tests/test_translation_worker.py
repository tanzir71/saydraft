"""Normal held speech -> separate translation owner -> durable history -> guarded memory paste."""

from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace as NS

import pytest

from saydraft.cleanup.llm.edit import EditReply
from saydraft.cleanup.llm.sidecar import SidecarConfig
from saydraft.core.interfaces import TargetContext
from saydraft.core.session import SessionState as State
from saydraft.history import DictationHistoryStore
from saydraft.insert.inserter import Inserter
from tests.test_hotkeys import FakeKeyboard as Gestures
from tests.test_inserter import FakeClipboard, FakeKeyboard
from tests.test_session_worker import make_worker


@pytest.fixture
def fixture(tmp_path):
    w, clock, executor, events, signals, _ = make_worker(queued=True)
    cfg = w.services.config
    cfg['app']['tier'] = 'pro'
    cfg['labs'].update(translate_mode=True, live_preview=True, use_streaming_result=True)
    cfg['translation']['targets'] = {'general': 'es'}
    cfg['command']['backend'] = 'cpu'
    cfg['dictation'].update(voice_enter_enabled=True, learn_corrections=True)
    target = TargetContext(15, 'Owned fixture', app_group='general', before_caret='PRIVATE FIELD WORDS',
                           selection='DO NOT TRANSLATE THIS SELECTION')
    w.services.context = NS(capture=lambda: target, verify=lambda _: '')
    history = w.services.history = DictationHistoryStore(tmp_path / 'history.db')
    clipboard, keyboard, calls, editors = FakeClipboard(), FakeKeyboard(), [], []
    def send(key):
        assert key == 'ctrl+v' and history.list_recent()[0].mode == 'translate'
        calls.append(('send', key))
    keyboard.send = send
    w.services.inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 15, sleep=lambda _: None)
    source, reply = ['The file is ready.'], [EditReply('El archivo está listo.', 'ok', stream_complete=True)]
    w.services.asr = NS(prepare=lambda: calls.append('speech_prepare'),
        transcribe=lambda audio: calls.append('asr') or source[0], model_id='fixture-asr',
        last_language='en', last_timings={'stt': .1})
    def factory(*args):
        assert w.services.recorder.started == w.services.recorder.stopped
        editor = NS(closed=False)
        editor.prepare = lambda **kw: calls.append('translate_prepare') or 'ready'
        def edit(text, instruction, **kw):
            assert text == source[0] and 'PRIVATE' not in text and 'SELECTION' not in text
            assert instruction.startswith('Translate to Spanish.')
            calls.append('translate')
            return reply[0]
        editor.edit_selection, editor.close = edit, lambda: setattr(editor, 'closed', True)
        editors.append(editor)
        return editor
    w.services.cleaner.llm = NS(command_session=factory)
    original = w.services.processor.process
    def ordinary(*args, **kwargs):
        calls.append('ordinary_cleanup')
        return original(*args, **kwargs)
    w.services.processor.process = ordinary
    w.translation.resolver = lambda *a, **kw: SidecarConfig(tmp_path / 'fixture.gguf')
    w.translation.report_loader = lambda: pytest.fail('Manual Pro must not discover hardware')
    gestures = Gestures()
    w.hotkeys.keyboard = gestures
    w.hotkeys.configure(cfg)
    w.hotkeys._controller.clock = lambda: clock.now
    w.hotkeys.start()
    f = NS(w=w, clock=clock, executor=executor, signals=signals, calls=calls, editors=editors,
           history=history, clipboard=clipboard, source=source, reply=reply, gestures=gestures)
    try:
        yield f
    finally:
        w.shutdown()


def record(f):
    f.gestures.press('ctrl+win')
    f.executor.drain()
    assert f.w.session.state == State.LISTENING
    f.clock.now += 1
    f.gestures.release('ctrl+win')
    f.executor.drain()


def test_normal_shortcut_translates_recognized_speech_only_and_persists_before_one_paste(fixture):
    f = fixture
    record(f)
    assert f.w.session.state == State.DONE and not f.w.busy and f.w.translation.active is None
    row = f.history.list_recent()[0]
    assert row.mode == 'translate' and row.raw_text == f.source[0] and row.cleaned_text == f.reply[0].text
    assert row.asr_model == 'fixture-asr' and row.language == 'en' and row.llm_model == 'qwen35-4b-q4-k-m'
    assert json.loads(row.edits_json)[0]['target_language'] == 'es'
    assert f.calls == ['translate_prepare', 'speech_prepare', 'asr', 'translate', ('send', 'ctrl+v')]
    assert f.clipboard.value == 'original' and all(e.closed for e in f.editors)
    assert f.history.last_transcript() == row.cleaned_text
    assert not f.w._background and not f.w._preview


def test_standard_refuses_before_model_or_microphone(fixture):
    f = fixture
    f.w.services.config['app']['tier'] = 'standard'
    assert not f.w.start_recording()
    assert not f.calls and not f.editors and f.w.services.recorder.started == 0
    assert any(s[0] == 'notification_requested' and 'Needs Pro' in s[1] for s in f.signals)


def test_missing_model_never_downloads_or_opens_microphone(fixture):
    f = fixture
    f.w.translation.resolver = lambda *a, **kw: None
    assert f.w.start_recording()
    f.executor.drain()
    assert f.w.session.state == State.ERROR and not f.calls and not f.editors
    assert f.w.services.recorder.started == 0 and f.w.translation.active is None


def test_release_during_model_preparation_prevents_a_late_microphone(fixture):
    f = fixture
    factory = f.w.services.cleaner.llm.command_session
    def create(*args):
        editor = factory(*args)
        editor.prepare = lambda **kw: f.w.stop_recording() or 'ready'
        return editor
    f.w.services.cleaner.llm.command_session = create
    f.w.start_recording()
    f.executor.drain()
    assert f.w.services.recorder.started == 0 and not f.history.list_recent()
    assert f.w.translation.active is None and all(e.closed for e in f.editors)


def test_invalid_translation_keeps_raw_speech_in_history_and_copy_recovery_without_paste(fixture):
    f = fixture
    f.reply[0] = EditReply('The file is ready.', 'ok', stream_complete=True)
    record(f)
    row = f.history.list_recent()[0]
    assert row.mode == 'translation_failed' and row.raw_text == row.cleaned_text == f.source[0]
    assert row.llm_decision == 'translation_not_translated' and not f.clipboard.ops
    assert f.history.last_transcript() is None
    request = next(s[1] for s in f.signals if s[0] == 'command_recovery_requested')
    assert request.result.task == 'translation_raw' and request.result.text == f.source[0]


def test_history_failure_preserves_both_versions_without_paste(fixture):
    f = fixture
    def failed(entry):
        raise OSError('Owned history fixture failure')
    f.history.append = failed
    record(f)
    assert not f.clipboard.ops and f.w.last_result.raw_text == f.source[0]
    assert f.w.last_result.cleaned_text == f.reply[0].text and f.w.services.processor.pending_results
    requests = [s[1] for s in f.signals if s[0] == 'command_recovery_requested']
    assert [r.result.task for r in requests] == ['translation_raw', 'translation']
    assert [r.result.text for r in requests] == [f.source[0], f.reply[0].text]


def test_cancel_during_generation_discards_late_output_and_retires_model(fixture):
    f = fixture
    factory = f.w.services.cleaner.llm.command_session
    def create(*args):
        editor = factory(*args)
        editor.edit_selection = lambda *a, **kw: f.w.cancel() or f.reply[0]
        return editor
    f.w.services.cleaner.llm.command_session = create
    record(f)
    assert not f.history.list_recent() and not f.clipboard.ops and all(e.closed for e in f.editors)
    assert f.w.translation.active is None and not f.w.busy


def test_cancel_after_commit_keeps_history_but_cannot_paste_or_open_recovery(fixture):
    f = fixture
    append = f.history.append
    def committed(entry):
        identifier = append(entry)
        f.w.cancel()
        return identifier
    f.history.append = committed
    record(f)
    assert len(f.history.list_recent()) == 1 and not f.clipboard.ops
    assert not any(s[0] == 'command_recovery_requested' for s in f.signals)


def test_settings_finish_current_translation_then_apply_without_stuck_owner(fixture):
    f = fixture
    f.w.start_recording()
    f.executor.drain()
    config = deepcopy(f.w.services.config)
    config['labs']['translate_mode'] = False
    replacement = replace(f.w.services, config=config)
    f.w.services_factory = lambda *a, **kw: replacement
    f.w.configure(config)
    f.clock.now += 1
    f.w.stop_recording()
    f.executor.drain()
    assert len(f.history.list_recent()) == 1 and f.w.services is replacement
    assert not f.w.busy and f.w.translation.active is None and f.w._pending_config is None


def test_recommended_backend_uses_saved_report_even_with_manual_pro_tier(fixture, tmp_path):
    f = fixture
    f.w.services.config['command']['backend'] = 'auto'
    f.w.translation.report_loader = lambda: {'vulkan': True}
    choices = []
    def resolve(choice, **kwargs):
        choices.append(choice)
        return SidecarConfig(tmp_path / 'fixture.gguf', backend=choice.backend)
    f.w.translation.resolver = resolve
    record(f)
    assert choices[0].backend == 'vulkan' and f.w.session.state == State.DONE


def test_background_recognition_remains_active_and_supplies_translation(fixture):
    from tests.test_session_worker import SegmentRecorder
    f = fixture
    f.w.services.recorder = SegmentRecorder()
    f.source[0] = 'The file is ready. The file is ready.'
    lengths = []
    f.w.services.asr.transcribe = lambda audio: lengths.append(len(audio)) or 'The file is ready.'
    record(f)
    assert len(lengths) == 2 and max(lengths) < len(f.w.services.recorder.audio)
    assert f.history.list_recent()[0].raw_text == f.source[0] and 'translate' in f.calls


@pytest.mark.parametrize('failure', ['empty', 'exception'])
def test_partial_background_words_require_review_when_final_recognition_cannot_finish(fixture, failure):
    f = fixture
    f.w.start_recording()
    f.executor.drain()
    f.w._background = NS(finish=lambda **kw: NS(failed=True, text=f.source[0],
        background_asr_seconds=.1, tail_seconds=0))
    def recognize(audio):
        if failure == 'exception':
            raise RuntimeError('Owned recognition failure')
        return ''
    f.w.services.asr.transcribe = recognize
    f.clock.now += 1
    f.w.stop_recording()
    f.executor.drain()
    row = f.history.list_recent()[0]
    assert row.mode == 'translation_failed' and row.cleaned_text == f.source[0]
    assert row.llm_decision == 'translation_source_requires_review'
    assert any(e.get('type') == 'source_incomplete' for e in json.loads(row.edits_json))
    assert 'translate' not in f.calls and not f.clipboard.ops


def test_preview_words_survive_for_review_without_translation_or_paste(fixture):
    from saydraft.core.preview import PreviewResult
    f = fixture
    f.w.start_recording()
    f.executor.drain()
    f.w._preview = NS(request_finish=lambda **kw: None,
        finish=lambda **kw: PreviewResult(f.source[0], False, True, 16000, .1))
    f.w.services.asr.transcribe = lambda audio: ''
    f.clock.now += 1
    f.w.stop_recording()
    f.executor.drain()
    row = f.history.list_recent()[0]
    assert row.mode == 'translation_failed' and row.cleaned_text == f.source[0]
    assert row.llm_decision == 'translation_source_requires_review'
    assert len(json.loads(row.edits_json)) == 2
    assert 'translate' not in f.calls and not f.clipboard.ops


def test_queue_failure_does_not_leave_a_reserved_translation_session(fixture):
    f = fixture
    def fail(*args):
        raise RuntimeError('Owned queue failure')
    f.executor.submit = fail
    assert not f.w.start_recording()
    assert not f.w.busy and f.w.translation.active is None
    assert f.w.session.state == State.ERROR and not f.calls


def test_empty_retained_translation_keeps_target_and_task_provenance(fixture, tmp_path):
    f = fixture
    f.w.services.config['recording']['retain_audio'] = True
    path = str(tmp_path / 'owned-audio.wav')
    f.w.services.audio_store = NS(save=lambda *a: path)
    f.w.services.asr.transcribe = lambda audio: ''
    record(f)
    row = f.history.list_recent()[0]
    assert row.mode == 'translation_failed' and row.audio_path == path and not row.cleaned_text
    assert row.llm_model == 'qwen35-4b-q4-k-m' and row.llm_decision == 'translation_asr_empty'
    assert json.loads(row.edits_json)[1]['target_language'] == 'es'
    assert f.history.last_transcript() is None and not f.w.retry_history(row)
