"""Synthetic Ask chords preserve recording ownership and explicit opt-in."""

from saydraft.config import default_config, sanitize_config
from saydraft.hotkeys import HotkeyConfig, HotkeyController
from saydraft.hotkeys.chords import Transition
from saydraft.hotkeys.recording import validate_hotkeys
from tests.test_native_recording import factory
from tests.test_notes_shortcuts import feed


def enabled():
    config = default_config()
    config['labs']['ask_mode'] = True
    return config


def test_default_off_and_missing_legacy_binding_never_take_over_custom_recording():
    config = default_config()
    assert config['hotkeys']['ask'] == 'ctrl+win+a' and config['labs']['ask_mode'] is False
    assert HotkeyConfig.from_app_config(config).ask_hotkey is None
    config['hotkeys'].pop('ask')
    config['hotkeys']['speech'] = 'ctrl+win+a'
    restored = sanitize_config(config)
    assert restored['hotkeys']['speech'] == 'ctrl+win+a' and restored['hotkeys']['ask'] == ''
    assert not restored['labs']['ask_mode']


def test_ask_binding_participates_in_conflicts_only_when_enabled():
    config = enabled()
    assert not validate_hotkeys(config['hotkeys'], ask_key=config['hotkeys']['ask'])
    config['hotkeys']['ask'] = config['hotkeys']['save']
    assert validate_hotkeys(config['hotkeys'], ask_key=config['hotkeys']['ask'])
    assert not validate_hotkeys(config['hotkeys'])


def test_ask_supersedes_only_its_cancelled_ptt_prefix_and_fires_once_on_release():
    create, owners = factory()
    calls, cancelled, stopped = [], [], []
    controller = HotkeyController(HotkeyConfig.from_app_config(enabled()),
        on_record_start=lambda: 17, on_record_stop=stopped.append,
        on_record_cancel=lambda: cancelled.append(True),
        on_utility=lambda name, **options: calls.append((name, options)), native_factory=create)
    controller.start()
    try:
        owner = owners[-1]
        for index, key in enumerate(('left_ctrl', 'left_win', 'a')):
            feed(owner, key, True, index / 10)
        feed(owner, 'a', True, .4)
        assert cancelled == [True] and not stopped and not calls
        for index, key in enumerate(('a', 'left_win', 'left_ctrl')):
            feed(owner, key, False, 1 + index / 10)
        assert calls == [('ask', {'prefix_session_id': 17})]
        assert not controller.is_recording
    finally:
        controller.stop()


def test_ask_does_not_cancel_or_take_ownership_of_preexisting_hands_free():
    create, owners = factory()
    calls, cancelled, stopped = [], [], []
    controller = HotkeyController(HotkeyConfig.from_app_config(enabled()),
        on_record_start=lambda: 17, on_record_stop=stopped.append,
        on_record_cancel=lambda: cancelled.append(True),
        on_utility=lambda name, **options: calls.append((name, options)), native_factory=create)
    controller.start()
    try:
        owner = owners[-1]
        owner.action(Transition('hands_free', 'press'), 0)
        assert controller.is_locked
        for index, key in enumerate(('left_ctrl', 'left_win', 'a')):
            feed(owner, key, True, 1 + index / 10)
        for index, key in enumerate(('a', 'left_win', 'left_ctrl')):
            feed(owner, key, False, 2 + index / 10)
        assert controller.is_locked and controller.is_recording
        assert calls == [('ask', {'prefix_session_id': None})]
        assert not cancelled and not stopped
    finally:
        controller.stop()


def test_reset_or_stop_cannot_turn_an_unreleased_ask_chord_into_a_request():
    create, owners = factory()
    calls = []
    controller = HotkeyController(HotkeyConfig.from_app_config(enabled()),
        on_record_start=lambda: 17, on_record_stop=lambda *args: None,
        on_record_cancel=lambda: None, on_utility=lambda *args, **kwargs: calls.append(True), native_factory=create)
    controller.start()
    owner = owners[-1]
    for index, key in enumerate(('left_ctrl', 'left_win', 'a')):
        feed(owner, key, True, index / 10)
    for transition in owner.matcher.reset().transitions:
        owner.action(transition, 1)
    controller.stop()
    assert not calls
