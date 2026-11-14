import json

import pytest

from saydraft.asr.model_ids import PREVIEW_MODEL
from saydraft.config import default_config, sanitize_config
from saydraft.core.preview import PreviewResult, choose_preview_result, preview_eligibility
from tests.test_processing import make_processor, process


@pytest.mark.parametrize("pins,routing,language,tier,reason", [
    ([], True, "auto", "pro", None), (["en"], True, "auto", "pro", None),
    (["bn"], True, "auto", "pro", "english_only"),
    (["en", "ar"], True, "auto", "pro", "english_only"),
    ([], False, "en", "pro", None), ([], False, "ar", "pro", "english_only"),
    ([], True, "auto", "standard", "needs_pro"), ([], True, "auto", "pending", "needs_pro"),
])
def test_preview_policy_matches_language_and_tier(pins, routing, language, tier, reason):
    config = default_config()
    config["stt"].update(pinned_languages=pins, routing_enabled=routing, language=language)
    assert preview_eligibility(config, {"assessment": {"tier": tier}}) == reason


def test_missing_hardware_evidence_cannot_enable_preview():
    assert preview_eligibility(default_config(), None) == "needs_pro"
    assert preview_eligibility(default_config(), {"assessment": None}) == "needs_pro"


def test_streaming_is_off_by_default_and_needs_a_live_preview_opt_in():
    config = default_config()
    assert config["labs"] == {"live_preview": False, "use_streaming_result": False, "command_mode": False}
    config["labs"]["use_streaming_result"] = True
    assert not sanitize_config(config)["labs"]["use_streaming_result"]
    config["labs"]["live_preview"] = True
    assert sanitize_config(config)["labs"]["use_streaming_result"]


@pytest.mark.parametrize("complete,failed,enabled,primary,selected,review", [
    (True, False, False, "default words", False, False),
    (True, False, True, "default words", True, False),
    (False, True, True, "default words", False, False),
    (True, False, False, "", True, True),
    (False, True, False, "", True, True),
    (False, True, True, "", True, True),
])
def test_default_precedence_explicit_streaming_and_review_only_recovery(complete, failed, enabled, primary, selected, review):
    preview = PreviewResult("preview words", failed, complete, 16000, 0.1)
    choice = choose_preview_result(primary, "parakeet", "auto", preview, use_streaming=enabled)
    assert choice.used_preview is selected and choice.review_only is review
    assert choice.text == ("preview words" if selected else primary)
    assert choice.model == (PREVIEW_MODEL if selected else "parakeet")
    if selected and primary:
        assert {"type": "asr_alternative", "model": "parakeet", "text": primary} in choice.edits


def test_empty_preview_keeps_available_default_words():
    choice = choose_preview_result("default words", "parakeet", "en",
                                  PreviewResult("", True, False, 16000, 0.1), use_streaming=True)
    assert choice.text == "default words" and not choice.used_preview


def test_alternative_words_survive_history_failure_and_caller_metadata_mutation():
    def unavailable(entry):
        raise OSError("database unavailable")

    from types import SimpleNamespace

    processor, events, _notifications = make_processor(history=SimpleNamespace(append=unavailable))
    notes = [{"type": "asr_alternative", "text": "original default words"}]
    result = process(processor, "selected streaming words", edits=notes)
    notes[0]["text"] = "caller changed its data"
    assert result.edits[0]["text"] == "original default words"
    assert processor.pending_results == [result] and not events


def test_preview_recovery_words_are_saved_for_review_without_insertion():
    preview = PreviewResult("available partial words", True, False, 16000, 0.1, "queue_overflow")
    choice = choose_preview_result("", "parakeet", "auto", preview)
    processor, events, _notifications = make_processor()
    result = process(processor, choice.text, insert_text=not choice.review_only, edits=list(choice.edits))
    assert [event[0] for event in events] == ["history"]
    assert result.insertion.reason == "history_only"
    assert json.loads(events[0][1].edits_json)[0]["type"] == "preview_recovery"
