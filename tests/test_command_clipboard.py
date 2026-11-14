"""Actual held worker + metadata MTA + SQLite + complete memory clipboard only."""

import json
from types import SimpleNamespace as NS

import pytest

from saydraft.context.foreground import ForegroundContextProvider
from saydraft.context.uia_worker import BoundedUIA
from saydraft.core.command_copy import capture_command_copy
from saydraft.core.session import SessionState as State
from saydraft.insert.clipboard_win import WindowsClipboard
from saydraft.insert.inserter import Inserter
from tests.test_command_recording import fixture as worker_fixture, record
from tests.test_foreground_context import Api
from tests.test_selection import SelectionReader
from tests.test_selection_copy import Clock, CopyApi


@pytest.fixture
def fixture(tmp_path):
    f = worker_fixture(tmp_path)
    reader = SelectionReader(f.captured.selection.text)
    reader.supported = False
    owner = BoundedUIA(factory=lambda: reader, capture_timeout=.5)
    context = ForegroundContextProvider(api=Api(), uia=owner)
    context.capture = lambda: f.captured.target  # Legitimate dictation prefix has its own scripted context.
    api, clock, calls = CopyApi(), Clock(), []
    api.pids[77] = 42
    clipboard = WindowsClipboard(api_factory=lambda: api)
    original = api.data()
    modifiers = [False]
    def send(key):
        calls.append(key)
        assert key == 'ctrl+c', 'An unsupported original range must never receive a blind paste'
        assert not f.history.list_recent(), 'Selection copy precedes recognition and edit History'
        api.copy(f.captured.selection.text)
    inserter = Inserter(clipboard=clipboard, keyboard=NS(send=send), focus_provider=lambda: 123,
        delivery_guard=lambda _: 'modifier_held' if modifiers[0] else '')
    f.w.services.context, f.w.services.inserter = context, inserter
    f.w.services.config['command']['clipboard_fallback'] = True
    f.copy_api, f.copy_clock, f.copy_calls, f.copy_original = api, clock, calls, original
    f.copy_clipboard, f.copy_reader, f.copy_context, f.copy_modifiers = clipboard, reader, context, modifiers
    try:
        yield f
    finally:
        api.busy = api.fail_duplicate = False
        api.fail_put.clear()
        clipboard.recover()
        f.w.shutdown()
        owner.close()
        assert owner.wait_closed(2)
        api.assert_retired()


def pending(f):
    return f.copy_context.capture_selection(allow_copy=True)


def capture(f, captured, *, current=lambda: True):
    return capture_command_copy(captured, context=f.copy_context, inserter=f.w.services.inserter,
        current=current, clock=f.copy_clock, sleep=f.copy_clock.sleep)


def test_waits_for_all_physical_modifiers_before_one_copy_and_seals_only_after_restore(fixture):
    f = fixture
    target = pending(f)
    f.copy_modifiers[0] = True
    def tick():
        if f.copy_clock.now >= .03:
            f.copy_modifiers[0] = False
    f.copy_clock.tick = tick
    seal = f.copy_context.seal_copy
    def restored(*args):
        assert f.copy_api.data() == f.copy_original and not f.copy_clipboard.pending
        return seal(*args)
    f.copy_context.seal_copy = restored
    result = capture(f, target)
    assert result.reason == 'ok' and f.copy_clock.now >= .03
    assert result.captured.selection.origin == 'clipboard' and result.captured.selection.text == f.captured.selection.text
    assert f.copy_calls == ['ctrl+c'] and not f.copy_reader.reads
    assert f.copy_context.verify_selection(result.captured) == 'copy_only'


def test_still_held_modifiers_refuse_without_synthesizing_key_release_or_copy(fixture):
    f = fixture
    target = pending(f)
    f.copy_modifiers[0] = True
    result = capture(f, target)
    assert result.reason == 'modifier_held' and f.copy_clock.now == pytest.approx(.75)
    assert not f.copy_calls and not f.copy_api.reads and f.copy_api.data() == f.copy_original


def test_cancel_while_waiting_for_modifiers_sends_no_copy(fixture):
    f = fixture
    target, active = pending(f), [True]
    f.copy_modifiers[0] = True
    f.copy_clock.tick = lambda: active.__setitem__(0, False)
    result = capture(f, target, current=lambda: active[0])
    assert result.reason == 'cancelled' and not f.copy_calls and not f.copy_api.reads


@pytest.mark.parametrize('reason', ['password', 'unknown', 'focus', 'elevated'])
def test_fresh_sensitive_target_or_integrity_refusal_never_sends_copy(fixture, reason):
    f = fixture
    target = pending(f)
    if reason == 'password':
        f.copy_reader.password_value = True
    elif reason == 'unknown':
        f.copy_reader.password_value = None
    elif reason == 'focus':
        f.copy_context.api.foreground = lambda: 456
    else:
        f.w.services.inserter.delivery_guard = lambda _: 'target_elevated'
    assert capture(f, target).reason != 'ok' and not f.copy_calls and not f.copy_api.reads


def test_cancellation_after_copy_restores_formats_and_cannot_seal_text(fixture):
    f = fixture
    target, active = pending(f), [True]
    f.copy_api.after_read = lambda: active.__setitem__(0, False)
    result = capture(f, target, current=lambda: active[0])
    assert result.reason == 'cancelled' and result.captured is None
    assert f.copy_calls == ['ctrl+c'] and f.copy_api.data() == f.copy_original


def test_no_delivery_guard_or_explicit_copy_transport_means_no_copy(fixture):
    f = fixture
    target = pending(f)
    f.w.services.inserter.delivery_guard = None
    assert capture(f, target).reason == 'copy_unavailable' and not f.copy_calls


def test_full_held_fallback_preserves_instruction_provenance_and_opens_current_copy_recovery(fixture):
    f = fixture
    record(f)
    assert f.w.session.state == State.NOT_INSERTED and not f.w.busy and f.copy_calls == ['ctrl+c']
    assert f.copy_api.data() == f.copy_original and f.copy_clipboard.pending is None
    row = f.history.list_recent()[0]
    assert row.raw_text == f.captured.selection.text and row.cleaned_text == 'The file arrived.'
    assert row.mode == 'command' and json.loads(row.edits_json)[0]['selection_source'] == 'clipboard'
    assert json.loads(row.edits_json)[0]['instruction'] == 'Make shorter.'
    result = f.w.last_command_result
    assert result.reason == 'copy_only' and result.history_id == row.id and result.insertion.method == 'none'
    request = next(s[1] for s in f.signals if s[0] == 'command_recovery_requested')
    assert request.result == result and f.w.is_current_command_request(request)
    assert not f.copy_reader.reads and f.w.last_result is None
    assert f.history.weekly_stats().dictations == 0 and f.history.last_transcript() is None


def test_default_off_fallback_refuses_unsupported_selection_before_command_model_or_audio(fixture):
    f = fixture
    f.w.services.config['command']['clipboard_fallback'] = False
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    assert not f.copy_calls and not f.editors and f.w.services.recorder.started == 0
    assert not f.history.list_recent() and not f.w.busy
    assert any(s[0] == 'notification_requested' and 'clipboard-copy' in s[1] for s in f.signals)


def test_prefix_capture_is_retired_before_fallback_instruction_and_copy(fixture):
    f = fixture
    f.gestures.press('ctrl+win')
    f.executor.drain()
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    assert f.w.services.recorder.started == 2 and f.w.services.recorder.stopped == 1
    assert not f.copy_calls
    f.clock.now += 1
    f.gestures.release('ctrl+win+alt')
    f.executor.drain()
    assert f.copy_calls == ['ctrl+c'] and f.w.last_command_result.reason == 'copy_only'


def test_changed_field_after_recording_retains_instruction_without_clipboard_or_edit(fixture):
    f = fixture
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    f.copy_reader.runtime = (4, 5)
    f.clock.now += 1
    f.gestures.release('ctrl+win+alt')
    f.executor.drain()
    assert not f.copy_calls and not f.copy_api.reads
    assert not any(isinstance(c, tuple) and c[0] == 'edit' for c in f.calls)
    row = f.history.list_recent()[0]
    assert row.raw_text == 'Make shorter.' and row.cleaned_text == '' and row.mode == 'command'
    assert row.llm_decision == 'edit_failed:focus_changed' and f.w.last_command_result.text is None


def test_failed_restoration_retains_original_for_shared_recovery_and_instruction_for_history(fixture):
    f = fixture
    f.copy_api.after_read = lambda: setattr(f.copy_api, 'busy', True)
    record(f)
    assert f.copy_calls == ['ctrl+c'] and f.copy_clipboard.pending is not None
    assert f.w.last_command_result.reason == 'clipboard_restore_pending'
    assert f.history.list_recent()[0].raw_text == 'Make shorter.'
    assert not any(isinstance(c, tuple) and c[0] == 'edit' for c in f.calls)
    assert any(s[0] == 'notification_requested' and 'Recover clipboard' in s[1] for s in f.signals)
    f.copy_api.busy = False
    assert f.copy_clipboard.recover() and f.copy_api.data() == f.copy_original


def test_failed_model_reply_retains_instruction_after_copy_without_any_paste(fixture):
    f = fixture
    f.reply[0] = NS(text=None, reason='unavailable')
    record(f)
    row = f.history.list_recent()[0]
    assert row.raw_text == 'Make shorter.' and row.cleaned_text == ''
    assert f.copy_calls == ['ctrl+c'] and f.copy_api.data() == f.copy_original
    assert not any(s[0] == 'command_recovery_requested' for s in f.signals)


def test_standard_tier_refuses_before_metadata_copy_or_instruction_capture(fixture):
    f = fixture
    f.w.services.config['app']['tier'] = 'standard'
    f.gestures.press('ctrl+win+alt')
    f.executor.drain()
    assert not f.copy_calls and not f.editors and not f.history.list_recent()
    assert f.w.services.recorder.started == 0 and not f.copy_reader.reads
    assert any(s[0] == 'notification_requested' and 'Needs Pro' in s[1] for s in f.signals)


def test_settings_during_copy_finish_the_current_result_then_apply_without_stuck_reservation(fixture):
    from copy import deepcopy
    from dataclasses import replace
    f = fixture
    original = f.w.services
    config = deepcopy(original.config)
    config['command']['clipboard_fallback'] = False
    replacement = replace(original, config=config)
    f.w.services_factory = lambda *a, **kw: replacement
    def settings():
        f.w.configure(config)
        assert f.w.services is original and f.w._pending_config == config
    f.copy_api.after_read = settings
    record(f)
    assert f.w.last_command_result.reason == 'copy_only' and len(f.history.list_recent()) == 1
    assert f.w.services is replacement and not f.w.busy and f.w._pending_config is None
    assert f.copy_calls == ['ctrl+c'] and f.copy_api.data() == f.copy_original
