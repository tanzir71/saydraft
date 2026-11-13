"""Synthetic native utility chords and migration-safe, revocable GUI requests."""

from saydraft.config import default_config, sanitize_config, migrate_settings_txt
from saydraft.core.hotkey_service import HotkeyService
from saydraft.hotkeys import HotkeyConfig, HotkeyController
from saydraft.hotkeys.chords import Transition
from saydraft.hotkeys.recording import validate_hotkeys
from saydraft.hotkeys.wispr import shortcut_warning
from tests.test_native_recording import factory


def feed(owner, key, down, when):
    decision = owner.matcher.feed(key, down)
    for transition in decision.transitions:
        owner.action(transition, when)
    return decision


def test_default_diff_supersedes_recording_prefix_cancels_it_and_fires_once_on_release():
    create, owners = factory()
    starts, stops, cancels, actions = [], [], [], []
    controller = HotkeyController(HotkeyConfig.from_app_config(default_config()),
        on_record_start=lambda: starts.append(True), on_record_stop=stops.append,
        on_record_cancel=lambda: cancels.append(True), on_utility=actions.append, native_factory=create)
    controller.start()
    try:
        owner = owners[-1]
        feed(owner, 'left_ctrl', True, 1)
        feed(owner, 'left_win', True, 1.1)
        assert controller.is_recording
        assert feed(owner, 'd', True, 1.2).suppress
        feed(owner, 'd', True, 1.3)  # Auto repeat.
        assert not controller.is_recording and cancels == [True] and not actions
        feed(owner, 'd', False, 1.4)
        feed(owner, 'left_win', False, 1.5)
        feed(owner, 'left_ctrl', False, 1.6)
        assert starts == [True] and not stops and actions == ['view_diff']
    finally:
        assert controller.stop()


def test_scratchpad_chord_uses_no_recording_callback_and_reset_cannot_open_it():
    create, owners = factory()
    actions = []
    def forbidden(*args):
        raise AssertionError('Scratchpad must not admit a recording')
    controller = HotkeyController(HotkeyConfig.from_app_config(default_config()),
        on_record_start=forbidden, on_record_stop=forbidden, on_utility=actions.append, native_factory=create)
    controller.start()
    try:
        owner = owners[-1]
        for index, key in enumerate(('left_win', 'left_alt', 's')):
            feed(owner, key, True, index)
        for transition in owner.matcher.reset().transitions:
            owner.action(transition, 4)
        assert actions == []
        for index, key in enumerate(('left_win', 'left_alt', 's')):
            feed(owner, key, True, index + 5)
        feed(owner, 's', False, 9)
        assert actions == ['scratchpad']
    finally:
        assert controller.stop()


def test_queued_gui_request_is_revoked_across_stop_restart_and_reconfiguration():
    create, owners = factory()
    requests = []
    service = HotkeyService(default_config(), start=lambda: None, stop=lambda: None,
        cancel=lambda: None, save=lambda: None, notify=lambda message: None,
        native_factory=create, ui_request=requests.append)
    service.start()
    try:
        owners[-1].action(Transition('scratchpad', 'release'), 1)
        first = requests[-1]
        assert service.is_current_ui_request(first)
        service.stop()
        assert not service.is_current_ui_request(first)
        service.start()
        assert not service.is_current_ui_request(first)
        owners[-1].action(Transition('view_diff', 'release'), 2)
        assert requests[-1].action == 'view_diff' and service.is_current_ui_request(requests[-1])
        previous = requests[-1]
        changed = default_config()
        changed['hotkeys'].update(scratchpad='ctrl+alt+n', view_diff='')
        service.configure(changed)
        assert not service.is_current_ui_request(previous)
        bindings = {item.name: item.chord.keys for item in owners[-1].bindings}
        assert bindings['scratchpad'] == frozenset(('ctrl', 'alt', 'n')) and 'view_diff' not in bindings
        owners[-1].action(Transition('scratchpad', 'release'), 3)
        assert service.is_current_ui_request(requests[-1])
        service.revoke_requests()
        assert not service.is_current_ui_request(requests[-1])
        assert not service._request_ui('scratchpad')
    finally:
        service.stop()


def test_rebind_disable_and_conflicts_use_the_same_compiler():
    keys = default_config()['hotkeys']
    assert validate_hotkeys(keys) == []
    keys.update(scratchpad='ctrl+alt+n', view_diff='ctrl+alt+d')
    assert validate_hotkeys(keys) == []
    keys['view_diff'] = keys['save']
    assert validate_hotkeys(keys)
    keys['view_diff'] = 'ctrl+win+space'
    assert validate_hotkeys(keys)
    keys.update(scratchpad='', view_diff='')
    assert validate_hotkeys(keys) == []
    assert sanitize_config({'hotkeys': keys})['hotkeys']['scratchpad'] == ''


def test_wispr_advisory_includes_diff_even_when_recording_chords_are_rebound():
    keys = default_config()['hotkeys']
    keys.update(speech='f8', speech_alternative='', hands_free='f7')
    assert 'Wispr Flow is running' in shortcut_warning(keys, detector=lambda: True)
    keys['view_diff'] = ''
    assert shortcut_warning(keys, detector=lambda: True) == ''


def test_upgrade_disables_only_new_defaults_that_conflict_with_existing_custom_shortcuts(tmp_path):
    keys = default_config()['hotkeys']
    keys.pop('scratchpad')
    keys.pop('view_diff')
    keys['speech_alternative'] = 'ctrl+win+d'
    result = sanitize_config({'hotkeys': keys})['hotkeys']
    assert result['speech_alternative'] == 'ctrl+win+d' and result['view_diff'] == ''
    assert result['scratchpad'] == 'win+alt+s' and validate_hotkeys(result) == []
    path = tmp_path / 'settings.txt'
    path.write_text('speech_hotkey=ctrl+win+d\n', encoding='utf-8')
    legacy = migrate_settings_txt(path)['hotkeys']
    assert legacy['speech'] == 'ctrl+win+d' and legacy['view_diff'] == ''
