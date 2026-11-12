import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from saydraft.context.focused_edit import FocusedEdit
from saydraft.context.uia_worker import BoundedUIA
from tests.test_focused_edit import Reader


def test_one_owner_creates_reads_and_closes_proxies_with_metadata_only_verification():
    calls = []
    class Owned(Reader):
        def __init__(self):
            calls.append(("create", threading.get_ident()))

        def text_context(self, *args):
            calls.append(("text", threading.get_ident()))
            return super().text_context(*args)

        def close(self):
            calls.append(("close", threading.get_ident()))
    owner = BoundedUIA(factory=Owned)
    try:
        assert owner.query(123).before_caret == "Before caret "
        result = owner.query(123, include_text=False)
        assert result.status == "ok" and result.before_caret == result.selection == ""
        assert owner._request is None
    finally:
        owner.close()
        assert owner.wait_closed(2)
    assert [name for name, _ in calls] == ["create", "text", "close"]
    assert len({thread for _, thread in calls}) == 1 and calls[0][1] != threading.get_ident()


@pytest.mark.parametrize("shutdown", [False, True])
def test_timeout_or_close_returns_before_provider_and_never_starts_extra_workers_or_late_text(shutdown):
    entered, release = threading.Event(), threading.Event()
    created, reads, closed = [], [], []
    class Blocked(Reader):
        def __init__(self):
            created.append(threading.get_ident())

        def focused_element(self):
            entered.set()
            assert release.wait(5)
            return super().focused_element()

        def text_context(self, *args):
            reads.append(True)
            return super().text_context(*args)

        def close(self):
            closed.append(threading.get_ident())
    owner = BoundedUIA(factory=Blocked, timeout=.5 if shutdown else .03)
    try:
        with ThreadPoolExecutor(max_workers=1) as caller:
            future = caller.submit(owner.query, 123)
            try:
                assert entered.wait(2)
                if shutdown:
                    assert not owner.close()
                assert future.result(timeout=1) == FocusedEdit()
                assert owner.query(123) == FocusedEdit() and len(created) == 1
                assert not owner.close() and not owner.wait_closed(.01)
            finally:
                release.set()
    finally:
        release.set()
        owner.close()
        assert owner.wait_closed(2)
    assert not reads and created == closed


def test_initialization_failure_is_terminal_without_retries_or_exception_logging(caplog):
    attempts = []
    def failed():
        attempts.append(True)
        raise OSError("Public failure must not reach logs")
    owner = BoundedUIA(factory=failed)
    assert owner.wait_closed(2)
    assert owner.query(123) == owner.query(123) == FocusedEdit()
    assert attempts == [True] and not caplog.records and owner.close()


def test_expired_initialization_request_never_reads_a_field_after_shutdown():
    entered, release = threading.Event(), threading.Event()
    reads = []
    class Owned(Reader):
        def focused_element(self):
            reads.append(True)
            return super().focused_element()

        def close(self):
            pass
    def factory():
        entered.set()
        assert release.wait(5)
        return Owned()
    owner = BoundedUIA(factory=factory, timeout=.02)
    try:
        assert entered.wait(2)
        assert owner.query(123) == FocusedEdit()
        owner.close()
    finally:
        release.set()
        owner.close()
        assert owner.wait_closed(2)
    assert not reads


@pytest.mark.parametrize("window", [0, None, "123", True])
def test_invalid_window_never_reaches_the_provider(window):
    class NoRead(Reader):
        def focused_element(self):
            pytest.fail("No field read authorized")

        def close(self):
            pass
    owner = BoundedUIA(factory=NoRead)
    try:
        assert owner.query(window) == FocusedEdit()
    finally:
        owner.close()
        assert owner.wait_closed(2)


def test_capture_budget_can_differ_from_metadata_without_changing_single_owner_lifetime():
    class Owned(Reader):
        def close(self):
            pass
    owner = BoundedUIA(factory=Owned, timeout=.2, capture_timeout=.5)
    try:
        assert owner.timeout == .2 and owner.capture_timeout == .5
        assert owner.query(123).status == owner.query(123, include_text=False).status == "ok"
    finally:
        owner.close()
        assert owner.wait_closed(2)


@pytest.mark.parametrize("budget", [0, .6, True, float("nan")])
def test_invalid_capture_budget_cannot_start_an_owner(budget):
    with pytest.raises(ValueError):
        BoundedUIA(factory=lambda: pytest.fail("No owner may start"), capture_timeout=budget)
