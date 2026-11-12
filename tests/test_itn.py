import pytest

from saydraft.cleanup.llm.validate import validate_llm_output
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary
from saydraft.dictation.rules import apply_self_corrections


def test_pipeline_normalizes_before_repetition_without_corrupting_generated_entities_or_lists():
    pipeline = DictationPipeline(DictationConfig())
    context = DictationContext(mode="aggressive", profile="email")
    assert pipeline.process_transcript("call one one one two three four five six seven eight", context) == "Call 1112345678."
    assert pipeline.process_transcript("john at example dot com", context) == "john@example.com."
    assert pipeline.process_transcript("https colon slash slash example dot com slash cap hello", context) == (
        "https://example.com/cap hello.")
    assert pipeline.process_transcript("first two apples second three pears", DictationContext(profile="notes")) == (
        "1. 2 apples\n2. 3 pears")
    pipeline.glossary = Glossary(user_terms=("One",))
    assert pipeline.process_transcript("send One two files", context) == "Send One 2 files."



def test_raw_and_code_paths_bypass_itn_and_prose_intensity_controls_small_numbers():
    pipeline = DictationPipeline(DictationConfig())
    raw = "one one two files"
    assert pipeline.process_transcript(raw, DictationContext(mode="raw", profile="code/comments")) == raw
    assert pipeline.process_transcript("two files", DictationContext(app_group="code")) == "two files"
    assert pipeline.process_transcript("two files", DictationContext(intensity=2)) == "Two files"



@pytest.mark.parametrize("source,expected", [
    ("I actually agree", "I actually agree"), ("we actually care", "we actually care"),
    ("আমি actually একমত", "আমি actually একমত"), ("أنا actually أوافق", "أنا actually أوافق"),
    ("I do actually agree", "I do actually agree"),
    ("send it to John, actually Jane.", "send it to Jane."),
    ("send __GLOSSARY_0__ actually __GLOSSARY_1__", "send __GLOSSARY_1__"),
    ("keep __SPAN_0__ no wait __SPAN_1__", "keep __SPAN_1__"),
    ("use the old endpoint never mind the new endpoint", "use the new endpoint"),
])
def test_backtrack_ordering_preserves_unaffected_text_protected_tokens_and_meaningful_adverbs(source, expected):
    assert apply_self_corrections(source) == expected



def test_negative_currency_sign_is_a_validated_detail():
    result = validate_llm_output("Pay -$25 for this order", "Pay $25 for this order")
    assert not result.ok and result.reason == "amounts_changed"
    assert not validate_llm_output("Pay - $25 for this order", "Pay $25 for this order").ok
    assert not validate_llm_output("Count - 25 items", "Count 25 items").ok



def test_backtrack_commands_and_generated_quoted_details_preserve_their_boundaries():
    pipeline = DictationPipeline(DictationConfig())
    context = DictationContext(mode="aggressive")
    for source, expected in (
        ("send it to John actually Jane period", "Send it to Jane."),
        ("the total is two point five actually three point five", "The total is 3.5"),
        ("open quote I actually agree close quote", "“I actually agree”"),
        ("open quote john at example dot com close quote", "“john@example.com”"),
        ("v two point one", "v2.1"),
        ("call one one one", "Call 111"),
    ):
        assert pipeline.process_transcript(source, context) == expected



def test_address_words_that_resemble_fillers_are_protected_before_cleanup():
    pipeline = DictationPipeline(DictationConfig())
    context = DictationContext(mode="aggressive")
    assert pipeline.process_transcript("um at example dot com", context) == "um@example.com"
    assert pipeline.process_transcript("visit uh dot com", context) == "Visit uh.com"
    assert pipeline.process_transcript("keep uh.com unchanged", context) == "Keep uh.com unchanged"
    assert not validate_llm_output("Keep one.com unchanged", "Keep two.com unchanged").ok



@pytest.mark.parametrize("source,expected", [
    ("first two apples second three pears", "1. 2 apples\n2. 3 pears"),
    ("number one two apples number two three pears", "1. 2 apples\n2. 3 pears"),
    ("bullet point two apples", "- 2 apples"),
    ("shopping list: bullet two apples bullet three pears", "Shopping list:\n- 2 apples\n- 3 pears"),
    ("there is a bullet point on the page", "There is a bullet point on the page"),
    ("number one apples", "1. Apples"),
])
def test_list_commands_keep_counts_within_items_and_preserve_literal_noun_uses(source, expected):
    pipeline = DictationPipeline(DictationConfig())
    assert pipeline.process_transcript(source, DictationContext(profile="notes")) == expected


def test_explicit_intensity_is_preserved_through_processing_and_sqlite_history(tmp_path):
    from types import SimpleNamespace

    from saydraft.core.interfaces import TargetContext
    from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
    from saydraft.history import DictationHistoryStore

    history = DictationHistoryStore(tmp_path / "history.db")
    pipeline = DictationPipeline(DictationConfig())
    processor = TranscriptProcessor(cleaner=pipeline, formatter=IdentityFormatter(), history=history,
                                    inserter=SimpleNamespace(insert_text=lambda *args, **kwargs: None))
    result = processor.process("two reports", target=TargetContext("fixture", "Fixture"),
        context=DictationContext(mode="aggressive", intensity=2), model="fixture", insert_text=False)
    row = history.list_recent()[0]
    assert result.cleaned_text == row.cleaned_text == "Two reports" and row.intensity == 2
    assert row.raw_text == "two reports" and row.mode == "aggressive"
