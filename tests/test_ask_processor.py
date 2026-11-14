"""Ask keeps source documents immutable and saves complete answers before UI."""

from dataclasses import asdict
import hashlib
import json
from types import SimpleNamespace as NS

import pytest

from saydraft.cleanup.llm.ask import AskReply
from saydraft.core.ask import AskProcessor, AskSource
from saydraft.history import DictationHistoryStore, HistoryEntry


SOURCE = AskSource('Public Arabic العربية and Bengali বাংলা reference.', 'Public article', 'browser.exe', 'browser')


def rig(tmp_path, *, reply=AskReply('The source mentions two languages.', 'ok', 200, 768, True)):
    history = DictationHistoryStore(tmp_path / 'history.db')
    events, active = [], [True]
    def ask(source, question, **options):
        events.append(('model', source, question, options))
        return reply
    def present(result):
        rows = history.list_recent()
        if result.history_id:
            assert rows[0].id == result.history_id and rows[0].cleaned_text == result.text
        events.append(('present', result))
    editor = NS(model_id='local-ask-fixture', ask_about=ask)
    processor = AskProcessor(editor=editor, history=history, present=present)
    def guarded(action):
        return action() if active[0] else None
    def run(source=SOURCE, question='What languages are mentioned?', **options):
        return processor.process(source, question, current=lambda: active[0],
            run_current=guarded, persist_current=guarded, **options)
    return NS(processor=processor, run=run, history=history, events=events, active=active, editor=editor)


@pytest.mark.parametrize('action', ['question', 'summarize', 'explain', 'rewrite'])
def test_complete_answer_is_saved_before_independent_presentation_with_no_source_copy(tmp_path, action):
    f = rig(tmp_path)
    result = f.run(action=action)
    assert result.reason == 'ok' and result.history_id == 1 and result.action == action
    assert [event[0] for event in f.events] == ['model', 'present']
    row = f.history.get_row(1)
    assert row.raw_text == 'What languages are mentioned?' and row.cleaned_text == result.text
    assert row.mode == row.profile == 'ask' and row.language == 'und'
    assert row.duration_seconds is row.audio_path is None and not row.asr_model
    metadata = json.loads(row.edits_json)[0]
    assert metadata['source_sha256'] == hashlib.sha256(SOURCE.text.encode('utf-8')).hexdigest()
    assert metadata['source_utf16_units'] == len(SOURCE.text.encode('utf-16-le')) // 2
    assert metadata['input_tokens'] == 200 and metadata['output_limit'] == 768
    assert SOURCE.text not in json.dumps(asdict(row), ensure_ascii=False)
    assert row.llm_model == 'local-ask-fixture' and row.llm_decision == 'ask_answered'


@pytest.mark.parametrize('reply,reason', [
    (AskReply(None, 'unavailable'), 'unavailable'),
    (AskReply('Partial', 'ok', stream_complete=False), 'incomplete'),
    (AskReply('Invented https://invented.example/', 'ok', stream_complete=True), 'external_reference'),
    (AskReply('Bad\0text', 'ok', stream_complete=True), 'invalid_answer'),
    (NS(text='An answer', reason='ok', stream_complete=True), 'invalid_reply'),
])
def test_failed_partial_or_invalid_output_never_reaches_history_or_presentation(tmp_path, reply, reason):
    f = rig(tmp_path, reply=reply)
    result = f.run()
    assert result.text is None and result.reason == reason
    assert not f.history.list_recent() and [event[0] for event in f.events] == ['model']


@pytest.mark.parametrize('when', ['before_model', 'after_model', 'before_history', 'after_history', 'before_present'])
def test_cancellation_retires_late_answers_at_each_boundary(tmp_path, when):
    f = rig(tmp_path)
    original = f.editor.ask_about
    if when == 'before_model':
        f.active[0] = False
    elif when == 'after_model':
        def ask(*args, **kwargs):
            reply = original(*args, **kwargs)
            f.active[0] = False
            return reply
        f.editor.ask_about = ask
    def persist(action):
        if when == 'before_history':
            f.active[0] = False
            return None
        identifier = action()
        if when == 'after_history':
            f.active[0] = False
        return identifier
    def present(action):
        if when == 'before_present':
            f.active[0] = False
        if f.active[0]:
            return action()
    result = f.processor.process(SOURCE, 'Question', current=lambda: f.active[0],
        run_current=present, persist_current=persist)
    assert result.text is None and result.reason == 'cancelled'
    assert not any(event[0] == 'present' for event in f.events)
    assert len(f.history.list_recent()) == (1 if when in ('after_history', 'before_present') else 0)


def test_history_failure_preserves_answer_in_standalone_recovery(tmp_path):
    f = rig(tmp_path)
    def fail(_entry):
        raise OSError('Authored storage failure')
    f.history.append = fail
    result = f.run()
    assert result.reason == 'history_unavailable' and result.text and result.history_id is None
    assert f.events[-1] == ('present', result)


def test_missing_answer_window_keeps_the_durable_history_answer(tmp_path):
    f = rig(tmp_path)
    def fail(_result):
        raise RuntimeError('Authored receiver failure')
    f.processor.present = fail
    result = f.run()
    assert result.reason == 'display_unavailable' and result.history_id == 1
    assert f.history.get_row(1).cleaned_text == result.text


def test_typed_question_and_answer_are_excluded_from_dictation_stats_and_paste_last(tmp_path):
    f = rig(tmp_path)
    assert f.run().reason == 'ok'
    stats = f.history.weekly_stats()
    assert (stats.dictations, stats.words, stats.audio_seconds) == (0, 0, 0)
    assert stats.duration_complete and f.history.last_transcript() is None
    with f.history._connect() as connection:
        assert connection.execute('SELECT sum(processing_seconds) FROM stats_daily').fetchone()[0] == 0
    f.history.append(HistoryEntry('Editor', 'Spoken text.', 'Spoken text.', 'balanced', 'notes', 2, 'fixture'))
    assert f.run().reason == 'ok'
    assert f.history.last_transcript() == 'Spoken text.'
    stats = f.history.weekly_stats()
    assert (stats.dictations, stats.words, stats.audio_seconds) == (1, 2, 2)
    assert stats.duration_complete


@pytest.mark.parametrize('source,question', [(SOURCE, ''), (AskSource(''), 'Q'), (None, 'Q')])
def test_invalid_request_starts_no_model_or_storage(tmp_path, source, question):
    f = rig(tmp_path)
    assert f.run(source, question).reason == 'invalid_request'
    assert not f.events and not f.history.list_recent()
