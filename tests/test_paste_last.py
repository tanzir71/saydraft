"""Saved SQLite text → frozen field → guarded memory delivery; no OS input."""

import sqlite3
import threading
from dataclasses import replace

import pytest

from saydraft.config import default_config, load_config, save_config
from saydraft.context.focused_edit import FocusedEdit
from saydraft.history import DictationHistoryStore, HistoryEntry
from saydraft.hotkeys import HotkeyConfig, HotkeyController
from saydraft.ui.settings_page import find_hotkey_conflicts
from tests.test_native_recording import factory
from tests.test_uia_delivery import setup

TEXT = ' iPhone বাংলা العربية https://example.com/x\npress enter '


def row(text):
    return HistoryEntry("Public fixture", "authored raw words", text, "balanced", "general", 1, "fixture")


def rig(tmp_path, *, queued=True):
    worker, _, executor, uia, api, keyboard, events, _ = setup(queued=queued)
    store = DictationHistoryStore(tmp_path / "history.db")
    worker.services.history = worker.services.processor.history = store
    worker.services.asr.transcribe = lambda audio: pytest.fail("Paste started recognition")
    worker.services.cleaner.process_transcript = lambda *args: pytest.fail("Paste ran cleanup")
    return worker, executor, uia, api, keyboard, events, store


def test_last_transcript_survives_restart_skips_blank_rows_and_preserves_exact_text(tmp_path):
    store = DictationHistoryStore(tmp_path / "history.db")
    assert store.last_transcript() is None
    store.append(row("Older words"))
    store.append(row(TEXT))
    for blank in ("", " \t\n", "\u2003\u00a0"):
        store.append(row(blank))
    before = store.list_recent()
    assert DictationHistoryStore(store.db_path).last_transcript() == TEXT
    assert store.list_recent() == before


def test_exact_saved_text_precedes_private_clipboard_delivery_without_enter_or_new_statistics(tmp_path):
    worker, executor, uia, api, keyboard, events, store = rig(tmp_path)
    store.append(row(TEXT))
    before, original = store.list_recent(), api.data()
    with sqlite3.connect(store.db_path) as connection:
        stats = connection.execute("SELECT * FROM stats_daily").fetchall()
    send = keyboard.send
    def checked(key):
        assert key == "ctrl+v" and store.list_recent() == before
        assert api.data() == [(format, bytes(4)) for format in api.privacy] + [
            (13, (TEXT + "\0").encode("utf-16-le"))]
        send(key)
    keyboard.send = checked
    assert worker.paste_last() and worker.busy
    assert uia.calls == [(123, False)] and not keyboard.ops
    assert not worker.paste_last() and uia.calls == [(123, False)]
    executor.drain()
    assert keyboard.ops == [("send", "ctrl+v")] and api.data() == original
    assert not worker.busy and not events and worker.services.recorder.started == 0
    assert uia.calls and all(not text for _, text in uia.calls)
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT * FROM stats_daily").fetchall() == stats
    worker.shutdown()
    api.assert_retired()


@pytest.mark.parametrize("status,password", [("password", True), ("unavailable", False), ("changed", False)])
def test_refused_field_reads_no_history_and_changes_no_clipboard(tmp_path, status, password):
    worker, _, uia, api, keyboard, _, store = rig(tmp_path)
    original = api.data()
    uia.result = FocusedEdit(status=status, is_password=password)
    store.last_transcript = lambda: pytest.fail("Refused field caused a History read")
    assert not worker.paste_last() and not worker.busy
    assert uia.calls == [(123, False)] and not keyboard.ops and api.data() == original
    worker.shutdown()
    api.assert_retired()


@pytest.mark.parametrize("change", ["window", "field", "password"])
def test_the_original_target_is_verified_after_the_saved_text_is_read(tmp_path, change):
    worker, executor, uia, api, keyboard, _, store = rig(tmp_path)
    store.append(row(TEXT))
    original, read = api.data(), store.last_transcript
    def changed():
        text = read()
        if change == "window":
            worker.services.context._api.foreground = lambda: 456
        elif change == "field":
            uia.result = replace(uia.result, runtime_id=(9, 9))
        else:
            uia.result = FocusedEdit(status="password", is_password=True)
        return text
    store.last_transcript = changed
    assert worker.paste_last()
    executor.drain()
    assert not keyboard.ops and api.data() == original and not worker.busy
    worker.shutdown()
    api.assert_retired()


@pytest.mark.parametrize("when", ["queued", "history_read"])
def test_cancellation_blocks_further_field_reads_and_delivery(tmp_path, when):
    worker, executor, uia, api, keyboard, _, store = rig(tmp_path)
    store.append(row(TEXT))
    read = store.last_transcript
    if when == "history_read":
        store.last_transcript = lambda: (worker.cancel(), read())[1]
    else:
        store.last_transcript = lambda: pytest.fail("Cancelled queue read History")
    assert worker.paste_last()
    if when == "queued":
        worker.cancel()
    executor.drain()
    assert uia.calls == [(123, False)] and not keyboard.ops and not worker.busy
    worker.shutdown()
    api.assert_retired()


@pytest.mark.parametrize("failure", ["empty", "database"])
def test_empty_or_failed_history_is_explained_without_input_or_private_error_details(tmp_path, failure, caplog):
    worker, executor, _, api, keyboard, _, store = rig(tmp_path)
    if failure == "database":
        def fail():
            raise OSError("private database detail")
        store.last_transcript = fail
    notices = []
    worker.emit_callback = lambda name, *args: notices.extend(args) if name == "notification_requested" else None
    assert worker.paste_last()
    executor.drain()
    assert notices and not keyboard.ops and not worker.busy
    assert "private database detail" not in caplog.text + repr(notices)
    worker.shutdown()
    api.assert_retired()


@pytest.mark.parametrize("action", ["cancel", "settings", "shutdown"])
def test_capture_is_reserved_cancellable_and_does_not_hold_the_session_mutex(tmp_path, action):
    worker, executor, uia, api, keyboard, _, store = rig(tmp_path)
    entered, release, result = threading.Event(), threading.Event(), []
    query = uia.query
    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return query(*args, **kwargs)
    uia.query = blocked
    store.last_transcript = lambda: pytest.fail("Cancelled capture read History")
    thread = threading.Thread(target=lambda: result.append(worker.paste_last()))
    thread.start()
    try:
        assert entered.wait(2) and worker.busy and not worker.start_recording()
        if action == "settings":
            config = default_config()
            config["dictation"]["profile"] = "chat"
            replacement = replace(worker.services, config=config)
            worker.services_factory = lambda *args, **kwargs: replacement
            worker.configure(config)
            assert worker._pending_config == config
        elif action == "shutdown":
            worker.shutdown()
        else:
            worker.cancel()
    finally:
        release.set()
        thread.join(2)
    assert result == [False] and not thread.is_alive() and not keyboard.ops
    if action == "settings":
        assert worker.busy  # The queued apply must execute outside the native dispatcher.
        executor.drain()
        assert worker.services.config["dictation"]["profile"] == "chat" and worker._pending_config is None
    assert not worker.busy
    if action != "shutdown":
        worker.shutdown()
    api.assert_retired()


def test_shortcut_returns_without_field_reads_while_settings_holds_the_mutex(tmp_path):
    worker, _, uia, api, _, _, _ = rig(tmp_path)
    result = []
    with worker._lock:
        thread = threading.Thread(target=lambda: result.append(worker.paste_last()))
        thread.start()
        thread.join(1)
        assert result == [False]
    assert not thread.is_alive() and not uia.calls
    worker.shutdown()
    api.assert_retired()


def test_rejected_paste_queue_releases_the_capture_slot_without_reading_history(tmp_path):
    worker, executor, uia, api, keyboard, _, store = rig(tmp_path)
    def rejected(*args):
        raise RuntimeError("executor unavailable")
    executor.submit = rejected
    store.last_transcript = lambda: pytest.fail("Rejected queue read History")
    assert not worker.paste_last() and not worker.busy and not keyboard.ops
    assert uia.calls == [(123, False)]
    worker.shutdown()
    api.assert_retired()


def test_native_shortcut_runs_once_on_release_and_never_starts_recording(tmp_path):
    worker, executor, uia, api, keyboard, _, store = rig(tmp_path)
    store.append(row(TEXT))
    create, owners = factory()
    worker.hotkeys.keyboard = None
    worker.hotkeys._controller._native_factory = create
    worker.hotkeys.start()
    owner = owners[0]
    def edge(key, down):
        for transition in owner.matcher.feed(key, down).transitions:
            owner.action(transition, 1)
    for key in ("left_shift", "left_alt", "z", "z"):
        edge(key, True)
    assert not uia.calls and worker.services.recorder.started == 0
    edge("z", False)
    assert uia.calls == [(123, False)]
    for key in ("left_alt", "left_shift"):
        edge(key, False)
    executor.drain()
    assert keyboard.ops == [("send", "ctrl+v")] and worker.services.recorder.started == 0
    worker.shutdown()
    api.assert_retired()


@pytest.mark.parametrize("key", ["f9", "f10", "ctrl+win+z", "shift+f10", "escape"])
def test_paste_prefix_conflicts_fail_in_settings_and_before_native_installation(key):
    config = default_config()
    config["hotkeys"]["paste_last"] = key
    assert find_hotkey_conflicts(config["hotkeys"])
    create, owners = factory()
    controller = HotkeyController(HotkeyConfig.from_app_config(config), on_record_start=lambda: None,
        on_record_stop=lambda session: None, on_save=lambda: None, on_paste=lambda: None, native_factory=create)
    with pytest.raises(ValueError):
        controller.start()
    assert not owners


@pytest.mark.parametrize("key", ["", "alt+p"])
def test_rebound_or_disabled_shortcut_survives_reload(tmp_path, key):
    config = default_config()
    config["hotkeys"]["paste_last"] = key
    path = tmp_path / "config.json"
    save_config(config, path)
    loaded = load_config(config_path=path)
    assert loaded["hotkeys"]["paste_last"] == key and not find_hotkey_conflicts(loaded["hotkeys"])
    create, owners = factory()
    pasted = []
    controller = HotkeyController(HotkeyConfig.from_app_config(loaded), on_record_start=lambda: None,
        on_record_stop=lambda session: None, on_paste=lambda: pasted.append(True), native_factory=create)
    controller.start()
    bindings = [item for item in owners[0].bindings if item.name == "paste_last"]
    assert bool(bindings) == bool(key)
    if key:
        from saydraft.hotkeys.chords import Transition
        owners[0].action(Transition("paste_last", "release", "superseded"), 1)
        assert not pasted
        owners[0].action(Transition("paste_last", "release"), 2)
        assert pasted == [True]
    assert controller.stop()
