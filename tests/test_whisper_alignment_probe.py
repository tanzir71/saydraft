"""Frozen comparison gates cannot hide a language regression or missing result."""

from copy import deepcopy

import pytest

from tools.bench_models import score
from tools import probe_whisper_alignment as probe


def paired_rows():
    rows = []
    for language, reference in [
        ("bn", "বাংলা ভাষা"),
        ("ta", "தமிழ் மொழி"),
        ("te", "తెలుగు భాష"),
    ]:
        for identifier in range(3):
            for arm in probe.ARMS:
                text = reference + " xxxx" if arm == "control" else reference
                rows.append(
                    {
                        "language": language,
                        "id": identifier,
                        "arm": arm,
                        "reference": reference,
                        "audio_sha256": f"{language}-{identifier}",
                        "text": text,
                        "scores": score(reference, text),
                        "error_type": None,
                    }
                )
    return rows


def test_complete_unicode_pairs_must_improve_every_language():
    result = probe.summarize(paired_rows())
    assert result["complete_pairs"] and result["development_gate_met"]
    assert all(result["languages"][lang]["passes"] for lang in ("bn", "ta", "te"))


def test_an_unchanged_language_fails_even_if_others_improve():
    rows = paired_rows()
    for row in rows:
        if row["language"] == "te":
            row["text"] = row["reference"]
            row["scores"] = score(row["reference"], row["text"])
    result = probe.summarize(rows)
    assert result["languages"]["bn"]["passes"] and result["languages"]["ta"]["passes"]
    assert (
        not result["languages"]["te"]["passes"] and not result["development_gate_met"]
    )


@pytest.mark.parametrize("failure", ["empty", "replacement", "error"])
def test_new_per_clip_failure_is_not_hidden_by_aggregate_improvement(failure):
    rows = paired_rows()
    row = rows[1]
    row["text"] = "" if failure == "empty" else row["reference"] + "\ufffd"
    if failure == "error":
        row["error_type"] = "RuntimeError"
    row["scores"] = score(row["reference"], row["text"])
    result = probe.summarize(rows)
    assert (
        not result["no_new_empty_or_replacement"] and not result["development_gate_met"]
    )


def test_partial_denominator_never_qualifies():
    result = probe.summarize(paired_rows()[:-1])
    assert not result["complete_pairs"] and not result["development_gate_met"]


@pytest.mark.parametrize("change", ["duplicate", "reference", "audio", "arm"])
def test_unequal_or_duplicated_pairs_are_rejected(change):
    rows = paired_rows()
    if change == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif change == "arm":
        rows[1]["arm"] = "unfrozen-candidate"
    else:
        rows[1]["audio_sha256" if change == "audio" else "reference"] += "changed"
    with pytest.raises(ValueError):
        probe.summarize(rows)


@pytest.mark.parametrize("change", ["holdout", "language", "count", "duplicate"])
def test_only_the_frozen_observed_development_selection_is_accepted(change):
    selection = {
        "scope": "Already-observed development clips",
        "clips": [
            {"language": language, "id": identifier}
            for language in ("bn", "ta", "te")
            for identifier in range(3)
        ],
    }
    assert len(probe.selected_clips(selection)) == 9
    if change == "holdout":
        selection["scope"] = "untouched confirmation"
    elif change == "language":
        selection["clips"][0]["language"] = "ar"
    elif change == "count":
        selection["clips"].pop()
    else:
        selection["clips"][-1] = selection["clips"][-2]
    with pytest.raises(ValueError):
        probe.selected_clips(selection)


def test_dirty_source_is_refused_before_any_model_or_audio_load(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.asr_accuracy._source", lambda: {"dirty": True})
    with pytest.raises(ValueError, match="Commit the probe"):
        probe.freeze(
            tmp_path / "not-read.json", tmp_path / "not-loaded", tmp_path / "result"
        )
    assert not (tmp_path / "result").exists()


@pytest.mark.parametrize(
    "change", ["missing", "unseen_id", "hash", "reference", "duplicate"]
)
def test_selection_requires_actual_matching_prior_inference(change):
    row = {"language": "bn", "id": 1}
    clip = {"sha256": "public-audio", "reference": "বাংলা ভাষা"}
    journal = [{**row, **clip, "model": "turbo"}]
    probe.require_observed(row, clip, journal, "turbo")
    if change == "missing":
        journal.clear()
    elif change == "unseen_id":
        row["id"] = 2
    elif change == "hash":
        journal[0]["sha256"] = "reserved-uninferred-audio"
    elif change == "reference":
        journal[0]["reference"] = "Changed reference"
    else:
        journal.append(deepcopy(journal[0]))
    with pytest.raises(ValueError, match="previously observed"):
        probe.require_observed(row, clip, journal, "turbo")
