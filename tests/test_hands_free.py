"""Physical chord decisions and session composition, without hooks or OS input."""

import pytest

from saydraft.config import default_config, load_config, save_config
from saydraft.hotkeys import HotkeyConfig, HotkeyController
from saydraft.ui.settings_page import find_hotkey_conflicts
from tests.test_native_recording import factory
from tests.test_session_worker import make_worker


def rig(*, start=None, cancel=None, key="ctrl+win+space"):
    config = default_config()
    config["hotkeys"]["hands_free"] = key
    create, owners = factory()
    starts, stops, cancelled = [], [], []
    controller = HotkeyController(HotkeyConfig.from_app_config(config),
        on_record_start=start or (lambda: starts.append(True)), on_record_stop=stops.append,
        on_record_cancel=cancel or (lambda: cancelled.append(True)), native_factory=create)
    controller.start()
    owner = owners[0]

    def event(key, down, when):
        decision = owner.matcher.feed(key, down)
        for transition in decision.transitions:
            owner.action(transition, when)
        return decision

    return controller, event, starts, stops, cancelled


@pytest.mark.parametrize("modifiers", [("left_ctrl", "left_win"), ("right_win", "right_ctrl")])
@pytest.mark.parametrize("release", [("space", 0, 1), (0, "space", 1), (1, 0, "space")])
def test_modifier_prefix_locks_one_capture_and_later_ptt_release_finishes(modifiers, release):
    controller, event, starts, stops, _ = rig()
    a, b = modifiers
    event(a, True, 1)
    event(b, True, 1.1)
    event("space", True, 1.2)
    event("space", True, 1.3)  # Native auto-repeat produces no second toggle.
    for key in release:
        event(modifiers[key] if type(key) is int else key, False, 1.4)
    assert controller.is_locked and controller.is_recording and starts == [True] and not stops
    event(a, True, 3)
    event(b, True, 3.1)
    event(a, False, 4)
    event(b, False, 4.1)
    assert not controller.is_recording and len(stops) == 1 and stops[0].locked
    assert stops[0].started_at == 1.1 and stops[0].stopped_at == 4
    assert controller.stop()


def test_rebound_toggle_starts_and_stops_once_ignoring_its_key_up_and_force_stop_tail():
    controller, event, starts, stops, _ = rig(key="f8")
    event("f8", True, 1)
    event("f8", False, 1.1)
    assert controller.is_locked and not stops
    event("f8", True, 3)
    event("f8", False, 3.1)
    assert starts == [True] and len(stops) == 1 and stops[0].duration_seconds == 2
    event("f8", True, 5)
    controller.force_stop()
    event("f8", False, 6)
    assert len(stops) == 2 and not controller.is_recording
    assert controller.stop()


def test_same_modifier_toggle_finishes_an_existing_lock_without_starting_again():
    controller, event, starts, stops, _ = rig()
    for when in (1, 3):
        for key in ("left_ctrl", "left_win", "space"):
            event(key, True, when)
        for key in ("space", "left_win", "left_ctrl"):
            event(key, False, when + .1)
    assert starts == [True] and len(stops) == 1 and stops[0].duration_seconds == 2
    assert not controller.is_locked and controller.stop()


def test_failed_start_and_escape_clear_hands_free_state_without_final_delivery():
    attempts = []
    controller, event, _, stops, cancelled = rig(start=lambda: attempts.append(True) or False, key="f8")
    event("f8", True, 1)
    event("f8", False, 1.1)
    assert attempts == [True] and not controller.is_recording and not controller.is_locked
    controller.on_record_start = lambda: None
    event("f8", True, 2)
    event("f8", False, 2.1)
    event("esc", True, 3)
    assert cancelled == [True] and not stops and not controller.is_recording
    assert controller.stop()
    controller._on_hands_free_press(4)
    assert not controller.is_recording


@pytest.mark.parametrize("key", ["f9", "f10", "ctrl+f10", "escape"])
def test_shared_settings_compiler_refuses_toggle_conflicts_before_hook_installation(key):
    config = default_config()
    config["hotkeys"]["hands_free"] = key
    assert find_hotkey_conflicts(config["hotkeys"])
    create, owners = factory()
    controller = HotkeyController(HotkeyConfig.from_app_config(config), on_record_start=lambda: None,
        on_record_stop=lambda session: None, on_save=lambda: None, native_factory=create)
    with pytest.raises(ValueError):
        controller.start()
    assert not owners


def test_blank_toggle_is_persisted_and_does_not_install_a_binding(tmp_path):
    config = default_config()
    config["hotkeys"]["hands_free"] = ""
    path = tmp_path / "config.json"
    save_config(config, path)
    loaded = load_config(config_path=path)
    assert loaded["hotkeys"]["hands_free"] == ""
    create, owners = factory()
    controller = HotkeyController(HotkeyConfig.from_app_config(loaded), on_record_start=lambda: None,
        on_record_stop=lambda session: None, native_factory=create)
    controller.start()
    assert not any(row.name == "hands_free" for row in owners[0].bindings)
    assert controller.stop()


def test_hands_free_session_persists_before_delivery_and_short_sessions_are_discarded():
    worker, clock, _, events, _, _ = make_worker()
    create, owners = factory()
    worker.hotkeys.keyboard = None
    worker.hotkeys._controller._native_factory = create
    worker.hotkeys.start()
    owner = owners[0]
    from saydraft.hotkeys.chords import Transition

    owner.action(Transition("hands_free", "press"), 0)
    assert worker.services.recorder.started == 1 and worker.hotkeys._controller.is_locked
    clock.now = 2
    owner.action(Transition("hands_free", "press"), 2)
    assert worker.services.recorder.stopped == 1 and [event[0] for event in events] == ["history", "insert"]
    events.clear()
    clock.now = 3
    owner.action(Transition("hands_free", "press"), 3)
    clock.now = 3.499
    owner.action(Transition("hands_free", "press"), 3.499)
    assert worker.services.recorder.stopped == 2 and not events
    worker.shutdown()
