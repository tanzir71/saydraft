import pytest

from saydraft.cleanup.llm.prompts import PromptHints, STYLES, build_messages
from saydraft.cleanup.llm.structure import rule_structure_reason
from saydraft.eval import EvalCase, execute_case
from tests.test_cleanup_bakeoff import pipeline_for


@pytest.mark.parametrize("source,candidate,reason", [
    ("Hello\n\nWorld!", "Hello World!", "rules_linebreaks_changed"),
    ("First\n\nSecond", "First\nSecond\n", "rules_paragraphs_changed"),
    ("First\n", "First\nNew words", "rules_paragraphs_changed"),
    ("First\r\nSecond", "First\nSecond", "rules_linebreaks_changed"),
    ("- Apples\n- Bananas", "Apples\nBananas", "rules_list_or_indent_changed"),
    ("1. Review\n2. Send", "2. Review\n1. Send", "rules_list_or_indent_changed"),
    ("  Review", "Review", "rules_list_or_indent_changed"),
    ("Ready? Yes.", "Ready. Yes.", "rules_punctuation_changed"),
    ("Wait...", "Wait.", "rules_punctuation_changed"),
    ("Wait…", "Wait", "rules_punctuation_changed"),
    ("هل أنت جاهز؟", "هل أنت جاهز.", "rules_punctuation_changed"),
    ("এটি প্রস্তুত।", "এটি প্রস্তুত", "rules_terminal_changed"),
    ("Ready.", "Ready", "rules_terminal_changed"),
])
def test_rendered_layout_and_strong_punctuation_cannot_be_lost(source, candidate, reason):
    assert rule_structure_reason(source, candidate) == reason


@pytest.mark.parametrize("source,candidate", [
    ("The files is ready", "The files are ready"),
    ("- The files is ready\n- Send tomorrow", "- The files are ready\n- Send tomorrow"),
    ("Is this ready?\n\nSend ⟦T0⟧.", "Is it ready?\n\nSend ⟦T0⟧."),
    ("Hello", "Hello."),  # Still a strict golden mismatch, not a layout refusal.
])
def test_finite_structure_guard_allows_grammar_and_is_not_an_exact_string_oracle(source, candidate):
    assert rule_structure_reason(source, candidate) is None


@pytest.mark.parametrize("style", sorted(STYLES))
def test_post_rules_examples_teach_existing_layout_without_inventing_a_final_period(style):
    messages = build_messages("Ready", hints=PromptHints(style=style, post_rules=True))
    pairs = list(zip(messages[1:-1:2], messages[2:-1:2]))
    assert len(pairs) == 8 and 'stage: "rules_cleaned"' in messages[-1]["content"]
    assert all('stage: "rules_cleaned"' in user["content"] for user, _ in pairs)
    agreement = next(answer["content"] for user, answer in pairs if "files is ready" in user["content"])
    assert agreement == "The files are ready for your review"
    assert any(answer["content"] == "Opening thought\n\nNext thought" for _, answer in pairs)
    assert any(answer["content"] == "- Apples\n- Bananas" for _, answer in pairs)
    assert any("fucking password" in answer["content"] for _, answer in pairs)
    assert 'stage: "transcript"' in build_messages("Ready")[-1]["content"]


@pytest.mark.parametrize("source,output,profile,reason", [
    ("Opening thought\n\nNext thought", "Opening thought\nNext thought", "notes", "rules_linebreaks_changed"),
    ("- Apples\n- Bananas", "Apples\nBananas", "notes", "rules_list_or_indent_changed"),
    ("Ready? Yes.", "Ready. Yes.", "general", "rules_punctuation_changed"),
    ("Wait...", "Wait.", "chat", "rules_punctuation_changed"),
])
def test_actual_client_refusal_keeps_rules_before_final_messaging_formatting(source, output, profile, reason):
    pipeline, observer = pipeline_for(output)
    try:
        result = execute_case(EvalCase("layout", source, source, "balanced", profile), pipeline)
        assert result.cleaned_text == source
        assert pipeline.last_llm_decision == reason
        assert observer.reply["source_tokens"] > 0
    finally:
        pipeline.close()


def test_remaining_grammar_edit_can_still_be_accepted_through_the_actual_client():
    pipeline, _ = pipeline_for("The files are ready for your review")
    try:
        result = execute_case(EvalCase("grammar", "The files is ready for your review", "The files are ready for your review",
                                       "balanced", "general"), pipeline)
        assert result.cleaned_text == "The files are ready for your review" and pipeline.last_llm_decision == "accepted"
    finally:
        pipeline.close()


def test_post_rules_stage_requires_an_actual_boolean():
    with pytest.raises(ValueError):
        PromptHints(post_rules="yes")
