"""Real chord compilation/controller routing with a synthetic native owner."""

from itertools import permutations
from types import SimpleNamespace

import pytest

from saydraft.config import default_config
from saydraft.hotkeys.chords import ChordMatcher
from saydraft.hotkeys.controller import HotkeyConfig, HotkeyController
from saydraft.hotkeys.recording import recording_bindings
from tests.test_hotkeys import FakeClock, FakeKeyboard
from tests.test_session_worker import Timer


def fixture(*, pending=False, native=False):
    starts, stops, cancels, requests, owners = [], [], [], [], []
    clock = FakeClock()
    def normal():
        starts.append('dictation')
        return 11
    def command(current, accepted, **kwargs):
        requests.append((current, accepted, kwargs))
        starts.append('command')
        if not pending:
            assert accepted(12)
        return True
    def factory(bindings, *, on_action, on_failure):
        matcher = ChordMatcher(bindings)
        owner = SimpleNamespace(status={'state': 'running'}, completion_thread=None,
            start=lambda: None, close=lambda: True, post_action=lambda callback: callback())
        def feed(key, down):
            decision = matcher.feed(key, down)
            for action in decision.transitions:
                on_action(action, clock.now())
            return decision
        owner.feed = feed
        owners.append(owner)
        return owner
    c = HotkeyController(HotkeyConfig(record_hotkey='ctrl+win', alternate_record_hotkey=None,
        hands_free_hotkey='ctrl+win+space', command_hotkey='ctrl+win+alt'),
        on_record_start=normal, on_record_stop=stops.append, on_record_cancel=lambda: cancels.append(True),
        on_command_start_guarded=command, clock=clock.now, timer_factory=Timer, native_factory=factory)
    keyboard = FakeKeyboard()
    c.start(None if native else keyboard)
    return SimpleNamespace(controller=c, keyboard=keyboard, clock=clock, starts=starts, stops=stops,
                           cancels=cancels, requests=requests, owners=owners)


@pytest.mark.parametrize('order', list(permutations(('left_ctrl', 'left_win', 'left_alt'))))
def test_native_chord_has_distinct_hold_session_and_retires_a_legitimate_ptt_prefix(order):
    f = fixture(native=True)
    for key in order:
        f.owners[0].feed(key, True)
    assert f.starts[-1] == 'command' and not f.controller.is_locked
    prefix = f.requests[0][2]['prefix_session_id']
    assert prefix == (11 if order[-1] == 'left_alt' else None)
    assert len(f.cancels) == (1 if prefix else 0)
    f.clock.advance(1)
    for key in reversed(order):
        f.owners[0].feed(key, False)
    assert len(f.stops) == 1 and f.stops[0].session_id == 12 and f.stops[0].kind == 'command'
    assert not f.controller.is_recording and not f.controller.is_locked
    f.controller.stop()


def test_pending_release_cannot_stop_any_worker_or_acknowledge_a_later_normal_gesture():
    f = fixture(pending=True)
    f.keyboard.press('ctrl+win+alt')
    current, accepted, _ = f.requests[0]
    assert current()
    f.clock.advance(.05)
    f.keyboard.release('ctrl+win+alt')
    assert not current() and not f.stops
    f.keyboard.press('ctrl+win')
    assert not accepted(12) and f.controller._session_id == 11
    f.clock.advance(1)
    f.keyboard.release('ctrl+win')
    assert len(f.stops) == 1 and f.stops[0].session_id == 11


def test_repeated_command_taps_never_lock_and_other_recording_gestures_do_not_retarget_command():
    f = fixture()
    for _ in range(2):
        f.keyboard.press('ctrl+win+alt')
        f.keyboard.press('ctrl+win+space')
        f.keyboard.press('ctrl+win')
        f.clock.advance(.05)
        f.keyboard.release('ctrl+win+alt')
        assert not f.controller.is_recording and not f.controller.is_locked
    assert f.starts == ['command', 'command'] and len(f.stops) == 2
    assert all(s.kind == 'command' and not s.locked and s.session_id == 12 for s in f.stops)


def test_preexisting_hands_free_session_is_not_cancelled_or_relabelled_by_command():
    f = fixture()
    f.keyboard.press('ctrl+win+space')
    f.keyboard.press('ctrl+win+alt')
    f.keyboard.release('ctrl+win+alt')
    assert f.controller.is_locked and f.starts == ['dictation'] and not f.requests and not f.cancels
    f.keyboard.press('ctrl+win+space')
    assert len(f.stops) == 1 and f.stops[0].session_id == 11 and f.stops[0].kind == 'dictation'


def test_escape_native_supersession_cancels_without_finalizing_an_instruction():
    f = fixture(native=True)
    for key in ('left_alt', 'left_ctrl', 'left_win'):
        f.owners[0].feed(key, True)
    assert f.starts == ['command']
    f.owners[0].feed('esc', True)
    for key in ('left_alt', 'left_ctrl', 'left_win'):
        f.owners[0].feed(key, False)
    assert f.cancels and not f.stops and not f.controller.is_recording


def test_disable_and_reenable_retires_pending_generation_ack():
    f = fixture(pending=True)
    f.keyboard.press('ctrl+win+alt')
    current, accepted, _ = f.requests[0]
    f.controller.stop()
    f.controller.start(f.keyboard)
    assert not current() and not accepted(12) and not f.stops


def test_command_only_installed_by_explicit_labs_opt_in_and_conflicts_are_checked_without_hooks():
    cfg = default_config()
    assert HotkeyConfig.from_app_config(cfg).command_hotkey is None
    cfg['labs']['command_mode'] = True
    assert HotkeyConfig.from_app_config(cfg).command_hotkey == 'ctrl+win+alt'
    with pytest.raises(ValueError, match='conflict'):
        recording_bindings({'ptt': 'ctrl+win'}, cancel_key='esc', save_key='',
                           utility_keys={'scratchpad': 'ctrl+win+alt'}, command_key='ctrl+win+alt')


def test_command_route_requires_an_explicit_owner_cancellation_callback_before_installing_hooks():
    with pytest.raises(ValueError, match='cancellation callback'):
        HotkeyController(on_record_start=lambda: 1, on_record_stop=lambda _: None,
                         on_command_start_guarded=lambda *a, **kw: True)
