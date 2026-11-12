from dataclasses import replace

import pytest

from saydraft.context.focused_edit import FocusedEdit
from saydraft.context.foreground import ForegroundContextProvider
from saydraft.core.interfaces import TargetContext
from tests.test_foreground_context import Api


class UIA:
    def __init__(self):
        self.result = FocusedEdit("ok", False, 50004, "Before ", "Selection", (1, 2, 3), True)
        self.calls, self.closes = [], 0

    def query(self, window, *, include_text):
        self.calls.append((window, include_text))
        return self.result

    def close(self):
        self.closes += 1
        return True


def test_capture_copies_field_data_then_fresh_verification_requests_metadata_only():
    uia = UIA()
    provider = ForegroundContextProvider(api=Api(), uia=uia)
    target = provider.capture()
    assert target.uia_status == "ok" and target.process_id == 42 and target.control_type == 50004
    assert target.before_caret == "Before " and target.selection == "Selection"
    assert target.selection_truncated and target.field_id == (1, 2, 3)
    assert provider.verify(target) == "" and uia.calls == [(123, True), (123, False)]


@pytest.mark.parametrize("field,reason", [
    (FocusedEdit(status="password", is_password=True), "password_field"),
    (FocusedEdit(status="changed"), "focus_changed"),
    (FocusedEdit(), "field_unavailable"),
    (FocusedEdit("ok", False, 50004, runtime_id=(7, 8)), "focus_changed"),
])
def test_verification_refuses_password_unknown_or_changed_fields(field, reason):
    uia = UIA()
    provider = ForegroundContextProvider(api=Api(), uia=uia)
    target = provider.capture()
    uia.result = field
    assert provider.verify(target) == reason


@pytest.mark.parametrize("change", ["window", "pid"])
def test_capture_drops_context_if_foreground_changes_during_uia(change):
    uia, api = UIA(), Api()
    query = uia.query
    def changed(*args, **kwargs):
        if change == "window":
            api.foreground = lambda: 456
        else:
            api.window_pid = lambda window: 43
        return query(*args, **kwargs)
    uia.query = changed
    assert ForegroundContextProvider(api=api, uia=uia).capture() == TargetContext()


def test_closed_provider_cannot_start_or_verify_another_read():
    uia = UIA()
    provider = ForegroundContextProvider(api=Api(), uia=uia)
    target = provider.capture()
    provider.set_profiles([{"exe": "chrome.exe", "app_group": "code"}])
    assert provider.capture().app_group == "code"
    assert provider.close()
    assert provider.verify(target) == "field_unavailable" and len(uia.calls) == 2
    assert provider.capture() == TargetContext() and provider.focus() is None and len(uia.calls) == 2


def test_provider_failure_cannot_authorize_delivery_or_surface_exception(caplog):
    uia = UIA()
    def fail(*args, **kwargs):
        raise RuntimeError("Public provider failure")
    uia.query = fail
    provider = ForegroundContextProvider(api=Api(), uia=uia)
    target = provider.capture()
    assert target.uia_status == "unavailable" and provider.verify(target) == "field_unavailable"
    assert not caplog.records


def test_verification_checks_original_process_and_does_not_trust_unrequested_context():
    uia = UIA()
    provider = ForegroundContextProvider(api=Api(), uia=uia)
    target = provider.capture()
    assert provider.verify(replace(target, process_id=99)) == "focus_changed"
    assert provider.verify(replace(target, uia_status="not_requested")) == "field_unavailable"
    assert uia.calls == [(123, True)]
