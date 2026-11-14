"""Post-write proofs on synthetic providers; no owner desktop or clipboard."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import time
from types import SimpleNamespace as NS

import pytest

from saydraft.cleanup.llm.edit import EditReply
from saydraft.context.foreground import ForegroundContextProvider
from saydraft.context.selection import SelectionTracker
from saydraft.context.uia_worker import BoundedUIA
from saydraft.core.command_edit import CommandEditProcessor
from saydraft.history import DictationHistoryStore
from saydraft.insert.inserter import Inserter
from tests.test_foreground_context import Api
from tests.test_inserter import FakeClipboard, FakeKeyboard
from tests.test_selection import SelectionReader


class ConfirmReader(SelectionReader):
    def __init__(self, text='Source'):
        super().__init__(text)
        self.confirm_reads, self.positions = [], []
        self.on_confirm = lambda: None

    def selection_position(self, element, selected, current):
        self.positions.append((selected.start, threading.get_ident()))
        return selected.start

    def replacement_text(self, element, position, limit, current):
        self.confirm_reads.append((position, limit, threading.get_ident()))
        text = self.document[position:self.end] if self.start == self.end else None
        self.on_confirm()
        return text


def written(reader, text, at=0):
    reader.document = reader.document[:at] + text + reader.document[reader.end:]
    reader.start = reader.end = at + len(text)


def test_post_write_exact_span_confirmation_is_one_shot_and_uses_native_position():
    reader = ConfirmReader('prefix Source suffix')
    reader.start, reader.end = 7, 13
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    assert snapshot.status == 'ready' and tracker.verify(snapshot) == ''
    written(reader, 'New text', 7)
    assert tracker.confirm(snapshot, 'New text') == ''
    assert reader.document == 'prefix New text suffix'
    assert reader.confirm_reads == [(7, 8, threading.get_ident())] * 2
    assert tracker.expires_at is None and tracker.confirm(snapshot, 'New text') == 'selection_expired'


@pytest.mark.parametrize('state', ['ignored', 'different', 'other_position', 'noncollapsed', 'missing_position'])
def test_a_sent_key_or_matching_text_elsewhere_never_confirms(state):
    reader = ConfirmReader('Done | Source | Done')
    reader.start, reader.end = 7, 13
    if state == 'missing_position':
        reader.selection_position = lambda *args: None
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    if state == 'different':
        written(reader, 'Other', 7)
    elif state == 'other_position':
        reader.start = reader.end = len(reader.document)
    elif state == 'noncollapsed':
        reader.start, reader.end = 0, 4
    elif state == 'missing_position':
        written(reader, 'Done', 7)
    assert tracker.confirm(snapshot, 'Done') == 'insertion_unconfirmed'
    assert tracker.expires_at is None


@pytest.mark.parametrize('change,reason', [('password_value', 'password_field'), ('runtime', 'focus_changed'),
    ('pid', 'focus_changed'), ('focused', 'focus_changed'), ('read_only', 'read_only')])
def test_confirmation_checks_fresh_sensitive_state_before_any_post_write_text(change, reason):
    reader = ConfirmReader()
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    written(reader, 'Done')
    setattr(reader, change, {'password_value': True, 'runtime': (9,), 'pid': 99, 'focused': False, 'read_only': True}[change])
    assert tracker.confirm(snapshot, 'Done') == reason
    assert not reader.confirm_reads and tracker.expires_at is None


def test_sensitive_change_after_first_confirmation_read_cannot_publish_success():
    reader = ConfirmReader()
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    written(reader, 'Done')
    reader.on_confirm = lambda: setattr(reader, 'password_value', True)
    assert tracker.confirm(snapshot, 'Done') == 'password_field' and len(reader.confirm_reads) == 1


@pytest.mark.parametrize('text,expected', [('😀' * 8192, ''), ('😀' * 8193, 'insertion_unconfirmed'),
    ('\ud800', 'insertion_unconfirmed'), ('', 'insertion_unconfirmed')], ids=['max', 'over', 'surrogate', 'empty'])
def test_complete_replacement_utf16_limit_or_no_confirmation(text, expected):
    reader = ConfirmReader()
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42)
    written(reader, text)
    assert tracker.confirm(snapshot, text) == expected and tracker.expires_at is None


def test_stale_confirmation_does_not_release_a_newer_lease():
    reader = ConfirmReader()
    tracker = SelectionTracker(reader)
    first = tracker.begin(123, 42)
    second = tracker.begin(123, 42)
    assert tracker.confirm(first, 'Done') == 'selection_expired'
    assert tracker.verify(second) == ''
    assert tracker.confirm(replace(second, text='forged'), 'Done') == 'selection_expired'
    assert tracker.verify(second) == ''


def test_blocked_confirmation_times_out_on_same_mta_and_cancel_wakes_caller():
    reader = ConfirmReader()
    owner = BoundedUIA(factory=lambda: reader, capture_timeout=.04)
    entered, release = threading.Event(), threading.Event()
    try:
        snapshot = owner.capture_selection(123, 42)
        written(reader, 'Done')
        def blocked():
            entered.set()
            release.wait(2)
        reader.on_confirm = blocked
        with ThreadPoolExecutor(max_workers=1) as caller:
            pending = caller.submit(owner.confirm_replacement, snapshot, 'Done')
            assert entered.wait(1)
            thread = owner._thread
            started = time.monotonic()
            assert owner.cancel_selection(snapshot)
            assert pending.result(timeout=.2) == 'insertion_unconfirmed'
            assert time.monotonic() - started < .2 and owner._thread is thread
            assert owner.capture_selection(123, 42).status == 'unavailable'
            release.set()
        assert owner._thread is thread
    finally:
        release.set()
        owner.close()
        assert owner.wait_closed(2)


@pytest.mark.parametrize('deliver', [True, False])
def test_actual_capture_provider_processor_and_history_bind_ready_status_and_confirmation(tmp_path, deliver):
    source, candidate = 'I wanted to say the file arrived.', 'The file arrived.'
    reader = ConfirmReader('prefix ' + source + ' suffix')
    reader.start, reader.end = 7, 7 + len(source)
    owner = BoundedUIA(factory=lambda: reader, capture_timeout=.5)
    provider = ForegroundContextProvider(api=Api(), uia=owner)
    store = DictationHistoryStore(tmp_path / 'command.db')
    clipboard, keyboard, recovered, sent = FakeClipboard('before'), FakeKeyboard(), [], []
    try:
        captured = provider.capture_selection()
        assert captured.selection.status == 'ready'
        def send(key):
            assert store.list_recent()[0].raw_text == source
            sent.append(key)
            if deliver:
                written(reader, clipboard.value, 7)
        keyboard.send = send
        editor = NS(model_id='fixture-llm', edit_selection=lambda *args, **kwargs: EditReply(candidate, 'ok'))
        processor = CommandEditProcessor(editor=editor, selections=provider, history=store,
            inserter=Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
                             sleep=lambda _: None), recover=recovered.append)
        result = processor.process(captured, 'Make shorter.', current=lambda: True, run_current=lambda action: action())
        assert result.reason == ('ok' if deliver else 'insertion_unconfirmed')
        assert sent == ['ctrl+v'] and not keyboard.ops and clipboard.value == 'before'
        assert recovered == ([] if deliver else [result])
        assert result.confirmation_reason == ('' if deliver else 'insertion_unconfirmed')
        assert reader.document == ('prefix ' + candidate + ' suffix' if deliver else 'prefix ' + source + ' suffix')
        assert provider.verify_selection(captured) == 'selection_expired'
        assert {row[-1] for row in reader.confirm_reads} <= {owner._thread.ident}
    finally:
        provider.close()
        assert owner.wait_closed(2)


class NativeRange:
    def __init__(self, state, start, end):
        self.state, self.start, self.end = state, start, end

    def Clone(self):
        return NativeRange(self.state, self.start, self.end)

    def CompareEndpoints(self, endpoint, other, other_endpoint):
        return (self.start if endpoint == 0 else self.end) - (other.start if other_endpoint == 0 else other.end)

    def MoveEndpointByRange(self, endpoint, other, other_endpoint):
        value = other.start if other_endpoint == 0 else other.end
        if endpoint == 0:
            self.start = value
            self.end = max(self.end, value)
        else:
            self.end = value
            self.start = min(self.start, value)

    def MoveEndpointByUnit(self, endpoint, unit, count):
        assert unit == 0
        before = self.start if endpoint == 0 else self.end
        after = max(0, min(len(self.state.text), before + count))
        if endpoint == 0:
            self.start, self.end = after, max(after, self.end)
        else:
            self.end, self.start = after, min(after, self.start)
        return after - before

    def GetText(self, maximum):
        self.state.reads.append((self.start, self.end, maximum))
        self.state.on_read()
        return self.state.text[self.start:self.end][:maximum]


def native_reader():
    from saydraft.context.uia_native import NativeUIAReader
    state = NS(text='prefix Source suffix', selected=(7, 13), reads=[], on_read=lambda: None)
    reader = NativeUIAReader.__new__(NativeUIAReader)
    reader.lib = NS(UIA_TextPatternId=14, IUIAutomationTextPattern='text', TextPatternRangeEndpoint_Start=0,
                    TextPatternRangeEndpoint_End=1, TextUnit_Character=0)
    pattern = NS(DocumentRange=NativeRange(state, 0, len(state.text)),
                 GetSelection=lambda: NS(Length=1, GetElement=lambda index: NativeRange(state, *state.selected)))
    element = NS(GetCurrentPattern=lambda key: NS(QueryInterface=lambda interface: pattern))
    return reader, element, state, pattern


def test_native_offset_roundtrip_reads_no_document_and_confirmation_reads_bounded_span_only():
    reader, element, state, pattern = native_reader()
    selected = reader.selection_range(element, lambda: True)
    assert reader.selection_position(element, selected, lambda: True) == 7 and not state.reads
    state.text, state.selected = 'prefix New text suffix', (15, 15)
    pattern.DocumentRange = NativeRange(state, 0, len(state.text))
    assert reader.replacement_text(element, 7, 8, lambda: True) == 'New text'
    assert state.reads == [(7, 15, 9)]  # No prefix/document/suffix GetText.


def test_native_replacement_refuses_noncollapsed_wrong_or_changed_caret_and_overlong_span():
    reader, element, state, _pattern = native_reader()
    assert reader.replacement_text(element, 7, 6, lambda: True) is None and not state.reads
    state.selected = (4, 4)
    assert reader.replacement_text(element, 7, 6, lambda: True) is None and not state.reads
    state.selected = (len(state.text), len(state.text))
    assert reader.replacement_text(element, 7, 6, lambda: True) is None
    assert state.reads[-1][2] == 7  # One overflow unit, never an unbounded document read.
    state.selected = (13, 13)
    state.on_read = lambda: setattr(state, 'selected', (14, 14))
    assert reader.replacement_text(element, 7, 6, lambda: True) is None


def test_native_roundtrip_rejects_provider_movement_with_unsupported_coordinate():
    reader, element, state, _pattern = native_reader()
    selected = NS(start=7, end=13, Clone=lambda: NS(MoveEndpointByUnit=lambda *args: -6,
                                   CompareEndpoints=lambda *args: 0))
    assert reader.selection_position(element, selected, lambda: True) is None
    assert not state.reads
