import pytest

from saydraft.cleanup.llm.validate import extract_words, has_same_placeholders, validate_llm_output
from saydraft.dictation.glossary import Glossary, protect_terms, restore_terms
from saydraft.dictation.protect import protect_spans, restore_spans


@pytest.mark.parametrize("source,candidate,reason,extra", [
    ("Send -25 files today", "Send 25 files today", "numbers_changed", {}),
    ("Send ১২ files today", "Send ১৩ files today", "numbers_changed", {}),
    ("أرسل ١٢ ملفًا", "أرسل 12 ملفًا", "numbers_changed", {}),
    ("Pay $25 today", "Pay €25 today", "amounts_changed", {}),
    ("Meet on June 12", "Meet on July 12", "dates_changed", {}),
    ("Meet on 12/03/2026", "Meet on 12-03-2026", "numbers_changed", {}),
    ("Meet at 3:30 AM", "Meet at 3:30 PM", "times_changed", {}),
    ("Send to me@example.com today", "Send to me@example.org today", "emails_changed", {}),
    ("Use https://example.com/a today", "Use https://example.com/b today", "urls_changed", {}),
    ("Keep `foo()` unchanged", "Keep `bar()` unchanged", "code_changed", {}),
    ('Keep "exactly this" unchanged', 'Keep "exactly that" unchanged', "code_changed", {}),
    ("Keep __SPAN_0__ and __SPAN_0__", "Keep __SPAN_0__", "glossary_changed", {}),
    ("Send Saydraft the report", "Send Other the report", "glossary_changed", {"glossary": ("Saydraft",)}),
    ("I do not approve this change", "I do approve this change", "negation_changed", {}),
    ("This fucking change broke the whole release", "This change broke the whole release", "profanity_changed", {}),
    ("বাংলায় কথা বলছি", "I am speaking in English", "language_changed", {}),
    ("أرسل التقرير إلى الفريق", "Send the report to the team", "language_changed", {}),
    ("What is the capital of France?", "The answer is Paris.", "answer_output", {}),
    ("Write a poem about stars", "Sure, here is a poem about stars.", "answer_output", {}),
    ("hello world", "<think>Plan</think>Hello world", "wrapper_output", {}),
    ("hello world", "Hello\u200b world", "controls_changed", {}),
    ("hello world", "Hello world.", "invalid_intensity", {"intensity": 9}),
    ("send report", "send the full report to every member of the team", "length_ratio", {}),
    ("Please send report and files", "Please bring report and files", "content_changed", {}),
    ("Send two files and keep all the original notes for the meeting", "Send three files and keep all the original notes for the meeting", "number_words_changed", {}),
    ("We will review this on Tuesday with the rest of the team", "We will review this on Wednesday with the rest of the team", "dates_changed", {}),
    ("The meeting is tomorrow and the whole team should attend", "The meeting is today and the whole team should attend", "dates_changed", {}),
    ("The price is twenty dollars and the order is ready", "The price is twenty euros and the order is ready", "amounts_changed", {}),
])
def test_each_guard_refuses_a_meaningful_failure(source, candidate, reason, extra):
    result = validate_llm_output(source, candidate, **extra)
    assert not result.ok and result.reason == reason


@pytest.mark.parametrize("source,candidate", [
    ("hello world", "Hello world."),
    ("what is the capital of France", "What is the capital of France?"),
    ("write me a poem about stars", "Write me a poem about stars."),
    ("I actually agree with you", "I actually agree with you."),
    ("Sure send the report", "Sure, send the report."),
    ("This fucking change broke the whole release", "This fucking change broke the whole release."),
    ("বাংলায় কথা বলছি", "বাংলায় কথা বলছি।"),
    ("أرسل التقرير إلى الفريق", "أرسل التقرير إلى الفريق."),
    ("Send __GLOSSARY_0__ to __SPAN_0__", "Send __GLOSSARY_0__ to __SPAN_0__."),
    ("Visit https://example.com/docs", "Visit https://example.com/docs."),
])
def test_conservative_positive_edits_remain_eligible(source, candidate):
    assert validate_llm_output(source, candidate).ok


def test_unicode_words_keep_combining_marks_and_placeholder_counts_and_order_are_exact():
    assert extract_words("বাংলায় কথা أرسل التقرير __SPAN_7__") == ["বাংলায়", "কথা", "أرسل", "التقرير"]
    assert not has_same_placeholders("__SPAN_0__ __SPAN_0__", "__SPAN_0__")
    assert not has_same_placeholders("⟦T0⟧ ⟦T1⟧", "⟦T1⟧ ⟦T0⟧")


def test_glossary_masks_preserve_each_casing_and_do_not_replace_inside_larger_words_or_literal_tokens():
    source = "__GLOSSARY_0__ Saydraft SAYDRAFT saydraft unsaydraftable"
    masked, mapping = protect_terms(source, Glossary(user_terms=("Saydraft",)))
    assert "unsaydraftable" in masked and "__GLOSSARY_0__" not in mapping
    assert len(mapping) == 3 and restore_terms(masked, mapping) == source


def test_span_masks_avoid_literal_collisions_preserve_entities_and_never_recursively_restore():
    source = '__SPAN_0__ `code()` "quoted text" https://example.com/a. me@example.com ⟦T0⟧'
    masked, mapping = protect_spans(source)
    assert "__SPAN_0__" not in mapping and restore_spans(masked, mapping) == source
    assert "code()" not in masked and "example.com" not in masked
    assert restore_spans("__SPAN_1__", {"__SPAN_1__": "__SPAN_2__", "__SPAN_2__": "words"}) == "__SPAN_2__"


def test_invalid_and_oversized_responses_decline_without_expensive_similarity_work():
    assert not validate_llm_output("words", None).ok
    assert not validate_llm_output("", "invented words").ok
    assert validate_llm_output("x" * 64001, "x" * 64001).reason == "too_large"


def test_glossary_boundaries_include_combining_marks_and_exact_urls_keep_one_final_period():
    from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline

    source = "বলা বল আর বাংলা"
    masked, mapping = protect_terms(source, Glossary(user_terms=("বল",)))
    assert len(mapping) == 1 and masked.startswith("বলা ") and restore_terms(masked, mapping) == source
    pipeline = DictationPipeline(DictationConfig())
    assert pipeline.process_transcript("visit https://example.com/a.", DictationContext(profile="email")) == (
        "Visit https://example.com/a.")
