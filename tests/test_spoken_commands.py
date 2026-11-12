import pytest

from saydraft.cleanup.commands import render_commands
from saydraft.cleanup.llm.validate import validate_llm_output
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline


@pytest.mark.parametrize("source,expected", [
    ("hello comma world", "hello, world"),
    ("hello full stop world", "hello. world"),
    ("ready question mark", "ready?"),
    ("ready exclamation mark", "ready!"),
    ("one colon two semicolon three", "one: two; three"),
    ("well ellipsis maybe", "well… maybe"),
    ("hello dash world", "hello — world"),
    ("hello em dash world", "hello — world"),
    ("hello en dash world", "hello – world"),
    ("a well hyphen known issue", "a well-known issue"),
    ("hyphen header", "- header"),
    ("hyphen", "-"),
    ("john apostrophe s report", "john's report"),
    ("john apostrophe-s report", "john's report"),
    ("open paren hello close paren", "(hello)"),
    ("open parenthesis hello close parenthesis", "(hello)"),
    ("open bracket hello close bracket", "[hello]"),
    ("open quote hello close quote", "“hello”"),
    ("say open quote hello close quote now", "say “hello” now"),
    ("cap hello world", "Hello world"),
    ("please use cap hello here", "please use Hello here"),
    ("all caps urgent message", "URGENT message"),
    ("please write all caps urgent here", "please write URGENT here"),
    ("hello new line world", "hello\nworld"),
    ("hello new paragraph world", "hello\n\nworld"),
    ("hello newline world", "hello\nworld"),
])
def test_explicit_spoken_text_commands(source, expected):
    assert render_commands(source, convert_newlines=True) == expected


@pytest.mark.parametrize("source", [
    "the cap on spending remains", "a cap for the bottle", "update the cap table",
    "we write in all caps for headings", "the all caps style is optional",
    "cap table planning", "capitalization is useful", "the periodical arrived",
    "this is a hyphenated word", "please press enter",
])
def test_noun_substrings_and_app_actions_are_not_spoken_text_commands(source):
    assert render_commands(source) == source


def test_newline_and_punctuation_switches_are_independent():
    assert render_commands("hello comma world new line next", convert_newlines=True,
                           convert_punctuation=False) == "hello comma world\nnext"
    assert render_commands("hello comma world new line next", convert_newlines=False) == "hello, world new line next"


def test_pipeline_uses_existing_modes_and_preserves_literal_code_quotes_urls_and_glossary():
    pipeline = DictationPipeline(DictationConfig())
    assert pipeline.process_transcript("hello em dash world", DictationContext(mode="aggressive")) == "Hello — world"
    assert pipeline.process_transcript("hello em dash world", DictationContext(mode="balanced")) == "Hello em dash world"
    assert pipeline.process_transcript("hello em dash world", DictationContext(mode="raw")) == "hello em dash world"
    source = '`all caps urgent` “cap hello” https://example.com/cap'
    assert pipeline.process_transcript(source, DictationContext(mode="aggressive")) == source
    assert not validate_llm_output("Keep “exact words” unchanged", "Keep “other words” unchanged").ok


def test_generated_opening_marks_allow_sentence_capitalization_without_rewriting_existing_quotes():
    pipeline = DictationPipeline(DictationConfig())
    context = DictationContext(mode="aggressive")
    assert pipeline.process_transcript("open paren maybe close paren send it", context) == "(Maybe) send it"
    assert pipeline.process_transcript("open quote hello close quote", context) == "“Hello”"
    assert pipeline.process_transcript("“hello”", context) == "“hello”"


def test_capitalization_commands_remove_the_marker_but_never_change_protected_names_or_code():
    from saydraft.dictation.glossary import Glossary

    pipeline = DictationPipeline(DictationConfig())
    pipeline.glossary = Glossary(user_terms=("Saydraft",))
    context = DictationContext(mode="aggressive")
    assert pipeline.process_transcript("all caps Saydraft is ready", context) == "Saydraft is ready"
    assert pipeline.process_transcript("cap `exact_code` is ready", context) == "`exact_code` is ready"
