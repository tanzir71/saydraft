"""Selection requests share the bounded owner, using synthetic providers only."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import time

import pytest

from saydraft.context.focused_edit import FocusedEdit
from saydraft.context.foreground import ForegroundContextProvider, SelectedContext
from saydraft.context.selection import SelectionSnapshot
from saydraft.context.uia_worker import BoundedUIA
from tests.test_foreground_context import Api
from tests.test_selection import SelectionReader


@pytest.fixture
def owned():
    reader = SelectionReader()
    owner = BoundedUIA(factory=lambda: reader, capture_timeout=.5)
    try:
        yield owner, reader
    finally:
        owner.close()
        assert owner.wait_closed(2)


def test_context_and_selection_use_one_owner_with_scoped_generation_retirement(owned):
    owner, reader = owned
    first = owner.capture_selection(123, 42)
    assert first.status == "ready" and first.generation > 0
    assert owner.query(123, include_text=False).status == "ok"
    assert owner.verify_selection(first) == ""
    second = owner.capture_selection(123, 42)
    assert second.generation > first.generation and second.ticket != first.ticket
    assert not owner.cancel_selection(first) and owner.verify_selection(second) == ""
    assert owner.cancel_selection(second) and owner.verify_selection(second) == "selection_expired"
    assert reader.anchor_released.wait(1)
    assert {row[3] for row in reader.reads} == {owner._thread.ident}
    assert all(thread == owner._thread.ident for _, thread in reader.released)


def test_expiry_releases_the_anchor_without_polling_or_reading_more_text(owned):
    owner, reader = owned
    snapshot = owner.capture_selection(123, 42, lease_seconds=.03)
    assert snapshot.status == "ready"
    before = len(reader.reads)
    assert reader.anchor_released.wait(1)
    assert len(reader.reads) == before and owner.verify_selection(snapshot) == "selection_expired"


@pytest.mark.parametrize("close", [False, True])
def test_cancel_or_close_wakes_the_caller_and_drops_a_blocked_late_read(close):
    entered, release = threading.Event(), threading.Event()
    reader = SelectionReader()
    original = reader.selection_text
    def blocked(*args):
        entered.set()
        assert release.wait(3)
        return original(*args)
    reader.selection_text = blocked
    owner = BoundedUIA(factory=lambda: reader, capture_timeout=.5)
    try:
        with ThreadPoolExecutor(max_workers=1) as caller:
            pending = caller.submit(owner.capture_selection, 123, 42)
            assert entered.wait(1)
            if close:
                assert not owner.close()
            else:
                assert owner.cancel_selection()
            assert pending.result(timeout=.3) == SelectionSnapshot()
            assert owner.query(123) == FocusedEdit()  # No replacement owner while provider is blocked.
            release.set()
    finally:
        release.set()
        owner.close()
        assert owner.wait_closed(2)
    assert len(reader.reads) == 1
    assert reader.closed == [owner._thread.ident]
    assert all(thread == owner._thread.ident for _, thread in reader.released)


def test_a_ready_result_that_expires_before_consumption_is_revoked(monkeypatch):
    import saydraft.context.uia_worker as module
    real_request = module._Request
    class LateReceive(threading.Event):
        def wait(self, timeout=None):
            result = super().wait(timeout)
            time.sleep(.15)
            return result
    def request(*args, **options):
        value = real_request(*args, **options)
        value.done = LateReceive()
        return value
    monkeypatch.setattr(module, "_Request", request)
    reader = SelectionReader()
    owner = BoundedUIA(factory=lambda: reader, capture_timeout=.1)
    try:
        assert owner.capture_selection(123, 42) == SelectionSnapshot()
        assert reader.anchor_released.wait(1) and owner._selection_epoch == 2
    finally:
        owner.close()
        assert owner.wait_closed(2)


def test_cancellation_during_verification_cannot_publish_a_late_permission(owned):
    owner, reader = owned
    captured = owner.capture_selection(123, 42)
    entered, release = threading.Event(), threading.Event()
    original = reader.selection_text
    def blocked(*args):
        entered.set()
        assert release.wait(3)
        return original(*args)
    reader.selection_text = blocked
    try:
        with ThreadPoolExecutor(max_workers=1) as caller:
            pending = caller.submit(owner.verify_selection, captured)
            assert entered.wait(1)
            assert owner.cancel_selection(captured)
            assert pending.result(timeout=.3) == "field_unavailable"
            release.set()
    finally:
        release.set()
    assert reader.anchor_released.wait(1)
    assert owner.verify_selection(captured) == "selection_expired"


def test_foreground_bridge_returns_only_complete_selection_and_rechecks_after_query(owned):
    owner, reader = owned
    reader.document = "😀" * 1000
    reader.end = len(reader.document)
    api = Api()
    provider = ForegroundContextProvider(api=api, uia=owner)
    captured = provider.capture_selection()
    assert captured.selection.status == "ready" and captured.target.selection == reader.document
    assert captured.target.selection_known and not captured.target.selection_truncated
    assert captured.target.before_caret == captured.target.after_caret == ""
    assert not captured.target.before_caret_known and not captured.target.after_caret_known
    assert provider.verify_selection(captured) == ""
    original = owner.verify_selection
    def changed(*args, **options):
        result = original(*args, **options)
        api.foreground = lambda: 456
        return result
    owner.verify_selection = changed
    assert provider.verify_selection(captured) == "focus_changed"


def test_unsupported_selection_keeps_verified_metadata_for_the_future_copy_fallback(owned):
    owner, reader = owned
    reader.supported = False
    provider = ForegroundContextProvider(api=Api(), uia=owner)
    captured = provider.capture_selection()
    assert captured.selection.status == "unsupported"
    assert captured.target.uia_status == "ok" and captured.target.field_id
    assert not captured.target.selection_known and not captured.target.selection and not reader.reads
    assert provider.verify(captured.target) == "" and provider.verify_selection(captured) == "selection_expired"


def test_capture_race_and_malformed_target_cannot_reuse_a_ready_selection(owned):
    owner, reader = owned
    api = Api()
    provider = ForegroundContextProvider(api=api, uia=owner)
    captured = provider.capture_selection()
    reads = len(reader.reads)
    bad = replace(captured, target=replace(captured.target, selection="different"))
    assert provider.verify_selection(bad) == "field_unavailable" and len(reader.reads) == reads
    assert provider.verify_selection(captured) == "selection_expired"
    original = owner.capture_selection
    def changed(*args, **options):
        result = original(*args, **options)
        api.foreground = lambda: 456
        return result
    owner.capture_selection = changed
    assert provider.capture_selection() == SelectedContext()


@pytest.mark.parametrize("snapshot", [None, SelectionSnapshot(), SelectionSnapshot(identity="bad")])
def test_malformed_or_unknown_snapshot_never_reads_a_field(owned, snapshot):
    owner, reader = owned
    assert owner.verify_selection(snapshot) == "selection_expired" and not reader.reads


def test_disabled_context_never_constructs_a_native_foreground_reader():
    provider = ForegroundContextProvider()
    provider._native = lambda: pytest.fail("Disabled selection support touched native APIs")
    assert provider.capture_selection() == SelectedContext()
    assert provider.verify_selection(SelectedContext()) == "field_unavailable"
