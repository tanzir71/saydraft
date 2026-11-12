import types

import pytest

from saydraft.cleanup.formatter import final_punctuation
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary


@pytest.mark.parametrize("text, expected", [
    ("See you soon.", "See you soon"), ("Thanks.  ", "Thanks  "), ("Thanks.\n", "Thanks\n"),
    ("We can ship", "We can ship"), ("Ready?", "Ready?"), ("Great!", "Great!"),
    ("Ready? Yes.", "Ready? Yes."), ("I agree. Let's go.", "I agree. Let's go."),
    ("Wait...", "Wait..."), ("Wait…", "Wait…"), ("Wait… please.", "Wait… please."),
    ("Ready。Go。", "Ready。Go。"), ("你好。", "你好"), ("হয়ে গেছে।", "হয়ে গেছে"),
    ("تم الأمر۔", "تم الأمر"), ("هل انتهيت؟ نعم.", "هل انتهيت؟ نعم."),
    ("Call Dr. Smith.", "Call Dr. Smith"), ("I live in the U.S.", "I live in the U.S."),
    ("Meet at 3 p.m.", "Meet at 3 p.m."), ("Send pens, paper, etc.", "Send pens, paper, etc."),
    ("Ask John A. Smith.", "Ask John A. Smith"), ("The value is 0.5.", "The value is 0.5"),
    ("A. This is next.", "A. This is next."), ("Buy pens etc. Bring paper.", "Buy pens etc. Bring paper."),
    ('He said "Ready. Go." yesterday.', 'He said "Ready. Go." yesterday.'),
    ("Use v2.1.", "Use v2.1"), ("Open example.com.", "Open example.com"),
    ("See https://example.com/v1.2.", "See https://example.com/v1.2"),
    ("Email a.b@example.com.", "Email a.b@example.com"),
    ('He said "ready.".', 'He said "ready."'), ('"Keep this."', '"Keep this."'),
    ("Use `x.y`.", "Use `x.y`"), ("Thanks (really).", "Thanks (really)"),
    ("1. Ready.", "1. Ready."), ("- Ready.", "- Ready."), ("• Ready.", "• Ready."),
    ("Ready\nGo.", "Ready\nGo."), ("", ""), ("   ", "   "), (".", "."),
])
def test_single_sentence_policy_preserves_literal_details_and_other_boundaries(text, expected):
    context = DictationContext(app_group="messages")
    assert final_punctuation(text, context) == expected
    assert final_punctuation(expected, context) == expected


@pytest.mark.parametrize("context, expected", [
    (DictationContext(app_group="work_chat"), "Ready"),
    (DictationContext(profile="chat"), "Ready"),
    (DictationContext(), "Ready."), (DictationContext(mode="raw", app_group="messages"), "Ready."),
    (DictationContext(profile="notes", app_group="messages"), "Ready."),
    (DictationContext(profile="email", app_group="messages"), "Ready."),
    (DictationContext(profile="chat", app_group="docs"), "Ready."),
    (DictationContext(profile="chat", app_group="email"), "Ready."),
    (DictationContext(profile="chat", app_group="code"), "Ready."),
    (DictationContext(profile="code/comments", app_group="messages"), "Ready."),
])
def test_context_and_explicit_profile_guards(context, expected):
    assert final_punctuation("Ready.", context) == expected


def test_toggle_and_protected_glossary_period_are_honored_after_model_cleanup():
    fake = types.SimpleNamespace(available=lambda: True,
        clean=lambda text, **kwargs: (text.rstrip(".") + ".", "ok"))
    context = DictationContext(app_group="work_chat")
    for enabled, expected in ((True, "Ready"), (False, "Ready.")):
        pipeline = DictationPipeline(DictationConfig(drop_message_period=enabled), llm_cleaner=fake)
        assert pipeline.process_transcript("ready", context) == expected
        assert pipeline.last_llm_decision == "accepted"
    pipeline = DictationPipeline(DictationConfig())
    pipeline.glossary = Glossary(protected_terms=("Acme.",))
    assert pipeline.process_transcript("ask Acme.", context) == "Ask Acme."


@pytest.mark.parametrize("raw, expected", [
    ("ask Dr. Smith.", "Ask Dr. Smith"), ("ask Dr. Smith. bring files.", "Ask Dr. Smith. Bring files."),
    ("use e.g. paper.", "Use e.g. paper"), ("meet at three p.m.", "Meet at 3 PM"),
])
def test_abbreviations_survive_prose_rules_without_blocking_time_itn(raw, expected):
    pipeline = DictationPipeline(DictationConfig())
    assert pipeline.process_transcript(raw, DictationContext(app_group="work_chat")) == expected


@pytest.mark.parametrize("raw, expected", [
    ('"Hello."', '"Hello."'), ("হয়ে গেছে।", "হয়ে গেছে।"), ("Thanks!", "Thanks!"),
    ("ask Dr. Smith", "Ask Dr. Smith."), ("I live in the U.S.", "I live in the U.S."),
    ("bullet point ready", "- Ready"),
])
def test_email_terminal_punctuation_runs_after_literal_restoration(raw, expected):
    pipeline = DictationPipeline(DictationConfig())
    assert pipeline.process_transcript(raw, DictationContext(profile="email")) == expected
