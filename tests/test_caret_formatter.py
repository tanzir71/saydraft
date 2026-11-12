from dataclasses import replace

import pytest

from saydraft.cleanup.formatter import caret_layout, layout_hints
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary


def context(before="", after="", **kwargs):
    return DictationContext(before_caret=before, before_caret_known=True,
        selection_known=True, after_caret=after, after_caret_known=True, **kwargs)


@pytest.mark.parametrize("before,text,expected", [
    ("Dear Dr. ", "The report", "the report"),
    ("Done! ", "the report", "The report"),
    ("Done.\u201d ", "the report", "The report"),
    ("Heading\n  ", "the report", "The report"),
    ("1. ", "the report", "The report"),
    ("- ", "the report", "The report"),
    ("prefix ", "May", "May"), ("prefix ", "Will", "Will"),
    ("prefix ", "I agree", "I agree"), ("prefix ", "I'm ready", "I'm ready"),
    ("prefix ", "NASA", "NASA"), ("prefix ", "New York", "New York"),
    ("prefix ", '"The report"', '"The report"'),
    ("prefix ", "`The report`", "`The report`"),
    ("prefix ", "https://example.com/The", "https://example.com/The"),
    ("prefix ", "The@example.com", "The@example.com"),
    ("prefix ", "🙂", "🙂"), ("🙂", "🙂", "🙂"),
    ("before\n", "- Ready", "- Ready"),
])
def test_layout_preserves_meaning_at_sentence_and_literal_boundaries(before, text, expected):
    assert caret_layout(text, context(before)) == expected


@pytest.mark.parametrize("changes,expected", [
    ({"before_caret_known": False, "after_caret_known": False}, "The report"),
    ({"selection_known": False}, "The report"),
    ({"selection_truncated": True}, "The report"),
    ({"before_caret_known": False}, "The report "),
    ({"after_caret_known": False}, " the report"),
    ({"mode": "raw"}, "The report"),
    ({"profile": "code/comments"}, "The report"),
    ({"app_group": "code"}, "The report"),
])
def test_unknown_boundaries_and_verbatim_modes_do_not_guess(changes, expected):
    assert caret_layout("The report", replace(context("prefix", "s"), **changes)) == expected


def test_glossary_and_snippet_initial_case_survives_even_known_empty_field():
    glossary = Glossary(user_terms=("iPhone", "theProduct"))
    for text in glossary.user_terms:
        assert caret_layout(text, context(), glossary=glossary) == text
    hint = layout_hints(context("prefix "), "sig", "Thanks.", ("Thanks.",))
    assert hint.literal_prefix
    assert caret_layout("Thanks.", hint) == "Thanks."


@pytest.mark.parametrize("before,raw,expected", [
    ("prefix ", "cap hello", "Hello"),
    ("prefix ", "all caps hello", "HELLO"),
    ("prefix ", "iPhone accessories", "iPhone accessories"),
    ("", "iPhone accessories", "iPhone accessories"),
    ("prefix ", "working now", "working now"),
    ("", "working now", "Working now"),
])
def test_pipeline_respects_explicit_case_commands_and_recovers_only_source_initial(before, raw, expected):
    pipeline = DictationPipeline(DictationConfig())
    assert pipeline.process_transcript(raw, replace(context(before), mode="aggressive")) == expected


def test_cleanup_hint_keeps_only_one_lowercase_character_and_mixed_source_case_stays_ambiguous():
    hint = layout_hints(context("prefix "), "working now", "Working now")
    assert hint.source_initial_lower == "w"
    assert not hint.literal_prefix
    assert layout_hints(context("prefix "), "working with Working", "Working now").source_initial_lower == ""
    assert layout_hints(DictationContext(), "working now", "Working now").source_initial_lower == ""
