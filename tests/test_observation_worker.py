import threading
import weakref
from types import SimpleNamespace as NS

import pytest

from saydraft.context.observation_worker import ObservationWorker
from saydraft.context.tracked_edit import ObservedEdit
from saydraft.context.uia_worker import BoundedUIA
from saydraft.context.foreground import ForegroundContextProvider
from saydraft.core.interfaces import TargetContext
from tests.test_tracked_edit import KEY, Reader
from tests.test_focused_edit import Reader as FocusedReader
from tests.test_foreground_context import Api


@pytest.fixture
def rig():
    clock, calls, owners = NS(now=0), [], []
    class Owned(Reader):
        def __init__(self):
            super().__init__()
            calls.append(("create", threading.get_ident()))

        def close(self):
            calls.append(("close", threading.get_ident()))
    def create(reader=None):
        ready = threading.Event()
        store = NS()
        def factory():
            store.reader = reader or Owned()
            ready.set()
            return store.reader
        owner = ObservationWorker(factory=factory, clock=lambda: clock.now)
        owners.append(owner)
        assert ready.wait(2)
        return owner, store.reader
    yield NS(create=create, clock=clock, calls=calls)
    for owner in owners:
        owner.close()
        assert owner.wait_closed(3)


def prepared(owner, lease=1260):
    ticket = owner.prepare(KEY, lease_seconds=lease)
    assert ticket is not None and ticket.ready.wait(2) and owner.reserve(ticket)
    return ticket


@pytest.mark.parametrize("early,leave", [(False, False), (False, True), (True, False)])
def test_prepare_while_speaking_reserve_before_paste_then_background_result(rig, early, leave):
    owner, reader = rig.create()
    ticket = prepared(owner)
    reader.text = "Before 🙂 " + ("Kubernetes" if early else "Kubernetis") + " after."
    assert owner.commit(ticket, "Kubernetis")  # A successful OS insertion has completed.
    assert ticket.active.wait(2)
    if not early:
        reads = reader.reads
        reader.text = "Before 🙂 Kubernetes after."
        rig.clock.now = 15 if not leave else 1
        reader.focus = not leave
        owner._wake.set()
        assert ticket.done.wait(2) and reader.reads == reads + 1
    assert owner.take(ticket) == ObservedEdit("Kubernetis", "Kubernetes")
    assert owner.take(ticket) is None


def test_pending_preparation_lease_handles_long_recording_but_watch_starts_at_insertion(rig):
    owner, reader = rig.create()
    ticket = owner.prepare(KEY, lease_seconds=1260)
    assert ticket.ready.wait(2)
    rig.clock.now = 1200
    assert owner.reserve(ticket)
    reader.text = "Before 🙂 Kubernetis after."
    assert owner.commit(ticket, "Kubernetis") and ticket.active.wait(2)
    rig.clock.now = 1214.9
    owner._wake.set()
    assert not ticket.done.wait(.05)
    rig.clock.now = 1215
    owner._wake.set()
    assert ticket.done.wait(2)
    assert owner.take(ticket) == ObservedEdit("Kubernetis", "Kubernetis")


@pytest.mark.parametrize("action", ["reserve", "cancel", "close", "expire"])
def test_blocked_preparation_cannot_capture_after_delivery_or_cancellation(rig, action):
    entered, release = threading.Event(), threading.Event()
    reader = Reader()
    def blocked(element, limit, current):
        entered.set()
        assert release.wait(3)
        if current():
            pytest.fail("Late text read after abandoned preparation")
        return None
    reader.insertion_edges, reader.close = blocked, lambda: None
    owner, _ = rig.create(reader)
    ticket = owner.prepare(KEY)
    try:
        assert entered.wait(2)
        if action == "reserve":
            assert not owner.reserve(ticket)  # Delivery proceeds without learning.
        elif action == "cancel":
            owner.cancel(ticket)
        elif action == "close":
            assert not owner.close() and not owner.wait_closed(.01)
        else:
            rig.clock.now = 3  # Two-second preparation budget.
        assert not owner.commit(ticket, "Kubernetis")
    finally:
        release.set()
    assert ticket.done.wait(2) and owner.take(ticket) is None


def test_learning_block_does_not_occupy_the_critical_metadata_owner(rig):
    entered, release = threading.Event(), threading.Event()
    reader = Reader()
    def blocked(*args):
        entered.set()
        assert release.wait(3)
        return None
    reader.insertion_edges, reader.close = blocked, lambda: None
    observation, _ = rig.create(reader)
    class Metadata(FocusedReader):
        def close(self):
            pass
    critical = BoundedUIA(factory=Metadata)
    try:
        observation.prepare(KEY)
        assert entered.wait(2)
        assert critical.query(KEY.window, include_text=False).status == "ok"
        assert critical._thread.ident != observation._thread.ident
    finally:
        release.set()
        critical.close()
        assert critical.wait_closed(2)


def test_old_tickets_and_payloads_cannot_mutate_the_new_scope(rig):
    owner, reader = rig.create()
    old = prepared(owner)
    new = owner.prepare(KEY)
    assert new.ready.wait(2)
    owner.cancel(old)
    assert not owner.commit(old, "secret") and owner.take(old) is None
    assert owner.reserve(new)
    reader.text = "Before 🙂 Kubernetis after."
    assert owner.commit(new, "Kubernetis") and new.active.wait(2)
    owner.cancel(new)
    assert new.done.wait(2) and owner.take(new) is None


@pytest.mark.parametrize("text", ["", None, "x" * 4097, "\ud800"])
def test_invalid_payload_or_commit_without_reservation_does_not_read(rig, text):
    owner, reader = rig.create()
    ticket = prepared(owner)
    reads = reader.reads
    assert not owner.commit(ticket, text) and owner.take(ticket) is None
    assert reader.reads == reads
    fresh = owner.prepare(KEY)
    assert fresh.ready.wait(2)
    assert not owner.commit(fresh, "Kubernetis") and fresh.done.is_set()


@pytest.mark.parametrize("lease", [0, True, 3661, float("nan")])
def test_invalid_preparation_limits_are_refused(rig, lease):
    owner, reader = rig.create()
    assert owner.prepare(KEY, lease_seconds=lease) is None and reader.reads == 0


def test_completion_retention_is_bounded_and_mta_closes_on_its_creator(rig):
    owner, reader = rig.create()
    ticket = prepared(owner)
    reader.text = "Before 🙂 Kubernetes after."
    assert owner.commit(ticket, "Kubernetis") and ticket.done.wait(2)
    rig.clock.now = 31
    owner._wake.set()
    assert owner.take(ticket) is None
    owner.close()
    assert owner.wait_closed(2)
    assert [name for name, _ in rig.calls] == ["create", "close"]
    assert len({thread for _, thread in rig.calls}) == 1
    assert rig.calls[0][1] != threading.get_ident()


def test_idle_owner_does_not_keep_a_consumed_result_alive(rig):
    owner, reader = rig.create()
    ticket = prepared(owner)
    reader.text = "Before 🙂 Kubernetes after."
    assert owner.commit(ticket, "Kubernetis") and ticket.done.wait(2)
    result = owner.take(ticket)
    assert result == ObservedEdit("Kubernetis", "Kubernetes")
    reference = weakref.ref(result)
    del result
    assert reference() is None


def test_factory_failure_is_terminal_and_never_logged_or_replaced(caplog):
    attempts = []
    def fail():
        attempts.append(True)
        raise RuntimeError("sensitive provider failure")
    owner = ObservationWorker(factory=fail)
    assert owner.wait_closed(2) and owner.prepare(KEY) is None and owner.close()
    assert attempts == [True] and not caplog.records


def test_expired_initialization_never_reads_late_or_spawns_another_owner():
    entered, release = threading.Event(), threading.Event()
    clock, attempts, reader = NS(now=0), [], Reader()
    reader.close = lambda: None
    def factory():
        attempts.append(True)
        entered.set()
        assert release.wait(3)
        return reader
    owner = ObservationWorker(factory=factory, clock=lambda: clock.now)
    try:
        assert entered.wait(2)
        ticket = owner.prepare(KEY)
        clock.now = 3
        release.set()
        assert ticket.done.wait(2) and reader.reads == 0
        assert owner.take(ticket) is None and attempts == [True]
    finally:
        release.set()
        owner.close()
        assert owner.wait_closed(2)


def test_context_routes_learning_without_changing_critical_queries_and_closes_both(rig):
    owner, reader = rig.create()
    closed = []
    uia = NS(query=lambda *a, **kw: NS(status="ok"), close=lambda: closed.append(True) or True)
    context = ForegroundContextProvider(api=Api(), uia=uia, observation=owner)
    target = TargetContext(focus=KEY.window, process_id=KEY.process_id, field_id=KEY.runtime_id, uia_status="ok")
    ticket = context.prepare_observation(target)
    assert ticket.ready.wait(2) and context.reserve_observation(ticket)
    reader.text = "Before 🙂 Kubernetes after."
    assert context.commit_observation(ticket, "Kubernetis") and ticket.done.wait(2)
    assert context.take_observation(ticket) == ObservedEdit("Kubernetis", "Kubernetes")
    context.close()
    assert owner.wait_closed(2) and closed == [True]
    assert context.prepare_observation(target) is None and not context.reserve_observation(ticket)
