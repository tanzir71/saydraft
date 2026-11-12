"""Synthetic events never install hooks, invoke an action or send OS keys."""

from itertools import permutations

import pytest

from saydraft.hotkeys.chords import Binding, Chord, ChordMatcher, conflicts
from saydraft.hotkeys.keys import physical_key


def binding(name, chord, **kwargs):
    return Binding(name, Chord.parse(chord), **kwargs)


def actions(decision):
    return [(item.name, item.phase, item.reason) for item in decision.transitions]


@pytest.mark.parametrize("text,keys", [("Control + Windows", {"ctrl", "win"}),
    ("Shift+ALT+Z", {"shift", "alt", "z"}), ("F9", {"f9"}), ("mouse4", {"xbutton1"}),
    ("left control + right windows", {"left_ctrl", "right_win"}), ("vk41", {"a"}),
    ("vkE8", {"vk_e8"}), ("ctrl+page up", {"ctrl", "page_up"})])
def test_chord_names_are_canonical_and_include_mouse_modifiers_and_legacy_keys(text, keys):
    assert Chord.parse(text).keys == frozenset(keys)


@pytest.mark.parametrize("text", [None, "", " ", "ctrl+", "+f9", "ctrl++f9", "unknown", "f25",
    "ctrl+control", "ctrl+left ctrl", "a+b", "ctrl,f9", "vk00", "vkff", "x" * 129])
def test_ambiguous_or_unsupported_bindings_are_refused(text):
    with pytest.raises(ValueError):
        Chord.parse(text)


def test_native_key_decode_preserves_sides_without_async_key_state_or_typed_characters():
    assert physical_key(0x11) == "left_ctrl" and physical_key(0x11, extended=True) == "right_ctrl"
    assert physical_key(0x10, scan=0x36) == "right_shift" and physical_key(0x10, scan=0x2A) == "left_shift"
    assert physical_key(0xA5) == "right_alt" and physical_key(0x74) == "f5"
    assert physical_key(0x05) == "xbutton1" and physical_key(0xE8) == "vk_e8"
    assert physical_key(0) is None and physical_key(True) is None and physical_key(255) is None


@pytest.mark.parametrize("ctrl", ["left_ctrl", "right_ctrl"])
@pytest.mark.parametrize("win", ["left_win", "right_win"])
def test_modifier_chord_fires_at_full_down_and_balances_each_release_order(ctrl, win):
    for press in permutations((ctrl, win)):
        for release in permutations((ctrl, win)):
            matcher = ChordMatcher([binding("ptt", "ctrl+win")])
            decisions = {}
            assert not matcher.feed(press[0], True).suppress
            decisions[press[0]] = False
            complete = matcher.feed(press[1], True)
            assert actions(complete) == [("ptt", "press", "physical")] and complete.suppress
            decisions[press[1]] = True
            assert not actions(matcher.feed(press[1], True))  # auto-repeat
            released = matcher.feed(release[0], False)
            assert actions(released) == [("ptt", "release", "physical")]
            assert released.suppress == decisions[release[0]]
            final = matcher.feed(release[1], False)
            assert not actions(final) and final.suppress == decisions[release[1]]
            assert (released.menu_mask, final.menu_mask) == tuple(key == win for key in release)


def test_superset_chords_supersede_without_restarting_prefix_on_key_up():
    matcher = ChordMatcher([binding("ptt", "ctrl+win"), binding("hands_free", "ctrl+win+space"),
                            binding("command", "ctrl+win+alt")])
    matcher.feed("left_ctrl", True)
    assert actions(matcher.feed("left_win", True)) == [("ptt", "press", "physical")]
    assert actions(matcher.feed("space", True)) == [("ptt", "release", "superseded"),
                                                   ("hands_free", "press", "physical")]
    assert actions(matcher.feed("space", False)) == [("hands_free", "release", "physical")]
    assert actions(matcher.feed("left_alt", True)) == [("command", "press", "physical")]
    assert actions(matcher.feed("left_alt", False)) == [("command", "release", "physical")]
    assert not actions(matcher.feed("left_ctrl", False))
    assert matcher.feed("left_win", False).menu_mask


def test_escape_passes_through_during_modifier_chord_and_records_no_user_keys():
    matcher = ChordMatcher([binding("ptt", "ctrl+win"), binding("cancel", "esc", suppress=False, extra_modifiers=True)])
    matcher.feed("left_win", True)
    matcher.feed("right_ctrl", True)
    escaped = matcher.feed("esc", True)
    assert actions(escaped) == [("ptt", "release", "superseded"), ("cancel", "press", "physical")]
    assert not escaped.suppress and not matcher.feed("esc", False).suppress
    assert not matcher.feed("right_ctrl", False).menu_mask
    assert matcher.feed("left_win", False).menu_mask


def test_ordinary_keys_modifiers_and_unused_mouse_buttons_pass_through():
    matcher = ChordMatcher([binding("legacy", "f9"), binding("mouse", "xbutton1")])
    for key in ("a", "left_win", "left_ctrl", "xbutton2", "middle_mouse"):
        assert not matcher.feed(key, True).suppress
        assert not matcher.feed(key, False).suppress
    assert actions(matcher.feed("xbutton1", True)) == [("mouse", "press", "physical")]
    assert matcher.feed("xbutton1", True).suppress
    assert actions(matcher.feed("xbutton1", False)) == [("mouse", "release", "physical")]
    assert matcher.feed("f9", True).suppress and matcher.feed("f9", False).suppress


def test_our_ignored_events_cannot_activate_clear_or_suppress_a_chord():
    matcher = ChordMatcher([binding("ptt", "ctrl+win")])
    matcher.feed("left_ctrl", True, ignore=True)
    assert not actions(matcher.feed("left_win", True))
    assert actions(matcher.feed("left_ctrl", True)) == [("ptt", "press", "physical")]
    assert not matcher.feed("left_ctrl", False, ignore=True).suppress
    assert actions(matcher.feed("left_ctrl", False)) == [("ptt", "release", "physical")]
    assert matcher.feed("left_win", False).menu_mask


def test_generic_modifier_stays_held_until_both_sides_are_released():
    matcher = ChordMatcher([binding("ptt", "ctrl+win")])
    matcher.feed("left_ctrl", True)
    matcher.feed("right_ctrl", True)
    matcher.feed("left_win", True)
    assert not actions(matcher.feed("left_ctrl", False))
    assert actions(matcher.feed("right_ctrl", False)) == [("ptt", "release", "physical")]
    assert matcher.feed("left_win", False).menu_mask


def test_passthrough_win_binding_does_not_mask_but_suppressed_alt_chord_does():
    passthrough = ChordMatcher([binding("observe", "win", suppress=False)])
    assert not passthrough.feed("left_win", True).suppress
    assert not passthrough.feed("left_win", False).menu_mask
    matcher = ChordMatcher([binding("paste", "shift+alt+z")])
    matcher.feed("left_alt", True)
    matcher.feed("left_shift", True)
    assert matcher.feed("z", True).suppress
    assert matcher.feed("z", False).suppress
    assert matcher.feed("left_alt", False).menu_mask


def test_reset_releases_action_clears_state_and_requests_pending_win_mask():
    matcher = ChordMatcher([binding("ptt", "ctrl+win")])
    matcher.feed("left_ctrl", True)
    matcher.feed("left_win", True)
    reset = matcher.reset()
    assert actions(reset) == [("ptt", "release", "reset")] and reset.menu_mask
    assert not actions(matcher.reset()) and not matcher.reset().menu_mask
    assert not actions(matcher.feed("left_win", False))
    matcher.feed("right_ctrl", True)
    assert actions(matcher.feed("right_win", True)) == [("ptt", "press", "physical")]


def test_alias_and_side_specific_conflicts_are_detected_but_prefixes_are_valid():
    rows = [binding("a", "ctrl+win"), binding("b", "Control+Windows"), binding("c", "left ctrl+win"),
            binding("d", "ctrl+win+space")]
    assert conflicts(rows) == [("a", "b"), ("a", "c"), ("b", "c")]
    with pytest.raises(ValueError, match="conflict"):
        ChordMatcher(rows)
    with pytest.raises(ValueError):
        ChordMatcher([binding("same", "f9"), binding("same", "f10")])
    with pytest.raises(ValueError):
        ChordMatcher([binding(str(i), "f9") for i in range(65)])
