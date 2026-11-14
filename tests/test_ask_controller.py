"""Worker Ask lifecycle uses frozen public source, fake models and owned SQLite."""

from types import SimpleNamespace as NS
import threading

import pytest

from saydraft.cleanup.llm.ask import AskReply
from saydraft.context.foreground import SelectedContext
from saydraft.context.selection import SelectionSnapshot
from saydraft.core.ask_controller import AskController
from saydraft.core.interfaces import TargetContext
from saydraft.history import DictationHistoryStore
from tests.test_session_worker import make_worker


def rig(tmp_path, *, enabled=True, tier='pro', config_ready=True):
    worker, clock, executor, _, signals, _ = make_worker(queued=True)
    worker.services.config['labs']['ask_mode'] = enabled
    worker.services.config['app']['tier'] = tier
    worker.services.config['command']['backend'] = 'cpu'
    events, calls = [], []
    selected = SelectedContext(TargetContext(app_title='Public read-only article', app_exe='browser.exe', app_group='browser'),
        SelectionSnapshot(status='ready', text='The library opens on Saturday.', read_only=True))
    def capture(**options):
        events.append(('capture', options))
        return selected
    def verify(value, **options):
        assert value is selected
        events.append(('verify', options))
        return ''
    def revoke(value):
        assert value is selected
        events.append(('revoke',))
        return True
    worker.services.context = NS(capture_selection=capture, verify_selection=verify, cancel_selection=revoke)
    worker.services.history = DictationHistoryStore(tmp_path / 'ask.db')
    editor = NS(model_id='shared-editing-model', on_prepare=lambda: None, on_answer=lambda: None,
                closed=threading.Event(), close_count=0)
    def prepare(**options):
        editor.on_prepare()
        return 'ready'
    def ask(source, question, **options):
        calls.append((source, question, options))
        editor.on_answer()
        return AskReply('The library opens on Saturday.', 'ok', 200, 768, True)
    def close():
        editor.close_count += 1
        editor.closed.set()
    editor.prepare, editor.ask_about, editor.close = prepare, ask, close
    factories = []
    def factory(config, model_id):
        factories.append((config, model_id))
        return editor
    worker.services.cleaner = NS(llm=NS(command_session=factory))
    resolutions = []
    def resolve(choice, **options):
        resolutions.append((choice, options))
        return object() if config_ready else None
    worker.ask = AskController(worker, report_loader=lambda: None, config_resolver=resolve)
    def review():
        assert worker.ask.request(lambda: True)
        assert events[-1] == ('revoke',) and not factories and not resolutions
        assert worker.ask.busy
        executor.drain()
        request = next(s[1] for s in reversed(signals) if s[0] == 'ask_review_requested')
        assert worker.ask.review_is_current(request) and not worker.ask.busy and not worker.busy
        return request
    return NS(worker=worker, clock=clock, executor=executor, signals=signals, events=events,
        calls=calls, editor=editor, resolutions=resolutions, factories=factories, review=review)


def test_complete_answer_uses_frozen_read_only_source_and_history_before_gui_delivery(tmp_path):
    f = rig(tmp_path)
    request = f.review()
    assert f.worker.ask.submit(request, 'When does it open?')
    assert f.worker.busy and not f.calls
    f.executor.drain()
    answer = next(s[1] for s in f.signals if s[0] == 'ask_answer_requested')
    assert f.worker.ask.answer_is_current(answer)
    assert answer.result.text == f.worker.services.history.list_recent()[0].cleaned_text
    assert f.calls[0][:2] == ('The library opens on Saturday.', 'When does it open?')
    assert f.editor.close_count == 1 and not f.worker.busy
    assert [s[1].phase for s in f.signals if s[0] == 'ask_status_changed'] == ['preparing', 'answering', 'finished']
    assert f.worker.ask.review_is_current(request)  # Follow-up questions reuse the reviewed snapshot.
    assert len(f.events) == 3  # No source re-read after the review UI can take focus.


@pytest.mark.parametrize('enabled,tier', [(False, 'pro'), (True, 'lite'), (True, 'standard')])
def test_disabled_and_non_pro_admission_never_reads_selection_or_resolves_models(tmp_path, enabled, tier):
    f = rig(tmp_path, enabled=enabled, tier=tier)
    assert not f.worker.ask.request(lambda: True)
    assert not f.events and not f.resolutions and not f.factories and not f.worker.busy


def test_missing_model_preserves_review_for_retry_without_starting_runtime(tmp_path):
    f = rig(tmp_path, config_ready=False)
    request = f.review()
    assert f.worker.ask.submit(request, 'Question')
    f.executor.drain()
    status = [s[1] for s in f.signals if s[0] == 'ask_status_changed'][-1]
    assert status.result.reason == 'model_missing' and f.worker.ask.status_is_current(status)
    assert not f.factories and not f.worker.services.history.list_recent()
    assert f.worker.ask.review_is_current(request) and not f.worker.busy


@pytest.mark.parametrize('stage', ['pending_review', 'queued_answer', 'prepare', 'answer', 'late_factory'])
def test_cancel_retires_each_boundary_without_history_or_late_gui_answer(tmp_path, stage):
    f = rig(tmp_path)
    if stage == 'pending_review':
        assert f.worker.ask.request(lambda: True)
        f.worker.ask.cancel()
    else:
        request = f.review()
        if stage == 'prepare':
            f.editor.on_prepare = lambda: f.worker.ask.cancel(request)
        elif stage == 'answer':
            f.editor.on_answer = lambda: f.worker.ask.cancel(request)
        elif stage == 'late_factory':
            old = f.worker.services.cleaner.llm.command_session
            def late(*args):
                f.worker.ask.cancel(request)
                return old(*args)
            f.worker.services.cleaner.llm.command_session = late
        assert f.worker.ask.submit(request, 'Question')
        if stage == 'queued_answer':
            f.worker.ask.cancel(request)
    f.executor.drain()
    assert not f.worker.services.history.list_recent()
    assert not any(s[0] == 'ask_answer_requested' for s in f.signals)
    assert not f.worker.busy and f.worker.ask.review is None
    if f.factories:
        assert f.editor.closed.wait(2) and f.editor.close_count == 1


def test_new_capture_invalidates_only_answer_popup_not_reviewed_source(tmp_path):
    f = rig(tmp_path)
    request = f.review()
    assert f.worker.ask.submit(request, 'Question')
    f.executor.drain()
    answer = next(s[1] for s in f.signals if s[0] == 'ask_answer_requested')
    assert f.worker.ask.answer_is_current(answer)
    f.worker.ask.invalidate_answer()
    assert not f.worker.ask.answer_is_current(answer) and f.worker.ask.review_is_current(request)
    status = [s[1] for s in f.signals if s[0] == 'ask_status_changed'][-1]
    assert f.worker.ask.status_is_current(status)
    assert f.worker.ask.submit(request, 'Follow-up question')
    assert not f.worker.ask.status_is_current(status)
    f.executor.drain()


def test_stale_window_close_cannot_cancel_successor_review(tmp_path):
    f = rig(tmp_path)
    first = f.review()
    second = f.review()
    assert not f.worker.ask.cancel(first)
    assert f.worker.ask.review_is_current(second)
    assert not f.worker.ask.review_is_current(first)


def test_cancel_during_admitted_history_write_keeps_durable_answer_without_popup(tmp_path):
    f = rig(tmp_path)
    request = f.review()
    old = f.worker.services.history.append
    def persist(entry):
        identifier = old(entry)
        f.worker.ask.cancel(request)
        return identifier
    f.worker.services.history.append = persist
    assert f.worker.ask.submit(request, 'Question')
    f.executor.drain()
    assert len(f.worker.services.history.list_recent()) == 1
    assert not any(s[0] == 'ask_answer_requested' for s in f.signals)
    assert not f.worker.busy


@pytest.mark.parametrize('prefix', ['exact', 'missing', 'stale', 'bool'])
def test_only_exact_cancelled_ptt_prefix_may_queue_review_behind_retiring_arm(tmp_path, prefix):
    f = rig(tmp_path)
    f.worker.services.context.capture = lambda: TargetContext(app_title='Owned question window')
    generation = f.worker.start_recording(_return_generation=True)
    assert type(generation) is int and f.worker.busy
    f.worker.cancel()
    value = {'exact': generation, 'missing': None, 'stale': generation + 1, 'bool': True}[prefix]
    assert f.worker.ask.request(lambda: True, prefix_session_id=value) is (prefix == 'exact')
    f.executor.drain()
    assert not f.worker.busy and f.worker.services.recorder.started == 0
    requests = [s[1] for s in f.signals if s[0] == 'ask_review_requested']
    assert len(requests) == (1 if prefix == 'exact' else 0)


def test_review_stays_available_for_voicing_question_but_queued_presentation_is_retired(tmp_path):
    f = rig(tmp_path)
    request = f.review()
    assert f.worker.ask.review_can_present(request)
    f.worker.services.context.capture = lambda: TargetContext(app_title='Owned question window')
    assert f.worker.start_recording(insert_text=False)
    assert f.worker.ask.review_is_current(request)
    assert not f.worker.ask.review_can_present(request)
    f.executor.drain()
    f.clock.now = 2
    assert f.worker.stop_recording() is None
    f.executor.drain()
    assert f.worker.ask.review_is_current(request) and not f.worker.busy
    assert not f.worker.ask.review_can_present(request)  # A late initial popup cannot steal focus.
    assert f.worker.ask.submit(request, 'A question voiced into the already open review')
    f.executor.drain()
    assert len(f.worker.services.history.list_recent()) == 1


@pytest.mark.parametrize('stage', ['capture', 'queued_answer', 'stream'])
def test_settings_retires_ask_before_replacing_its_services(tmp_path, stage):
    from dataclasses import replace
    from saydraft.config import default_config
    f = rig(tmp_path)
    old = f.worker.services
    replacement = replace(old, config=default_config())
    f.worker.services_factory = lambda *args, **kwargs: replacement
    def configure():
        f.worker.configure(replacement.config)
        assert f.worker.services is old and f.worker._pending_config is replacement.config
    if stage == 'capture':
        original = old.context.capture_selection
        def capture(**options):
            selected = original(**options)
            configure()
            return selected
        old.context.capture_selection = capture
        assert not f.worker.ask.request(lambda: True)
    else:
        request = f.review()
        if stage == 'stream':
            f.editor.on_answer = configure
        assert f.worker.ask.submit(request, 'Question')
        if stage == 'queued_answer':
            configure()
    f.executor.drain()
    assert f.worker.services is replacement and f.worker._pending_config is None
    assert not old.history.list_recent() and not f.worker.busy
    assert f.worker.ask.review is None


def test_close_does_not_wait_for_admitted_history_write_or_blocking_model_close(tmp_path):
    f = rig(tmp_path)
    request = f.review()
    entered, release, closed, cancelled = (threading.Event() for _ in range(4))
    old_append = f.worker.services.history.append
    def append(entry):
        entered.set()
        assert release.wait(5)
        return old_append(entry)
    def close():
        closed.set()
        assert release.wait(5)
    f.worker.services.history.append, f.editor.close = append, close
    assert f.worker.ask.submit(request, 'Question')
    job = threading.Thread(target=f.executor.drain)
    job.start()
    assert entered.wait(3)
    stop = threading.Thread(target=lambda: (f.worker.ask.cancel(request), cancelled.set()))
    stop.start()
    try:
        assert cancelled.wait(2) and closed.wait(2)
        assert not f.worker.ask.review_is_current(request)
    finally:
        release.set()
        stop.join(5)
        job.join(5)
    assert not stop.is_alive() and not job.is_alive() and not f.worker.busy
    assert len(f.worker.services.history.list_recent()) == 1
    assert not any(s[0] == 'ask_answer_requested' for s in f.signals)
