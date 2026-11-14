import math

import pytest

from saydraft.ui.bar_motion import RmsEnvelope, insertion_message, shimmer_opacity


@pytest.mark.parametrize('reason', ['command_failed', 'command_recovery'])
@pytest.mark.parametrize('saved', [False, True])
def test_command_warnings_do_not_offer_the_dictation_only_paste_last_shortcut(reason, saved):
    title, detail = insertion_message(reason, saved=saved, paste_hint='Shift+Alt+Z')
    assert 'Shift+Alt+Z' not in detail
    assert ('History' in detail or 'recovery' in detail) and title


def test_envelope_reaches_63_percent_in_thirty_ms_and_decays_in_120_ms():
    envelope = RmsEnvelope(10.)
    envelope.sample(.125, 10.)
    assert envelope.advance(10.030) == pytest.approx(1 - math.exp(-1))
    peak = envelope.level
    envelope.sample(0, 10.030)
    assert envelope.advance(10.150) == pytest.approx(peak * math.exp(-1))


@pytest.mark.parametrize("rms,target", [(1., 1.), (-1., 0.), (float("nan"), 0.), (float("inf"), 0.)])
def test_envelope_rejects_nonfinite_levels_and_clamps_microphone_samples(rms, target):
    envelope = RmsEnvelope()
    envelope.sample(rms, 0)
    envelope.advance(1)
    assert envelope.level == pytest.approx(target)
    assert len(envelope.heights) == 14 and all(3 <= height <= 22 for height in envelope.heights)


def test_rewinding_the_clock_does_not_reverse_or_double_apply_smoothing():
    envelope = RmsEnvelope(2)
    envelope.sample(.125, 2)
    level = envelope.advance(2.03)
    assert envelope.advance(1) == level
    assert envelope.advance(2.03) == level


def test_shimmer_moves_left_to_right_and_is_periodic_without_changing_geometry():
    assert shimmer_opacity(0, .36) > shimmer_opacity(13, .36)
    assert shimmer_opacity(13, 1.92) > shimmer_opacity(0, 1.92)
    for index in range(14):
        assert .48 <= shimmer_opacity(index, .9) <= 1
        assert shimmer_opacity(index, .9) == pytest.approx(shimmer_opacity(index, 3.3))


def test_unconfirmed_paste_prevents_a_duplicate_and_disabled_shortcut_uses_history():
    assert "check for pasted text" in insertion_message("insertion_unconfirmed", saved=True, paste_hint="Shift+Alt+Z")[1]
    assert insertion_message("focus_changed", saved=True, paste_hint="")[1] == "Saved · open History to copy"
    assert "Saved" not in insertion_message("history_unavailable", saved=False, paste_hint="Shift+Alt+Z")[1]
