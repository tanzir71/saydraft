import pytest

from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary
from saydraft.dictation.rules import apply_self_corrections


@pytest.mark.parametrize("source, expected", [
    ("send it to John Smith actually Jane", "send it to Jane"),
    ("call John actually Jane Doe", "call Jane Doe"),
    ("use the old endpoint actually the new production endpoint", "use the new production endpoint"),
    ("use old endpoint actually new production endpoint", "use new production endpoint"),
    ("book it tomorrow morning sorry Friday afternoon before lunch", "book it Friday afternoon before lunch"),
    ("send it to John actually Jane after lunch with the final report attached", "send it to Jane after lunch with the final report attached"),
    ("set priority high sorry very low", "set priority very low"),
    ("move the meeting to Friday at two actually Monday at three after lunch", "move the meeting to Monday at three after lunch"),
    ("send it to John actually Jane actually Priya", "send it to Priya"),
    ("call John actually Jane. bring apples scratch that oranges", "call Jane. bring oranges"),
    ("First save this. Send it to John, actually to Jane.", "First save this. Send it to Jane."),
    ("I will send it tomorrow scratch that we will send it on Friday after the review", "we will send it on Friday after the review"),
    ("bring apples never mind call Jane", "call Jane"),
    ("I can attend no actually I cannot attend", "I cannot attend"),
    ("I want blue I mean I like green", "I like green"),
    ("I will send it tomorrow scratch that I'm sending it on Friday", "I'm sending it on Friday"),
    ("I will send the draft actually I will send the final report", "I will send the final report"),
    ("send 東京 actually ঢাকা", "send ঢাকা"), ("call مُحَمَّد no sorry فاطمة", "call فاطمة"),
    ("pay -$25 actually -$35 before Friday", "pay -$35 before Friday"),
    ("keep __SPAN_0__ no wait __SPAN_1__ after lunch", "keep __SPAN_1__ after lunch"),
    ("send it to John\ncall Sam actually Priya", "send it to John\ncall Priya"),
    ("جاهز؟ call John actually Jane", "جاهز؟ call Jane"),
])
def test_explicit_backtracks_align_slots_names_restarts_and_continuations(source, expected):
    assert apply_self_corrections(source) == expected


@pytest.mark.parametrize("source, expected", [
    ("I bought it as a gift… as a present", "I bought it as a present"),
    ("I bought it as a small gift... as a present for you", "I bought it as a present for you"),
    ("use it for the demo — for the final presentation tomorrow", "use it for the final presentation tomorrow"),
    ("meet me at the old station… at the new office after lunch", "meet me at the new office after lunch"),
    ("I would like the blue one… I would like the red one", "I would like the red one"),
    ("we should send a draft… we should send the final report before lunch", "we should send the final report before lunch"),
    ("Please send the draft… Please send the report", "Please send the report"),
    ("use it as a gift… as a present… as a donation", "use it as a donation"),
    ("First save it. I want blue… I want red.", "First save it. I want red."),
    ("give it as a উপহার… as a подарок", "give it as a подарок"),
])
def test_pause_and_repeated_frame_identify_natural_restatements(source, expected):
    assert apply_self_corrections(source) == expected


@pytest.mark.parametrize("source", [
    "I actually agree", "The app actually responds quickly", "Sara is actually brilliant",
    "Rufe Hans actually Anna an", "John Smith actually Jane",
    "I really actually care", "I do not actually agree", "send it when John actually arrives",
    "I am sorry I missed the meeting", "I feel very sorry for her", "well I mean well",
    "what I mean is that we should go", "please scratch that itch", "the words scratch that mean redo",
    "there is no wait time today", "no, wait for me", "we have no wait list",
    "I work as a developer as a parent", "I work as a developer, as a parent",
    "as a gift and as a present", "as a gift… and as a present", "as a gift. As a present",
    "I like cats. I like dogs", "I like cats… and I like dogs", "I want blue… I want",
    "call John\nactually Jane", "call John? actually Jane", "call John؛ actually Jane",
    "call John actually\nJane", "call John actually? Jane", "as a gift…\nas a present",
    'write "as a gift… as a present"', 'say "send it to John actually Jane"',
    "keep `call John actually Jane`", "keep ```as a gift… as a present```",
    "send https://example.com/actually/Jane", "email sorry@example.com",
    "আমি actually একমত", "أنا actually أوافق", "send actuallý Jane",
])
def test_literal_adverb_apology_enumeration_boundary_and_incomplete_guards(source):
    assert apply_self_corrections(source) == source


def test_pipeline_applies_commands_itn_and_dictionary_protection_around_backtracks():
    pipeline = DictationPipeline(DictationConfig())
    pipeline.glossary = Glossary(protected_terms=("John Smith", "Jane Doe"))
    ctx = DictationContext(mode="aggressive", profile="email")
    assert pipeline.process_transcript("send it to John Smith actually Jane Doe after lunch", ctx) == (
        "Send it to Jane Doe after lunch.")
    assert pipeline.process_transcript("pay two dollars actually three dollars before Friday", ctx) == (
        "Pay $3 before Friday.")
    assert pipeline.process_transcript("I bought it as a gift ellipsis as a present", ctx) == (
        "I bought it as a present.")
    for context in (DictationContext(mode="raw"), DictationContext(profile="code/comments"), DictationContext(app_group="code")):
        assert pipeline.process_transcript("as a gift… as a present", context) == "as a gift… as a present"
    assert pipeline.process_transcript("as a gift… as a present", DictationContext()) == "As a gift… as a present"


def test_long_clauses_and_many_corrections_are_bounded_without_losing_final_words():
    import time

    source = "call John actually Jane. " * 2000
    started = time.perf_counter()
    assert apply_self_corrections(source) == "call Jane. " * 2000
    assert apply_self_corrections("word " * 30000) == "word " * 30000
    assert time.perf_counter() - started < 3.0
