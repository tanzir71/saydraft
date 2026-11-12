import pytest

from saydraft.cleanup.code_mode import render_code
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary


@pytest.mark.parametrize("source,expected", [
    ("camel case foo bar", "fooBar"), ("snake case foo bar", "foo_bar"),
    ("camelcase foo bar", "fooBar"), ("snakecase foo bar", "foo_bar"),
    ("kebabcase foo bar", "foo-bar"), ("pascalcase foo bar", "FooBar"), ("constantcase foo bar", "FOO_BAR"),
    ("kebab case foo bar", "foo-bar"), ("pascal case foo bar", "FooBar"),
    ("constant case foo bar", "FOO_BAR"), ("snake case HTTPServer", "http_server"),
    ("camel case foo_bar", "fooBar"), ("pascal case http server v2", "HttpServerV2"),
    ("snake case _private field", "_private_field"), ("camel case _private field", "_privateField"),
    ("camel case বাংলা নাম", "বাংলানাম"), ("snake case বাংলা নাম", "বাংলা_নাম"),
    ("constant case اسم المستخدم", "اسم_المستخدم"),
    ("git dash dash version", "git --version"), ("python dash m pytest", "python -m pytest"),
    ("foo dot bar", "foo.bar"), ("src slash app", "src/app"), ("foo underscore bar", "foo_bar"),
    ("foo hyphen bar", "foo-bar"), ("x equals y plus z", "x = y + z"),
    ("x equals open paren y plus z close paren", "x = (y + z)"),
    ("x double equals y", "x == y"), ("x triple equals y", "x === y"),
    ("x not equals y", "x != y"), ("x greater than or equal y", "x >= y"),
    ("x less than or equal y", "x <= y"), ("x pipe y", "x | y"),
    ("x double ampersand y", "x && y"), ("x double pipe y", "x || y"),
    ("print open paren open quote hello world close quote close paren", 'print("hello world")'),
    ("echo open single quote hello close single quote", "echo 'hello'"),
    ("items open bracket number zero close bracket", "items[0]"),
    ("open brace key colon value close brace", "{key: value}"),
    ("x equals number two plus number three", "x = 2 + 3"),
    ("number minus five", "-5"), ("number negative two point five", "-2.5"),
    ("camel case foo bar equals snake case user name", "fooBar = user_name"),
    ("at file app dot py", "@app.py"), ("at file src slash app dot py", "@src/app.py"),
    ("at file dot slash app dot py", "@./app.py"),
    ("at file dot dot slash app dot py", "@../app.py"),
    ("at file my hyphen app dot py", "@my-app.py"),
    ("python at file app dot py dash dash verbose", "python @app.py --verbose"),
    ("at file app.py", "@app.py"),
    ("at file plus dot py", "@plus.py"), ("at file hash dot json", "@hash.json"),
    ("def plus open paren x close paren colon", "def plus(x):"),
    ("let minus equals number two", "let minus = 2"),
    ("from math import plus", "from math import plus"), ("return plus", "return plus"),
    ("return minus number two", "return -2"),
    ("camel case foo bar new line snake case other value", "fooBar\nother_value"),
    ("    snake case foo bar", "    foo_bar"),
    ("print open paren x comma y close paren semicolon", "print(x, y);"),
])
def test_explicit_code_commands(source, expected):
    assert render_code(source) == expected


@pytest.mark.parametrize("source", [
    "foo foo", "um hello hello world", "like this is actually correct", "two files", "fooBar",
    "def foo(x):\n    return x", "\tfoo  bar\r\n    return x", "hello.",
    "def plus(x):\n    return x", "number = plus", "result: int = minus", "obj[plus]",
    "# camel case foo bar", "// snake case foo bar", "x = plus  # camel case foo bar",
    "'dot slash'", r'''"use \"dot slash\" here"''',
    "`camel case foo bar`", '"dot slash equals"', "“snake case foo bar”", "one@example.com",
    "https://example.com/slash", "foo.bar", "__CODE_LITERAL_0__", "__SPAN_0__", "⟦T0⟧",
    "camel case", "camel case 2 foo", "number of items", "at file",
])
def test_literal_or_unsupported_text_stays_exact(source):
    assert render_code(source) == source


def test_code_profile_and_group_use_same_commands_without_llm_or_prose_edits():
    class NoLLM:
        def available(self):
            raise AssertionError("Code mode must not consult a prose model")

    pipeline = DictationPipeline(DictationConfig(), llm_cleaner=NoLLM())
    for context in (DictationContext(profile="code/comments"), DictationContext(app_group="code")):
        assert pipeline.process_transcript("camel case foo bar", context) == "fooBar"
        assert pipeline.process_transcript("um hello hello world", context) == "um hello hello world"
        assert pipeline.process_transcript("def foo(x):\n    return x", context) == "def foo(x):\n    return x"
        assert pipeline.last_llm_decision == "bypassed"
    assert pipeline.process_transcript("camel case foo bar", DictationContext(mode="raw", app_group="code")) == (
        "camel case foo bar")


def test_protected_names_code_and_file_literals_restore_without_private_token_collisions():
    pipeline = DictationPipeline(DictationConfig())
    pipeline.glossary = Glossary(user_terms=("Saydraft",))
    context = DictationContext(profile="code/comments")
    assert pipeline.process_transcript("at file app.py", context) == "@app.py"
    assert pipeline.process_transcript("camel case Saydraft value", context) == "camel case Saydraft value"
    assert pipeline.process_transcript("`dot slash` camel case foo bar", context) == "`dot slash` fooBar"
    source = "__CODE_LITERAL_0_0__ at file app.py"
    assert pipeline.process_transcript(source, context) == "__CODE_LITERAL_0_0__ @app.py"


def test_typed_lines_and_nested_strings_restore_before_following_spoken_commands():
    source = 'value = "dot slash"\r\n    snake case user name'
    assert render_code(source) == 'value = "dot slash"\r\n    user_name'
    assert render_code("value = camel case user name") == "value = userName"
