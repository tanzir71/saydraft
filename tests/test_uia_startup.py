import threading

import pytest

from saydraft.context.uia_startup import verify_initialization
from saydraft.context.uia_startup import field_metadata


def test_package_check_initializes_and_closes_on_one_worker_without_querying_fields():
    calls = []

    class Reader:
        def __init__(self):
            calls.append(("create", threading.get_ident()))

        def close(self):
            calls.append(("close", threading.get_ident()))

        def focused_element(self):
            pytest.fail("Initialization must not acquire any field")

    assert verify_initialization(factory=Reader)
    assert [name for name, _ in calls] == ["create", "close"]
    assert calls[0][1] == calls[1][1] != threading.get_ident()


def test_failed_initialization_blocks_package_without_provider_error_details():
    def failed():
        raise OSError("Private provider failure detail")

    with pytest.raises(RuntimeError, match="^Windows field verification could not initialize$"):
        verify_initialization(factory=failed)


def test_timed_out_initialization_retires_its_reader_on_the_original_worker():
    release, closed = threading.Event(), threading.Event()

    class Reader:
        def __init__(self):
            assert release.wait(3)

        def close(self):
            closed.set()

    try:
        with pytest.raises(RuntimeError):
            verify_initialization(factory=Reader, timeout=.01)
    finally:
        release.set()
    assert closed.wait(2)


def test_explicit_field_diagnostic_returns_metadata_without_reading_text():
    from tests.test_focused_edit import Reader

    class MetadataOnly(Reader):
        def text_context(self, *args):
            pytest.fail("The diagnostic must never read text")

        def close(self):
            pass

    assert field_metadata(123, factory=MetadataOnly) == dict(
        status="ok", is_password=False, control_type=50004, identity_length=3)
