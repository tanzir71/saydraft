from types import SimpleNamespace

import pytest

from saydraft.hotkeys import HotkeyController


def controller_with_owned_queue():
    queued, starts, stops = [], [], []
    ticks = [0.]
    controller = HotkeyController(on_record_start=lambda: starts.append(True) or 1,
        on_record_stop=stops.append, clock=lambda: ticks[0])
    controller._listening = True
    controller._native = SimpleNamespace(defer=lambda callback: queued.append(callback) or True)
    return controller, queued, starts, stops, ticks


def test_clicks_use_the_native_action_queue_and_stop_the_locked_session():
    controller, queued, starts, stops, ticks = controller_with_owned_queue()
    assert controller.request_hands_free()
    assert not starts and not controller.is_recording
    queued.pop(0)()
    assert starts == [True] and controller.is_locked
    assert not controller.request_hands_free()
    ticks[0] = .6
    assert controller.request_hands_free(stop=True)
    assert not stops
    queued.pop(0)()
    assert len(stops) == 1 and stops[0].locked
    assert stops[0].duration_seconds == .6 and not controller.is_recording


@pytest.mark.parametrize("stop", [False, True])
def test_cancelled_clicks_cannot_start_or_stop_a_newer_recording(stop):
    controller, queued, starts, stops, _ = controller_with_owned_queue()
    if stop:
        controller._on_hands_free_press()
    assert controller.request_hands_free(stop=stop)
    callback = queued.pop(0)
    controller.discard_active_recording()
    if stop:
        controller._on_hands_free_press()
    previous = len(starts), len(stops), controller.is_recording
    callback()
    assert (len(starts), len(stops), controller.is_recording) == previous


def test_a_queued_click_does_not_cross_native_backend_replacement():
    controller, queued, starts, _, _ = controller_with_owned_queue()
    assert controller.request_hands_free()
    controller._native = SimpleNamespace()
    queued.pop(0)()
    assert not starts


def test_app_routes_the_error_fix_to_the_correct_settings_page():
    from saydraft.app import SaydraftApp

    app = SaydraftApp()
    opened, indices = [], []
    app._show_settings = lambda: opened.append(True)
    labels = ["General", "Languages", "Models", "Microphone"]
    app.settings_window = SimpleNamespace(tabs=SimpleNamespace(count=lambda: len(labels),
        tabText=lambda index: labels[index], setCurrentIndex=indices.append))
    app._fix_bar_error("microphone")
    app._fix_bar_error("models")
    assert indices == [3, 2] and len(opened) == 2
