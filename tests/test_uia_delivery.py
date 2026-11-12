import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from saydraft.context.focused_edit import FocusedEdit
from saydraft.context.foreground import ForegroundContextProvider
from saydraft.context.uia_worker import BoundedUIA
from saydraft.core.session import SessionState
from tests.test_focused_edit import Reader
from tests.test_foreground_context import Api as Foreground
from tests.test_native_clipboard_app import adapter
from tests.test_processing import make_processor
from tests.test_session_worker import make_worker
from tests.test_uia_context import UIA


def setup(*, queued=False):
    inserter, api, keyboard = adapter()
    processor, events, notices = make_processor(inserter=inserter)
    worker, clock, executor, *_ = make_worker(queued=queued, processor=(processor, events, notices))
    uia = UIA()
    worker.services.context = ForegroundContextProvider(api=Foreground(), uia=uia)
    return worker, clock, executor, uia, api, keyboard, events, notices


@pytest.mark.parametrize("status,password,reason", [
    ("password", True, "password_field"), ("unavailable", False, "field_unavailable"),
    ("changed", False, "focus_changed")])
def test_password_unknown_or_changed_capture_saves_both_versions_without_clipboard_or_keys(status, password, reason):
    worker, clock, _, uia, api, keyboard, events, notices = setup()
    original = api.data()
    uia.result = FocusedEdit(status=status, is_password=password)
    assert worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert worker.last_result.insertion.reason == reason
    assert [(event[1].raw_text, event[1].cleaned_text) for event in events] == [
        ("raw transcript", "clean raw transcript")]
    assert not keyboard.ops and api.data() == original and len(uia.calls) == 1
    assert notices and worker.session.state == SessionState.NOT_INSERTED and not worker.busy
    worker.shutdown()
    api.assert_retired()


@pytest.mark.parametrize("changed_at", ["recognition", "pre_paste", "pre_enter"])
def test_fresh_field_checks_block_password_changes_inside_the_same_window(changed_at):
    worker, clock, _, uia, api, keyboard, events, notices = setup()
    original = api.data()
    password = FocusedEdit(status="password", is_password=True)
    if changed_at == "recognition":
        def transcribe(audio):
            uia.result = password
            return "Public words"
        worker.services.asr.transcribe = transcribe
    elif changed_at == "pre_paste":
        worker.services.inserter.sleep = lambda delay: setattr(uia, "result", password)
    else:
        worker.services.context.set_profiles([{"exe": "chrome.exe", "app_group": "messages"}])
        worker.services.processor.voice_enter_enabled = True
        worker.services.asr.transcribe = lambda audio: "Hello there press enter"
        send = keyboard.send
        def pasted(key):
            send(key)
            uia.result = password
        keyboard.send = pasted
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    result = worker.last_result.insertion
    assert result.reason == ("enter_password_field" if changed_at == "pre_enter" else "password_field")
    assert keyboard.ops == ([("send", "ctrl+v")] if changed_at == "pre_enter" else [])
    assert not result.enter_sent and not result.clipboard_pending and events[0][0] == "history"
    assert api.data() == original and notices and not worker.busy
    assert uia.calls[0] == (123, True) and all(not text for _, text in uia.calls[1:])
    worker.shutdown()
    api.assert_retired()


def test_cancel_during_field_verification_is_checked_again_before_publishing_text():
    worker, clock, _, uia, api, keyboard, events, _ = setup()
    original, query = api.data(), uia.query
    def cancel(window, *, include_text):
        if not include_text:
            worker.cancel()
        return query(window, include_text=include_text)
    uia.query = cancel
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert worker.last_result.insertion.reason == "cancelled" and not keyboard.ops
    assert events[0][0] == "history" and api.data() == original and not worker.busy
    worker.shutdown()
    api.assert_retired()


@pytest.mark.parametrize("status,password", [("ok", False), ("password", True), ("unavailable", False)])
def test_history_reinsertion_is_serial_and_uses_the_same_field_checks(status, password):
    worker, _, executor, uia, api, keyboard, events, _ = setup(queued=True)
    original = api.data()
    uia.result = replace(uia.result, status=status, is_password=password)
    assert worker.reinsert_text("Saved History text") and worker.busy
    assert not uia.calls and not worker.reinsert_text("Overlapping text")
    executor.drain()
    assert not worker.busy and not events and worker.services.recorder.started == 0
    assert keyboard.ops == ([("send", "ctrl+v")] if status == "ok" else [])
    assert api.data() == original
    worker.shutdown()
    api.assert_retired()


def test_cancelled_queued_reinsertion_performs_no_field_read_or_delivery():
    worker, _, executor, uia, _, keyboard, _, _ = setup(queued=True)
    assert worker.reinsert_text("Saved text")
    worker.cancel()
    executor.drain()
    assert not uia.calls and not keyboard.ops and not worker.busy
    worker.shutdown()


def test_history_only_note_does_not_warn_about_insertion_into_an_unverified_field():
    worker, clock, _, uia, _, keyboard, events, notices = setup()
    uia.result = FocusedEdit(status="password", is_password=True)
    assert worker.start_recording(insert_text=False)
    clock.now = 1
    worker.stop_recording()
    assert worker.last_result.insertion.reason == "history_only" and events[0][0] == "history"
    assert not keyboard.ops and not notices
    worker.shutdown()


def test_legacy_pre_paste_guard_restores_the_clipboard_without_sending_keys():
    from saydraft.insert.inserter import Inserter
    from tests.test_inserter import FakeClipboard, FakeKeyboard
    clipboard, keyboard = FakeClipboard(), FakeKeyboard()
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
                        sleep=lambda seconds: None)
    checks = iter(["", "field_unavailable"])
    result = inserter.insert_text("Public text", start_focus=123, field_guard=lambda: next(checks))
    assert result.reason == "field_unavailable" and not keyboard.ops and clipboard.value == "original"


def test_typing_and_provider_errors_refuse_before_clipboard_or_input():
    from saydraft.insert.inserter import Inserter
    from tests.test_inserter import FakeClipboard, FakeKeyboard
    clipboard, keyboard = FakeClipboard(), FakeKeyboard()
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
                        profiles=[{"match": "Fixture", "insertion": "typing"}])
    def failed():
        raise OSError("Public field failure")
    result = inserter.insert_text("Public text", start_focus=123, app_title="Fixture", field_guard=failed)
    assert result.reason == "field_unavailable" and not keyboard.ops and not clipboard.ops


def test_settings_and_shutdown_keep_one_blocked_uia_owner_instead_of_spawning_replacements():
    entered, release = threading.Event(), threading.Event()
    class Blocked(Reader):
        def focused_element(self):
            entered.set()
            assert release.wait(5)
            return super().focused_element()

        def close(self):
            pass
    uia = BoundedUIA(factory=Blocked, timeout=.03)
    context = ForegroundContextProvider(api=Foreground(), uia=uia)
    worker, *_ = make_worker()
    worker.services.inserter, *_ = adapter()
    worker.services.context = context
    replacements = []
    def services(*args, **kwargs):
        replacement = ForegroundContextProvider(api=Foreground(), use_uia=True)
        replacements.append(replacement)
        return replace(worker.services, context=replacement, profiles=[{"exe": "chrome.exe", "app_group": "code"}])
    worker.services_factory = services
    try:
        with ThreadPoolExecutor(max_workers=2) as callers:
            start = callers.submit(worker.start_recording)
            try:
                assert entered.wait(2)
                worker.configure(worker.services.config)
                assert start.result(timeout=1) is False
                for _ in range(3):
                    worker.configure(worker.services.config)
                assert worker.services.context is context and context._uia is uia
                assert all(item._closed and item._uia is None for item in replacements)
                assert context.profiles == [{"exe": "chrome.exe", "app_group": "code"}]
                assert worker.services.inserter.focus_provider == context.focus
                callers.submit(worker.shutdown).result(timeout=1)
                assert not uia.wait_closed(.01)
                worker.configure(worker.services.config)
                assert len(replacements) == 4
            finally:
                release.set()
    finally:
        release.set()
        worker.shutdown()
        assert uia.wait_closed(2)
