import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.edit import EditClient, EditReply, build_edit_messages, validate_edit_output
from saydraft.cleanup.llm.edit_eval import check_case, load_cases
from saydraft.cleanup.llm.sidecar import SidecarReply
from saydraft.context.foreground import SelectedContext
from saydraft.context.selection import SelectionSnapshot
from saydraft.core.command_edit import CommandEditProcessor
from saydraft.core.interfaces import TargetContext
from saydraft.history import DictationHistoryStore, HistoryEntry
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.insert.inserter import Inserter
from tests.test_cleanup_streaming import DONE, frame
from tests.test_inserter import FakeClipboard, FakeKeyboard


@pytest.mark.parametrize('source,instruction,output', [
    ('I wanted to let you know that the package arrived.', 'Make this shorter.', 'The package arrived.'),
    ('Can you send the report?', 'Make this more formal.', 'Would you kindly send the report?'),
    ('Bring bread and milk.', 'Use bullets.', '- Bring bread.\n- Bring milk.'),
    ('The file is not ready.', 'Translate to Spanish.', 'El archivo no está listo.'),
    ('Cost: $25. Contact a@example.com.', 'Translate to Spanish.', 'Costo: $25. Contacto: a@example.com.'),
])
def test_editing_allows_rewrites_that_normal_cleanup_must_refuse(source, instruction, output):
    assert validate_edit_output(source, instruction, output).ok


@pytest.mark.parametrize('source,output,reason', [
    ('Cost: $25.', 'Cost: $26.', 'numbers_changed'),
    ('Cost: $25.', 'Cost: 25.', 'currency_changed'),
    ('Send to a@example.com.', 'Send to b@example.com.', 'emails_changed'),
    ('Use https://example.com/a.', 'Use https://example.com/b.', 'urls_changed'),
    ('Run `a += 1`.', 'Run `a += 2`.', 'code_changed'),
    ('Use __SPAN_0__.', 'Use __SPAN_1__.', 'placeholders_changed'),
    ('Do not send it.', 'Send it.', 'negation_changed'),
    ('Meet May 2.', 'Meet June 2.', 'dates_changed'),
    ('Meet at 10:30.', 'Meet at 30:10.', 'times_changed'),
    ('Cost 10 USD.', 'Cost 10 EUR.', 'amounts_changed'),
    ('Document text.', '<think>Document text.</think>', 'wrapper_output'),
    ('Document text.', '<|im_start|>assistant', 'wrapper_output'),
    ('Document text.', 'Sure, document text.', 'instruction_or_commentary'),
    ('Document text.', 'Make shorter.', 'instruction_or_commentary'),
    ('Document text.', 'Doc\u202etext.', 'controls_added'),
])
def test_changed_protected_values_and_new_wrappers_are_refused(source, output, reason):
    assert validate_edit_output(source, 'Make shorter.', output).reason == reason


def test_complete_selection_instruction_and_unicode_bounds_without_truncation():
    source, instruction = '😀' * 4096, 'Translate to Spanish.'
    messages = build_edit_messages(source, instruction)
    assert json.loads(messages[-1]['content']) == {'selection': source, 'instruction': instruction}
    for bad_source, bad_instruction in [(source + 'x', instruction), ('x', 'a' * 1025),
                                        ('\ud800', instruction), ('a\0b', instruction), ('', instruction)]:
        with pytest.raises(ValueError):
            build_edit_messages(bad_source, bad_instruction)
    assert validate_edit_output('x', instruction, '😀' * 8193).reason == 'invalid_replacement'


def test_negated_translation_instruction_does_not_relax_normal_edit_negation_guard():
    assert validate_edit_output('Do not send it.', 'Do not translate. Make shorter.', 'Send it.').reason == 'negation_changed'


def test_thirty_authored_cases_have_valid_references_for_all_four_instruction_families():
    cases = load_cases()
    assert len(cases) == 30 and {case['kind'] for case in cases} == {'shorter', 'formal', 'bullets', 'spanish'}
    assert all(check_case(case, case['reference']) == 'ok' for case in cases)


class Model:
    def __init__(self, output='{"replacement":"The file arrived."}', *, chunks=None, tokens=200):
        self.chunks = chunks if chunks is not None else [frame(output, finish='stop'), DONE]
        self.tokens, self.calls, self.closed = tokens, [], False
        self.on_request = lambda: None

    def request_json(self, path, **options):
        self.calls.append((path, options))
        self.on_request()
        return {'prompt': 'complete rendered chat'} if path == '/apply-template' else {'tokens': list(range(self.tokens))}

    @contextmanager
    def response_bytes(self, path, **options):
        self.calls.append((path, options))
        try:
            yield iter(self.chunks)
        finally:
            self.closed = True


def client(model, *, context_size=4096, invalidate=lambda: None):
    def run(operation, *, timeout):
        return SidecarReply(operation(model, 100 + timeout), 'ok')
    return EditClient(SimpleNamespace(run=run, config=SimpleNamespace(context_size=context_size)),
                      clock=lambda: 100, invalidate=invalidate)


def test_full_local_request_counts_chat_and_reserves_output_before_generation():
    model, invalidations = Model(), []
    reply = client(model, invalidate=lambda: invalidations.append(True)).edit(
        'I wanted to say the file arrived.', 'Make shorter.')
    assert reply == EditReply('The file arrived.', 'ok', 200, 768)
    assert [path for path, _ in model.calls] == ['/apply-template', '/tokenize', '/v1/chat/completions']
    assert invalidations == [True, True] and model.closed
    payload = model.calls[-1][1]['payload']
    assert payload['cache_prompt'] is False and payload['response_format']['schema']['additionalProperties'] is False
    assert all(options['deadline'] == 145 for _, options in model.calls)
    assert model.calls[1][1]['payload']['parse_special'] is True


def test_over_context_refuses_before_generation_and_keeps_cleanup_prefix():
    model, invalidations = Model(tokens=3500), []
    reply = client(model, invalidate=lambda: invalidations.append(True)).edit('Text.', 'Make shorter.')
    assert reply.text is None and reply.reason == 'context_limit'
    assert not invalidations and len(model.calls) == 2 and not model.closed


@pytest.mark.parametrize('raw', ['{"replacement":"Text.","replacement":"Other."}',
    '{"replacement":"Text.","explanation":"words"}', '{"replacement":null}',
    '{"replacement":NaN}', '{"replacement":"Text."} trailing', 'Text.', '```json\n{}\n```'])
def test_structured_response_is_exact_and_never_silently_repaired(raw):
    reply = client(Model(raw)).edit('Text.', 'Make shorter.')
    assert reply.text is None and reply.reason == 'response_format'


@pytest.mark.parametrize('chunks,reason', [
    ([frame('{"replacement":"partial"}')], 'incomplete'),
    ([frame('{"replacement":"Text."}', finish='length'), DONE], 'incomplete'),
    ([frame('{"replacement":"Text."}', finish='stop', tool_calls=[{}]), DONE], 'tool_output')])
def test_incomplete_or_tool_output_never_delivered(chunks, reason):
    model = Model(chunks=chunks)
    reply = client(model).edit('Text.', 'Make shorter.')
    assert reply.text is None and reply.reason == reason and model.closed


def test_cancel_before_request_during_token_count_and_midstream_drops_all_output():
    model = Model()
    assert client(model).edit('Text.', 'Make shorter.', cancelled=lambda: True).reason == 'cancelled'
    assert not model.calls
    cancelled = [False]
    model.on_request = lambda: cancelled.__setitem__(0, True)
    assert client(model).edit('Text.', 'Make shorter.', cancelled=lambda: cancelled[0]).reason == 'cancelled'
    assert len(model.calls) == 1
    model, cancelled = Model(), [False]
    def chunks():
        yield frame('{"replacement":')
        cancelled[0] = True
        yield frame('"Text."}', finish='stop')
        yield DONE
    model.chunks = chunks()
    invalidations = []
    reply = client(model, invalidate=lambda: invalidations.append(True)).edit(
        'Text.', 'Make shorter.', cancelled=lambda: cancelled[0])
    assert reply.reason == 'cancelled' and reply.text is None and model.closed
    assert invalidations == [True, True]


def test_app_adapter_reuses_owned_manager_and_invalidates_both_cleanup_readiness_receipts(tmp_path):
    model = Model()
    def run(operation, *, timeout):
        return SidecarReply(operation(model, 100 + timeout), 'ok')
    managers = []
    def factory(config):
        manager = SimpleNamespace(config=config, run=run, close=lambda: None)
        managers.append(manager)
        return manager
    local = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path=str(tmp_path / 'fixture.gguf'),
        prepare_prompt=False), manager_factory=factory, clock=lambda: 100)
    cleanup = local._get_client()
    cleanup._prefix = ('prior',)
    invalidations = []
    local._preparation = SimpleNamespace(invalidate=lambda: invalidations.append(True), close=lambda: None)
    reply = local.edit_selection('I wanted to say the file arrived.', 'Make shorter.')
    assert reply.text == 'The file arrived.' and len(managers) == 1 and cleanup._prefix is None
    assert invalidations == [True, True]
    local.close()
    assert local.edit_selection('Text.', 'Make shorter.').reason == 'cancelled'
    disabled = LocalLLMCleaner(LocalLLMConfig(), manager_factory=lambda _: pytest.fail('Disabled runtime'))
    assert disabled.edit_selection('Text.', 'Make shorter.').reason == 'disabled'


def setup_processor(tmp_path, *, verify=lambda: '', history=None):
    events, active, recovered = [], [True], []
    store = history or DictationHistoryStore(tmp_path / 'command.db')
    editor = SimpleNamespace(model_id='fixture-llm', edit_selection=lambda *args, **kwargs:
                             EditReply('The file arrived.', 'ok', 150, 768))
    captured = SelectedContext(TargetContext(focus=15, app_title='Owned fixture', uia_status='ok'),
                               SelectionSnapshot(status='ok', text='I wanted to say the file arrived.', ticket=1))
    selections = SimpleNamespace(verify_selection=lambda *args, **kwargs: verify(),
                                 cancel_selection=lambda value: events.append(('cancel', value)))
    clipboard, keyboard = FakeClipboard(), FakeKeyboard()
    def send(key):
        assert store.list_recent()[0].mode == 'command'  # Durable before input.
        events.append(('send', key))
    keyboard.send = send
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 15, sleep=lambda _: None)
    processor = CommandEditProcessor(editor=editor, selections=selections, history=store,
        inserter=inserter, recover=recovered.append)
    def run():
        return processor.process(captured, 'Make shorter.', current=lambda: active[0],
                                 run_current=lambda action: action() if active[0] else None, asr_model='fixture-asr')
    return SimpleNamespace(processor=processor, run=run, editor=editor, captured=captured,
                           active=active, events=events, recovered=recovered, history=store,
                           clipboard=clipboard, keyboard=keyboard)


def test_command_persists_selection_instruction_models_before_guarded_paste(tmp_path):
    f = setup_processor(tmp_path)
    result = f.run()
    assert result.reason == 'ok' and result.insertion.status == 'inserted'
    row = f.history.list_recent()[0]
    assert row.raw_text == f.captured.selection.text and row.cleaned_text == result.text
    assert row.llm_model == 'fixture-llm' and row.asr_model == 'fixture-asr' and row.mode == 'command'
    assert json.loads(row.edits_json)[0]['instruction'] == 'Make shorter.'
    assert f.events == [('send', 'ctrl+v'), ('cancel', f.captured)]
    assert f.clipboard.value == 'original' and not f.recovered
    assert f.history.weekly_stats().words == f.history.weekly_stats().dictations == 0
    assert f.history.weekly_stats().duration_complete and f.history.last_transcript() is None
    f.history.append(HistoryEntry('fixture', 'spoken words', 'Spoken words.', 'balanced', 'general', 2, 'asr'))
    assert f.history.weekly_stats().dictations == 1 and f.history.weekly_stats().words == 2
    assert f.history.last_transcript() == 'Spoken words.'


def test_selection_changed_after_generation_keeps_result_for_copy_without_input(tmp_path):
    reasons = iter(['', 'selection_changed'])
    f = setup_processor(tmp_path, verify=lambda: next(reasons))
    result = f.run()
    assert result.reason == 'selection_changed' and f.recovered == [result]
    assert f.history.list_recent() and not f.clipboard.ops and not f.keyboard.ops
    assert f.events == [('cancel', f.captured)]


def test_cancel_during_generation_discards_late_result_and_releases_only_this_lease(tmp_path):
    f = setup_processor(tmp_path)
    def edit(*args, **kwargs):
        f.active[0] = False
        assert kwargs['cancelled']()
        return EditReply('The file arrived.', 'ok')
    f.editor.edit_selection = edit
    assert f.run().reason == 'cancelled'
    assert not f.history.list_recent() and not f.recovered and not f.clipboard.ops
    assert f.events == [('cancel', f.captured)]


def test_history_failure_recovers_valid_output_without_paste(tmp_path):
    def fail(entry):
        raise OSError('fixture storage failure')
    f = setup_processor(tmp_path, history=SimpleNamespace(append=fail))
    result = f.run()
    assert result.reason == 'history_unavailable' and f.recovered == [result]
    assert not f.clipboard.ops and not f.keyboard.ops


@pytest.mark.parametrize('reason', ['read_only', 'password_field', 'selection_expired'])
def test_initial_target_failure_never_calls_editor_or_changes_storage(tmp_path, reason):
    f = setup_processor(tmp_path, verify=lambda: reason)
    f.editor.edit_selection = lambda *args, **kwargs: pytest.fail('Must not generate')
    assert f.run().reason == reason
    assert not f.history.list_recent() and not f.recovered and not f.clipboard.ops


def test_command_delivery_refuses_typing_profile_and_clipboard_failure(tmp_path):
    f = setup_processor(tmp_path)
    f.processor.inserter.profiles = [{'match': 'Owned', 'insertion': 'typing'}]
    assert f.run().reason == 'paste_unavailable' and not f.keyboard.ops and not f.clipboard.ops
    f = setup_processor(tmp_path / 'next')
    class Unavailable:
        pending = None
        @contextmanager
        def temporary_text(self, *args, **kwargs):
            raise OSError('fixture clipboard unavailable')
            yield  # noqa: B018
    f.processor.inserter.clipboard = Unavailable()
    result = f.run()
    assert result.reason == 'clipboard_unavailable' and not f.keyboard.ops and f.recovered == [result]
