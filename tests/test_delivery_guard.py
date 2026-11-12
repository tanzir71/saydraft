"""Delivery refusal must happen before changing the clipboard or injecting keys."""

import ctypes as ct
from types import SimpleNamespace

import pytest

from saydraft.insert.guards_win import NativeDeliveryApi, SidAttributes, WindowsDeliveryGuard, integrity_rid
from saydraft.insert.inserter import Inserter
from tests.test_inserter import FakeClipboard, FakeKeyboard


class Api:
    def __init__(self, *, own=8192, target=8192, held=False, foreground=(123, 123), pids=(7, 7)):
        self.own, self.target, self.held = own, target, held
        self.windows, self.pids = iter(foreground), iter(pids)

    def foreground(self):
        return next(self.windows)

    def window_pid(self, window):
        assert window == 123
        return next(self.pids)

    def integrity(self, pid=None):
        return self.own if pid is None else self.target

    def modifiers_down(self):
        return self.held


@pytest.mark.parametrize("target", [None, True, 0, -1, "123"])
def test_unknown_targets_are_refused_without_querying_os(target):
    assert WindowsDeliveryGuard(Api())(target) == "unknown_target"


@pytest.mark.parametrize("options,reason", [({}, ""), ({"own": 12288}, ""),
    ({"target": 12288}, "target_elevated"), ({"held": True}, "modifier_held"),
    ({"foreground": (456,)}, "focus_changed"), ({"foreground": (123, 456)}, "focus_changed"),
    ({"pids": (7, 8)}, "focus_changed")])
def test_integrity_modifier_and_target_checks(options, reason):
    assert WindowsDeliveryGuard(Api(**options))(123) == reason


def test_inaccessible_token_is_not_assumed_to_be_lower_integrity():
    api = Api()
    api.integrity = lambda pid=None: (_ for _ in ()).throw(OSError("access denied"))
    assert WindowsDeliveryGuard(api)(123) == "integrity_unavailable"


@pytest.mark.parametrize("reason", ["target_elevated", "integrity_unavailable", "modifier_held"])
@pytest.mark.parametrize("typing", [False, True])
def test_blocked_delivery_does_not_touch_clipboard_type_or_paste(reason, typing):
    clipboard, keyboard = FakeClipboard(), FakeKeyboard()
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
        profiles=[{"match": "Editor", "insertion": "typing"}] if typing else [],
        delivery_guard=lambda target: reason, sleep=lambda delay: None)
    result = inserter.insert_text("public fixture", start_focus=123, app_title="Editor")
    assert result.status == "not_inserted" and result.reason == reason
    assert not clipboard.ops and not keyboard.ops


def test_pre_paste_guard_failure_restores_clipboard_and_sends_no_keys():
    clipboard, keyboard = FakeClipboard("rich fixture represented by test port"), FakeKeyboard()
    reasons = iter(("", "modifier_held"))
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
        delivery_guard=lambda target: next(reasons), sleep=lambda delay: None)
    result = inserter.insert_text("fixture", start_focus=123)
    assert result.reason == "modifier_held" and result.status == "not_inserted"
    assert clipboard.value == "rich fixture represented by test port" and not keyboard.ops


def test_guard_is_rechecked_before_trailing_enter_without_undoing_inserted_text():
    clipboard, keyboard = FakeClipboard(), FakeKeyboard()
    reasons = iter(("", "", "target_elevated"))
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
        delivery_guard=lambda target: next(reasons), sleep=lambda delay: None)
    result = inserter.insert_text("fixture", start_focus=123, send_enter=True)
    assert result.status == "inserted" and result.reason == "enter_target_elevated" and not result.enter_sent
    assert keyboard.ops == [("send", "ctrl+v")]


def test_native_adapter_installs_guard_while_injected_keyboard_keeps_explicit_test_port(monkeypatch):
    monkeypatch.setattr("saydraft.insert.inserter.sys.platform", "win32")
    assert isinstance(Inserter().delivery_guard, WindowsDeliveryGuard)
    assert Inserter(keyboard=FakeKeyboard()).delivery_guard is None


@pytest.mark.parametrize("reason,notice", [("target_elevated", "admin window"),
    ("modifier_held", "Release Ctrl, Win, Alt and Shift"), ("integrity_unavailable", "could not be checked")])
def test_refusal_keeps_both_versions_in_history_and_explains_delivery_reason(reason, notice):
    from saydraft.core.interfaces import TargetContext
    from tests.test_processing import make_processor, process
    clipboard, keyboard = FakeClipboard(), FakeKeyboard()
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
        delivery_guard=lambda target: reason)
    processor, events, notifications = make_processor(inserter=inserter)
    result = process(processor, target=TargetContext(123, "Editor"))
    assert [event[0] for event in events] == ["history"] and result.history_id == 1
    assert events[0][1].raw_text == "words" and events[0][1].cleaned_text == "clean words"
    assert result.insertion.reason == reason and result.insertion.status == "not_inserted"
    assert notice in notifications[0]
    assert not clipboard.ops and not keyboard.ops


def label_buffer(rid=8192):
    buffer = ct.create_string_buffer(128)
    offset = ct.sizeof(SidAttributes)
    SidAttributes.from_buffer(buffer).sid = ct.addressof(buffer) + offset
    data = b"\1\1\0\0\0\0\0\x10" + rid.to_bytes(4, "little")
    ct.memmove(ct.addressof(buffer) + offset, data, len(data))
    return buffer, offset + len(data)


def test_label_sid_bounds_authority_count_and_truncation_are_validated_before_read():
    buffer, length = label_buffer(12288)
    assert integrity_rid(buffer, length) == 12288
    for size in (0, length - 1, len(buffer) + 1):
        with pytest.raises(ValueError):
            integrity_rid(buffer, size)
    for pointer in (0, 1, ct.addressof(buffer) + len(buffer) + 1):
        SidAttributes.from_buffer(buffer).sid = pointer
        with pytest.raises(ValueError):
            integrity_rid(buffer, length)
    for offset, value in ((0, 2), (1, 0), (1, 255), (7, 5)):
        buffer, length = label_buffer()
        buffer[ct.sizeof(SidAttributes) + offset] = value
        with pytest.raises(ValueError):
            integrity_rid(buffer, length)


@pytest.mark.parametrize("failure", ["open", "token", "size", "query", "sid", None])
def test_native_query_closes_owned_process_and_token_handles_on_every_path(failure):
    closed = []
    api = NativeDeliveryApi.__new__(NativeDeliveryApi)
    def token(process, access, out):
        assert process == 100 and access == 8
        out._obj.value = 200
        return failure != "token"
    def information(handle, kind, buffer, capacity, required):
        assert handle.value == 200 and kind == 25
        required._obj.value = 128 if failure != "size" else 999999
        if buffer is None:
            return False
        if failure == "query":
            return False
        if failure != "sid":
            offset = ct.sizeof(SidAttributes)
            SidAttributes.from_buffer(buffer).sid = ct.addressof(buffer) + offset
            ct.memmove(ct.addressof(buffer) + offset, b"\1\1\0\0\0\0\0\x10\0\x20\0\0", 12)
        return True
    def open_process(access, inherit, pid):
        assert (access, inherit, pid) == (0x1000, False, 7)
        return None if failure == "open" else 100
    api.kernel = SimpleNamespace(OpenProcess=open_process, CloseHandle=lambda handle: closed.append(
        handle.value if hasattr(handle, "value") else handle))
    api.security = SimpleNamespace(OpenProcessToken=token, GetTokenInformation=information)
    if failure is None:
        assert api.integrity(7) == 8192
    else:
        with pytest.raises((OSError, ValueError)):
            api.integrity(7)
    assert closed == ([] if failure == "open" else [100] if failure == "token" else [200, 100])


def test_current_process_pseudo_handle_is_not_closed_and_key_state_uses_high_bit():
    api = NativeDeliveryApi.__new__(NativeDeliveryApi)
    closed = []
    api.kernel = SimpleNamespace(GetCurrentProcess=lambda: -1, CloseHandle=closed.append)
    api.security = SimpleNamespace(OpenProcessToken=lambda *args: False)
    with pytest.raises(OSError):
        api.integrity()
    assert not closed
    api.user = SimpleNamespace(GetAsyncKeyState=lambda key: 1)
    assert not api.modifiers_down()
    for held in (0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C):
        api.user.GetAsyncKeyState = lambda key: -32768 if key == held else 0
        assert api.modifiers_down()
