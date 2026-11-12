"""Exercise the app adapter with native transaction semantics and no OS input."""

import builtins
from dataclasses import replace
from types import SimpleNamespace

import pytest

from saydraft.insert.clipboard_win import WindowsClipboard
from saydraft.insert.inserter import Inserter
from tests.test_clipboard_transactions import Api
from tests.test_inserter import FakeKeyboard


def adapter(*, api=None, keyboard=None, guard=lambda target: "", sleep=lambda delay: None):
    api = api or Api()
    clipboard = WindowsClipboard(api_factory=lambda: api)
    keyboard = keyboard or FakeKeyboard()
    return Inserter(clipboard=clipboard, keyboard=keyboard, delivery_guard=guard,
                    focus_provider=lambda: 123, sleep=sleep), api, keyboard


def test_windows_default_is_native_and_does_not_import_pyperclip(monkeypatch):
    original = builtins.__import__
    def checked(name, *args, **kwargs):
        assert name != "pyperclip"
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", checked)
    monkeypatch.setattr("saydraft.insert.inserter.sys.platform", "win32")
    assert isinstance(Inserter().clipboard, WindowsClipboard)


def test_paste_sees_private_text_once_and_all_original_formats_are_restored_before_enter():
    inserter, api, keyboard = adapter()
    original, send = api.data(), keyboard.send
    def observed(key):
        if key == "ctrl+v":
            assert api.data() == [(format, bytes(4)) for format in api.privacy] + [
                (13, "fixture\0".encode("utf-16-le"))]
        else:
            assert key == "enter" and api.data() == original
        send(key)
    keyboard.send = observed
    result = inserter.insert_text("fixture", start_focus=123, send_enter=True)
    assert result.status == "inserted" and result.method == "paste" and result.enter_sent
    assert not result.clipboard_pending and api.data() == original
    assert keyboard.ops == [("send", "ctrl+v"), ("send", "enter")]
    api.assert_retired()


@pytest.mark.parametrize("failure", ["opaque", "oversize", "unrendered", "busy"])
def test_uncapturable_clipboard_uses_guarded_typing_without_changing_original(failure):
    inserter, api, keyboard = adapter()
    if failure == "opaque":
        api.clip[0] = (0x200, api.clip[0][1])
    elif failure == "oversize":
        api.sizes = {8: 64 * 1024 * 1024}
    elif failure == "unrendered":
        api.no_render = set(api.formats())
    else:
        api.busy = True
    original = api.data()
    result = inserter.insert_text("fixture", start_focus=123)
    assert result.status == "inserted" and result.method == "typing" and result.reason == "clipboard_unavailable"
    assert keyboard.ops == [("write", "fixture")] and api.data() == original
    api.assert_retired()


@pytest.mark.parametrize("phase", [2, 3])
def test_guard_rechecked_after_snapshot_and_before_paste_blocks_all_input(phase):
    reasons = iter([""] * (phase - 1) + ["focus_changed"])
    inserter, api, keyboard = adapter(guard=lambda target: next(reasons))
    original = api.data()
    result = inserter.insert_text("fixture", start_focus=123)
    assert result.status == "skipped_focus_changed" and not keyboard.ops and api.data() == original
    api.assert_retired()


def test_typing_fallback_rechecks_target_and_refuses_newly_held_modifiers():
    reasons = iter(("", "modifier_held"))
    inserter, api, keyboard = adapter(guard=lambda target: next(reasons))
    api.busy = True
    result = inserter.insert_text("fixture", start_focus=123)
    assert result.status == "not_inserted" and result.reason == "modifier_held" and not keyboard.ops
    api.assert_retired()


def test_changed_clipboard_before_paste_is_preserved_and_never_typed_again():
    inserter, api, keyboard = adapter()
    def new_copy(delay):
        with api.opened(999):
            api.empty()
            api.put(api.memory(13, b"new copy"))
    inserter.sleep = new_copy
    result = inserter.insert_text("fixture", start_focus=123)
    assert result.status == "not_inserted" and result.reason == "clipboard_changed"
    assert not keyboard.ops and api.data() == [(13, b"new copy")]
    api.assert_retired()


def test_failed_paste_is_unconfirmed_and_never_retried_by_typing():
    inserter, api, keyboard = adapter()
    original = api.data()
    def failed(key):
        keyboard.ops.append(("send", key))
        raise OSError("partial input")
    keyboard.send = failed
    result = inserter.insert_text("fixture", start_focus=123)
    assert result.status == "not_inserted" and result.reason == "insertion_unconfirmed"
    assert keyboard.ops == [("send", "ctrl+v")] and api.data() == original
    api.assert_retired()


def test_pending_restore_keeps_history_explains_recovery_and_skips_enter():
    from saydraft.core.interfaces import TargetContext
    from saydraft.dictation import DictationContext
    from tests.test_processing import make_processor
    inserter, api, keyboard = adapter()
    original = api.data()
    def sent(key):
        keyboard.ops.append(("send", key))
        api.busy = True
    keyboard.send = sent
    processor, events, notifications = make_processor(inserter=inserter)
    processor.voice_enter_enabled = True
    result = processor.process("words press enter", target=TargetContext(123, "Editor"),
        context=DictationContext(mode="balanced", profile="chat", app_group="messaging"), model="base")
    assert events[0][0] == "history" and result.history_id == 1
    assert result.insertion.status == "inserted" and result.insertion.clipboard_pending
    assert not result.insertion.enter_sent and events[0][1].raw_text == "words press enter"
    assert any("Restore clipboard" in notice for notice in notifications)
    assert keyboard.ops == [("send", "ctrl+v")]
    api.busy = False
    assert inserter.close() and api.data() == original
    api.assert_retired()


def test_explicit_history_copy_uses_privacy_flags_replaces_opaque_data_and_discards_pending():
    inserter, api, keyboard = adapter()
    with inserter.clipboard.temporary_text("fixture"):
        api.busy = True
    assert inserter.clipboard.pending is not None
    api.busy = False
    api.clip[0] = (0x200, api.clip[0][1])
    inserter.clipboard.setText("History copy")
    assert api.data() == [(format, bytes(4)) for format in api.privacy] + [
        (13, "History copy\0".encode("utf-16-le"))]
    assert inserter.clipboard.pending is None and not keyboard.ops
    api.assert_retired()


def test_history_window_shared_recovery_and_copy_errors_are_visible(tmp_path):
    from saydraft.ui.history_window import HistoryWindow
    from tests.test_history_window import build_history, qt_modules
    inserter, api, _keyboard = adapter()
    original = api.data()
    with inserter.clipboard.temporary_text("fixture"):
        api.busy = True
    window = HistoryWindow(qt_modules=qt_modules(), store=build_history(tmp_path), clipboard=inserter.clipboard)
    assert window.restore_clipboard_button.isEnabled()
    assert not window.copy_current_text() and "Could not copy" in window.status_label.text()
    assert not window.restore_clipboard()
    api.busy = False
    assert window.restore_clipboard() and api.data() == original
    assert not window.restore_clipboard_button.isEnabled()
    assert window.copy_current_text()
    assert api.data()[-1] == (13, (window.current_text() + "\0").encode("utf-16-le"))
    window.close()
    api.assert_retired()


def test_settings_reuses_the_clipboard_port_and_shutdown_attempts_recovery():
    from tests.test_session_worker import make_worker
    from tests.test_processing import make_processor
    worker, *_ = make_worker()
    clipboard = SimpleNamespace(close=lambda: True)
    old_inserter = Inserter(clipboard=clipboard, keyboard=FakeKeyboard())
    worker.services.inserter = old_inserter
    new_inserter = Inserter(clipboard=object(), keyboard=FakeKeyboard())
    processor, *_ = make_processor(inserter=new_inserter)
    new_services = replace(worker.services, inserter=new_inserter, processor=processor)
    worker.services_factory = lambda *args, **kwargs: new_services
    worker.configure(worker.services.config)
    assert worker.services.inserter.clipboard is clipboard
    calls = []
    clipboard.close = lambda: calls.append(True) or True
    worker.shutdown()
    assert calls == [True]
