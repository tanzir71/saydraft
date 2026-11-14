"""No desktop access: copy metadata, sealed text and scoped MTA retirement."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading

import pytest

from saydraft.context.foreground import ForegroundContextProvider
from saydraft.context.selection import SelectionTracker
from saydraft.context.uia_worker import BoundedUIA
from tests.test_foreground_context import Api
from tests.test_selection import SelectionReader


def tracker_fixture():
    reader = SelectionReader()
    reader.supported = False
    return reader, SelectionTracker(reader)


def test_copy_permission_reserves_metadata_only_and_sealing_never_grants_write_authority():
    reader, tracker = tracker_fixture()
    assert tracker.begin(123, 42).status == 'unsupported' and tracker.expires_at is None
    pending = tracker.begin(123, 42, allow_copy=True)
    assert pending.status == 'copy_pending' and pending.origin == 'clipboard' and pending.ticket > 0
    assert not pending.text and not reader.reads and not reader.range_count
    assert tracker.verify(pending, for_write=False) == ''
    sealed = tracker.seal_copy(pending, 'Copied public selection')
    assert sealed.status == 'ready' and sealed.origin == 'clipboard' and sealed.ticket == pending.ticket
    assert sealed.text == 'Copied public selection' and not reader.reads and not reader.range_count
    assert tracker.verify(pending, for_write=False) == 'selection_expired'
    assert tracker.verify(sealed, for_write=False) == '' and tracker.verify(sealed) == 'copy_only'
    assert tracker.confirm(sealed, 'Edit') == 'insertion_unconfirmed' and tracker.expires_at is None


@pytest.mark.parametrize('control,expected', [(50004, 'copy_pending'), (50020, 'copy_pending'),
    (50030, 'copy_pending'), (50000, 'unsupported'), (50033, 'unsupported')])
def test_only_known_text_controls_can_reserve_a_copy_target(control, expected):
    reader, tracker = tracker_fixture()
    reader.control_type = lambda _: control
    assert tracker.begin(123, 42, allow_copy=True).status == expected
    assert not reader.reads and not reader.range_count
    tracker.clear()


@pytest.mark.parametrize('password', [True, None, 0, 'false'])
def test_password_and_unknown_state_never_authorize_metadata_copy_reservation(password):
    reader, tracker = tracker_fixture()
    reader.password_value = password
    assert tracker.begin(123, 42, allow_copy=True).status != 'copy_pending'
    assert tracker.expires_at is None and not reader.reads and not reader.range_count


@pytest.mark.parametrize('change,reason', [('password', 'password_field'), ('unknown', 'field_unavailable'),
    ('runtime', 'focus_changed'), ('pid', 'focus_changed'), ('focus', 'focus_changed'), ('control', 'focus_changed')])
def test_sealing_rechecks_original_identity_and_password_without_reading_new_field_text(change, reason):
    reader, tracker = tracker_fixture()
    pending = tracker.begin(123, 42, allow_copy=True)
    if change == 'password':
        reader.password_value = True
    elif change == 'unknown':
        reader.password_value = None
    elif change == 'runtime':
        reader.runtime = (4, 5)
    elif change == 'pid':
        reader.pid = 43
    elif change == 'focus':
        reader.focused = False
    else:
        reader.control_type = lambda _: 50030
    sealed = tracker.seal_copy(pending, 'Copied public text')
    assert sealed.status == reason and not sealed.text and tracker.expires_at is None
    assert not reader.reads and not reader.range_count


@pytest.mark.parametrize('text,ready', [('x' * 8192, True), ('\U0001f600' * 4096, True),
    ('x' * 8193, False), ('\U0001f600' * 4097, False), ('', False), ('a\0b', False), ('\ud800', False)],
    ids=['limit', 'utf16-limit', 'over', 'utf16-over', 'empty', 'nul', 'surrogate'])
def test_sealed_text_is_complete_bounded_unicode_or_no_text(text, ready):
    reader, tracker = tracker_fixture()
    pending = tracker.begin(123, 42, allow_copy=True)
    sealed = tracker.seal_copy(pending, text)
    assert (sealed.status == 'ready') == ready
    assert sealed.text == (text if ready else '') and not reader.reads
    tracker.clear()


def test_forged_origin_or_text_cannot_escalate_a_copy_lease_and_stale_seal_preserves_successor():
    reader, tracker = tracker_fixture()
    old = tracker.begin(123, 42, allow_copy=True)
    current = tracker.begin(123, 42, allow_copy=True)
    assert tracker.seal_copy(old, 'Old').status == 'selection_expired'
    assert tracker.verify(current, for_write=False) == ''
    sealed = tracker.seal_copy(current, 'Current')
    assert tracker.verify(replace(sealed, origin='uia')) == 'selection_expired'
    assert tracker.verify(replace(sealed, text='Other'), for_write=False) == 'selection_expired'
    assert tracker.verify(sealed, for_write=False) == '' and not reader.reads
    tracker.clear()


def test_sealing_does_not_extend_the_original_lease():
    reader, _ = tracker_fixture()
    now = [0]
    tracker = SelectionTracker(reader, clock=lambda: now[0])
    pending = tracker.begin(123, 42, allow_copy=True, lease_seconds=1)
    now[0] = .9
    sealed = tracker.seal_copy(pending, 'Public')
    assert tracker.expires_at == 1
    now[0] = 1
    assert tracker.verify(sealed, for_write=False) == 'selection_expired' and not reader.reads


def test_available_native_selection_keeps_its_range_even_when_copy_permission_is_present():
    reader = SelectionReader()
    tracker = SelectionTracker(reader)
    snapshot = tracker.begin(123, 42, allow_copy=True)
    assert snapshot.status == 'ready' and snapshot.origin == 'uia' and tracker.verify(snapshot) == ''
    tracker.clear()


@pytest.fixture
def owner():
    reader, _ = tracker_fixture()
    owner = BoundedUIA(factory=lambda: reader, capture_timeout=.5)
    try:
        yield owner, reader
    finally:
        owner.close()
        assert owner.wait_closed(2)


def test_pending_and_sealed_requests_share_one_mta_and_generation(owner):
    uia, reader = owner
    pending = uia.capture_selection(123, 42, allow_copy=True)
    assert pending.status == 'copy_pending' and pending.generation > 0
    sealed = uia.seal_copy(pending, 'Public copied text')
    assert sealed.generation == pending.generation and sealed.ticket == pending.ticket
    assert uia.verify_selection(sealed, for_write=False) == ''
    assert uia.verify_selection(sealed) == 'copy_only'
    next_target = uia.capture_selection(123, 42, allow_copy=True)
    assert uia.seal_copy(pending, 'Old text').status == 'selection_expired'
    assert not uia.cancel_selection(sealed) and uia.verify_selection(next_target, for_write=False) == ''
    assert not reader.reads and not reader.range_count


def test_cancellation_wakes_a_blocked_seal_and_discards_its_late_copied_text(owner):
    uia, reader = owner
    pending = uia.capture_selection(123, 42, allow_copy=True)
    entered, release = threading.Event(), threading.Event()
    original = reader.password
    def blocked(element):
        entered.set()
        assert release.wait(3)
        return original(element)
    reader.password = blocked
    try:
        with ThreadPoolExecutor(max_workers=1) as caller:
            future = caller.submit(uia.seal_copy, pending, 'Late copied text')
            assert entered.wait(1)
            assert uia.cancel_selection(pending)
            result = future.result(timeout=.3)
            assert result.status != 'ready' and not result.text
            release.set()
    finally:
        release.set()
    assert not reader.reads


def test_foreground_bridge_binds_text_without_caret_or_surrounding_context(owner):
    uia, reader = owner
    provider = ForegroundContextProvider(api=Api(), uia=uia)
    pending = provider.capture_selection(allow_copy=True)
    assert pending.selection.status == 'copy_pending' and not pending.target.selection_known
    assert not provider.verify_selection(pending, for_write=False)
    sealed = provider.seal_copy(pending, 'Copied public text')
    assert sealed.selection.status == 'ready' and sealed.target.selection_known
    assert sealed.target.selection == 'Copied public text' and sealed.target.field_id == pending.target.field_id
    assert not sealed.target.before_caret and not sealed.target.after_caret and not reader.reads
    assert provider.verify_selection(sealed) == 'copy_only'


def test_foreground_change_after_seal_never_returns_the_copied_text(owner):
    uia, reader = owner
    api = Api()
    provider = ForegroundContextProvider(api=api, uia=uia)
    pending = provider.capture_selection(allow_copy=True)
    original = uia.seal_copy
    def changed(*args):
        sealed = original(*args)
        api.foreground = lambda: 456
        return sealed
    uia.seal_copy = changed
    result = provider.seal_copy(pending, 'Public')
    assert result.selection.status == 'focus_changed' and not result.selection.text
    assert not result.target.selection_known and not reader.reads
