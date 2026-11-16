"""Optional provider text must not block normal paste or weaken field guards."""

from dataclasses import replace
import threading
from saydraft.context.focused_edit import FocusedEdit
from saydraft.context.foreground import ForegroundContextProvider
from saydraft.context.uia_worker import BoundedUIA
from tests.test_foreground_context import Api
from tests.test_focused_edit import Reader


def test_stalled_optional_text_keeps_fresh_metadata_delivery_and_password_refusal():
    entered, release = threading.Event(), threading.Event()
    password = [False]

    class Metadata(Reader):
        def password(self, element):
            return password[0]

        def close(self):
            pass

    class Text(Reader):
        def text_context(self, *args):
            entered.set()
            assert release.wait(3)
            return "Public prefix", "Public selection"

        def close(self):
            pass

    required = BoundedUIA(factory=Metadata, timeout=0.2)
    optional = BoundedUIA(factory=Text, timeout=0.03, capture_timeout=0.03)
    provider = ForegroundContextProvider(api=Api(), uia=required, text_uia=optional)
    try:
        target = provider.capture()
        assert entered.wait(1) and target.uia_status == "ok"
        assert not target.before_caret_known and target.before_caret == ""
        assert provider.verify(target) == ""
        # A second dictation must not spawn a second blocked text worker.
        assert provider.capture().field_id == target.field_id
        password[0] = True
        assert provider.verify(target) == "password_field"
    finally:
        release.set()
        provider.close()
        assert required.wait_closed(2) and optional.wait_closed(2)


def test_optional_context_for_another_field_never_changes_captured_identity():
    class Port:
        def __init__(self, result):
            self.result = result

        def query(self, *args, **kwargs):
            return self.result

        def close(self):
            return True

    metadata = FocusedEdit("ok", False, 50004, runtime_id=(1, 2, 3))
    context = replace(
        metadata, runtime_id=(9, 9), before_caret="Unrelated", before_caret_known=True
    )
    provider = ForegroundContextProvider(
        api=Api(), uia=Port(metadata), text_uia=Port(context)
    )
    target = provider.capture()
    assert target.field_id == (1, 2, 3) and target.before_caret == ""
    provider.close()


def test_optional_password_observation_remains_a_hard_refusal():
    class Port:
        def __init__(self, result):
            self.result = result

        def query(self, *args, **kwargs):
            return self.result

        def close(self):
            return True

    metadata = FocusedEdit("ok", False, 50004, runtime_id=(1, 2, 3))
    provider = ForegroundContextProvider(
        api=Api(), uia=Port(metadata), text_uia=Port(FocusedEdit("password", True))
    )
    target = provider.capture()
    assert target.is_password and provider.verify(target) == "password_field"
    provider.close()
