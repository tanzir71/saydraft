"""App default native routing, gesture time and supervised ownership."""

import builtins
import threading
import time

import pytest

from saydraft.config import default_config
from saydraft.core.hotkey_service import HotkeyService
from saydraft.hotkeys import HotkeyConfig, HotkeyController
from saydraft.hotkeys.chords import ChordMatcher, Transition
from tests.test_session_worker import make_worker


class Owner:
    def __init__(self, bindings, *, on_action, on_failure):
        self.bindings, self.action, self.failure = bindings, on_action, on_failure
        self.matcher = ChordMatcher(bindings)
        self.running, self.stuck, self.completion_thread = False, False, None

    @property
    def status(self):
        return {"state": "running" if self.running else "closed"}

    def start(self):
        self.running = True

    def close(self):
        if self.stuck:
            return False
        self.running = False
        return True


def factory():
    owners = []
    def create(*args, **kwargs):
        owner = Owner(*args, **kwargs)
        owners.append(owner)
        return owner
    return create, owners


def test_fresh_mouse_route_and_explicit_disable_reconfigure_without_changing_other_keys():
    cfg = default_config()
    create, owners = factory()
    starts, stops = [], []
    controller = HotkeyController(HotkeyConfig.from_app_config(cfg), on_record_start=lambda: starts.append(True),
        on_record_stop=stops.append, native_factory=create)
    controller.start()
    assert [row.chord.keys for row in owners[0].bindings[:3]] == [
        frozenset(("ctrl", "win")), frozenset(("f9",)), frozenset(("xbutton1",))]
    owners[0].action(Transition("record2", "press"), 10)
    owners[0].action(Transition("record2", "release"), 11)
    assert starts == [True] and stops[0].duration_seconds == 1
    assert controller.stop()
    cfg["hotkeys"]["speech_mouse"] = ""
    controller = HotkeyController(HotkeyConfig.from_app_config(cfg), on_record_start=lambda: None,
        on_record_stop=lambda result: None, native_factory=create)
    controller.start()
    assert [row.name for row in owners[-1].bindings] == ["record0", "record1", "hands_free", "cancel"]
    assert controller.stop()


def test_default_controller_uses_native_without_importing_keyboard_and_keeps_physical_times(monkeypatch):
    create, owners = factory()
    monkeypatch.setattr("saydraft.hotkeys.llhook.LowLevelHooks", create)
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name == "keyboard":
            pytest.fail("External keyboard package must never be imported")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    starts, stops, cancels, saved = [], [], [], []
    controller = HotkeyController(on_record_start=lambda: starts.append(True), on_record_stop=stops.append,
        on_record_cancel=lambda: cancels.append(True), on_save=lambda: saved.append(True), clock=lambda: 100)
    controller.start()
    owner = owners[0]
    assert [row.name for row in owner.bindings] == ["record0", "record1", "cancel", "save"]
    assert all(row.suppress for row in owner.bindings if row.name != "cancel")
    assert not owner.bindings[2].suppress and owner.bindings[2].extra_modifiers
    owner.action(Transition("record0", "press"), 2)
    owner.action(Transition("record0", "release"), 3)
    assert starts == [True] and stops[0].duration_seconds == 1 and stops[0].stopped_at == 3
    owner.action(Transition("save", "press"), 4)
    owner.action(Transition("save", "release"), 5)
    owner.action(Transition("record1", "press"), 6)
    owner.action(Transition("record1", "release", "superseded", "cancel"), 7)
    owner.action(Transition("cancel", "press"), 7)
    assert saved == [True] and cancels == [True] and not controller.is_recording
    assert controller.stop() and not owner.running


def test_record_prefix_handoff_keeps_capture_and_history_prefix_conflicts_fail_before_install():
    create, owners = factory()
    starts, stops = [], []
    controller = HotkeyController(HotkeyConfig(record_hotkey="ctrl", alternate_record_hotkey="ctrl+win"),
        on_record_start=lambda: starts.append(True), on_record_stop=stops.append, native_factory=create)
    controller.start()
    owner = owners[0]
    owner.action(Transition("record0", "press"), 1)
    owner.action(Transition("record0", "release", "superseded", "record1"), 1.1)
    owner.action(Transition("record1", "press"), 1.1)
    owner.action(Transition("record1", "release"), 2)
    assert starts == [True] and len(stops) == 1 and stops[0].duration_seconds == 1
    assert controller.stop()
    conflict = HotkeyController(HotkeyConfig(save_hotkey="ctrl+win+s"), on_record_start=lambda: None,
        on_record_stop=lambda session: None, on_save=lambda: None, native_factory=create)
    with pytest.raises(ValueError, match="prefix"):
        conflict.start()
    assert len(owners) == 1


def test_unretired_owner_blocks_replacement_and_native_failure_cancels_without_final_insertion():
    create, owners = factory()
    cancelled, stopped = [], []
    controller = HotkeyController(on_record_start=lambda: None, on_record_stop=stopped.append,
        on_record_cancel=lambda: cancelled.append(True), native_factory=create)
    controller.start()
    owners[0].action(Transition("record0", "press"), 1)
    owners[0].failure("action_failed")
    assert cancelled == [True] and not stopped and not controller.is_recording
    owners[0].stuck = True
    assert not controller.stop()
    with pytest.raises(OSError, match="still stopping"):
        controller.start()
    assert len(owners) == 1
    owners[0].stuck = False
    controller.start()
    assert len(owners) == 2 and controller.stop()


@pytest.mark.parametrize("manual", [False, True])
def test_native_completion_monitor_recovers_once_then_disables_without_a_restart_loop(manual):
    owners, notices = [], []
    class Supervised(Owner):
        def start(self):
            self.running, self._stopping = True, False
            self.done = threading.Event()
            def work():
                self.done.wait()
                self.running = False
                if not self._stopping:
                    self.failure("message_loop_stopped")
            self.completion_thread = threading.Thread(target=work, daemon=True)
            self.completion_thread.start()
        def close(self):
            self._stopping = True
            self.done.set()
            self.completion_thread.join(1)
            return not self.completion_thread.is_alive()
    def create(*args, **kwargs):
        owner = Supervised(*args, **kwargs)
        owners.append(owner)
        return owner
    service = HotkeyService(default_config(), start=lambda: None, stop=lambda: None, cancel=lambda: None,
        save=lambda: None, notify=notices.append, native_factory=create)
    def wait(predicate):
        until = time.monotonic() + 3
        while not predicate() and time.monotonic() < until:
            time.sleep(.001)
        assert predicate()
    try:
        service.start()
        previous_monitor = service._monitor
        if manual:
            with service._lock:
                owners[0].done.set()
                owners[0].completion_thread.join(1)
                assert service.restart_if_dead()
            previous_monitor.join(1)
        else:
            owners[0].done.set()
        wait(lambda: len(owners) == 2 and len(notices) == 1)
        owners[1].done.set()
        wait(lambda: not service.enabled and len(notices) == 2)
        assert len(owners) == 2 and "restarted" in notices[0] and "stopped" in notices[1]
    finally:
        service.stop()


def test_native_dispatcher_does_not_wait_on_idle_settings_lock_and_cancel_during_capture_aborts_start():
    worker, _, _, _, _, _ = make_worker()
    result = []
    with worker._lock:
        thread = threading.Thread(target=lambda: result.append(worker.start_recording()))
        thread.start()
        thread.join(1)
        assert result == [False]
        thread = threading.Thread(target=worker.cancel)
        thread.start()
        thread.join(1)
        assert not thread.is_alive()
    entered, release = threading.Event(), threading.Event()
    def capture():
        entered.set()
        assert release.wait(3)
    worker.services.context.capture = capture
    thread = threading.Thread(target=lambda: result.append(worker.start_recording()))
    thread.start()
    assert entered.wait(3)
    worker.cancel()
    release.set()
    thread.join(1)
    assert result == [False, False] and worker.services.recorder.started == 0 and not worker.busy


def test_native_recording_release_limits_budget_from_hook_time_and_disable_cancels_capture():
    worker, clock, _, events, _, _ = make_worker()
    create, owners = factory()
    worker.hotkeys.keyboard = None
    worker.hotkeys._controller._native_factory = create
    worker.hotkeys.start()
    owners[0].action(Transition("record0", "press"), 1)
    clock.now = 3
    owners[0].action(Transition("record0", "release"), 2)
    assert worker._context.cleanup_deadline == 4 and [row[0] for row in events] == ["history", "insert"]
    owners[0].action(Transition("record0", "press"), 4)
    worker.hotkeys.stop()
    assert not worker.session.active and not worker.hotkeys.enabled
