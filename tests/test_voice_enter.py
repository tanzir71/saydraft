from types import SimpleNamespace

import pytest

from saydraft.cleanup.delivery import DeliveryIntent, trailing_enter
from saydraft.dictation import DictationContext
from saydraft.insert.inserter import Inserter


@pytest.mark.parametrize("text, expected", [
    ("hello press enter", "hello"), ("hello, press enter.", "hello"),
    ("thank you press enter", "thank you"), ("Hello. PRESS ENTER", "Hello."),
    ("ধন্যবাদ press enter।", "ধন্যবাদ"), ("مرحبا press enter", "مرحبا"),
    ("line one\nline two press enter\n", "line one\nline two"),
    ("hello press\tenter!", "hello"), ('say "hello" press enter', 'say "hello"'),
    ("print('hello') press enter", "print('hello')"),
    ("press enter", None), ("press enter.", None), ("hello press enter?", None),
    ("hello press enter tomorrow", None), ("hello press\nenter", None),
    ('say "press enter"', None), ('say "press enter', None), ("say 'I'm ready press enter", None),
    ("say “press enter”,", None), ("keep `press enter`", None), ("keep `press enter", None),
    ("keep ```hello\npress enter", None), ("say press enter", None), ("the words press enter", None),
    ("how to press enter", None), ("can you press enter", None), ("the command press enter", None),
    ("open https://example.com/press enter", None), ("hellópress enter", None),
])
def test_explicit_original_text_suffix_and_literal_guards(text, expected):
    result = trailing_enter(text, DictationContext(), enabled=True)
    assert result == (DeliveryIntent(text) if expected is None else DeliveryIntent(expected, True))
    assert trailing_enter(text, DictationContext()) == DeliveryIntent(text)


@pytest.mark.parametrize("context, allowed", [
    (DictationContext(app_group="messages"), True), (DictationContext(app_group="work_chat"), True),
    (DictationContext(mode="raw"), True), (DictationContext(profile="code/comments"), True),
    (DictationContext(app_group="code"), True), (DictationContext(app_group="email"), False),
    (DictationContext(app_group="docs"), False), (DictationContext(profile="email"), False),
    (DictationContext(profile="notes", app_group="work_chat"), False),
])
def test_enabled_command_is_independent_of_prose_mode_and_never_runs_in_email_or_docs(context, allowed):
    assert trailing_enter("hello press enter", context, enabled=True) == (
        DeliveryIntent("hello", True) if allowed else DeliveryIntent("hello press enter"))


@pytest.mark.parametrize("text", ["# say press enter", "// hello press enter", "-- hello press enter"])
def test_typed_code_comments_remain_literal(text):
    assert trailing_enter(text, DictationContext(app_group="code"), enabled=True) == DeliveryIntent(text)


def fake_inserter(*, method="paste", sleep=lambda seconds: None):
    events, focus, state = [], {"value": "same"}, {"allowed": True}
    clipboard = SimpleNamespace(paste=lambda: "before", copy=lambda text: events.append(("copy", text)))
    keyboard = SimpleNamespace(send=lambda key: events.append(("send", key)),
                               write=lambda text: events.append(("write", text)))
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, sleep=sleep,
        focus_provider=lambda: focus["value"], profiles=[{"match": "test", "insertion": method}])
    return inserter, events, focus, state


@pytest.mark.parametrize("method", ["paste", "typing"])
def test_enter_is_sent_once_after_successful_text_delivery_and_clipboard_restoration(method):
    inserter, events, _, state = fake_inserter(method=method)
    result = inserter.insert_text("hello", start_focus="same", app_title="test", send_enter=True,
                                  enter_guard=lambda: state["allowed"])
    assert result.status == "inserted" and result.enter_sent
    assert events == ([("copy", "hello"), ("send", "ctrl+v"), ("copy", "before"), ("send", "enter")]
                      if method == "paste" else [("write", "hello"), ("send", "enter")])


@pytest.mark.parametrize("phase, change, reason", [
    (1, "focus", "focus_changed"), (2, "focus", "enter_focus_changed"),
    (1, "cancel", "cancelled"), (2, "cancel", "enter_cancelled"),
    (1, "unknown", "unknown_target"), (2, "unknown", "enter_unknown_target"),
])
def test_checks_before_paste_and_before_enter_block_changed_focus_or_cancelled_delivery(phase, change, reason):
    inserter, events, focus, state = fake_inserter()
    calls = []
    def sleep(seconds):
        calls.append(seconds)
        if len(calls) == phase:
            if change == "cancel":
                state["allowed"] = False
            else:
                focus["value"] = None if change == "unknown" else "other"
    inserter.sleep = sleep
    result = inserter.insert_text("hello", start_focus="same", send_enter=True,
                                  enter_guard=lambda: state["allowed"])
    assert result.reason == reason and not result.enter_sent
    assert ("send", "enter") not in events and events[-1] == ("copy", "before")
    assert (("send", "ctrl+v") in events) == (phase == 2)
    assert (result.status == "inserted") == (phase == 2)


def test_failed_enter_does_not_report_text_as_uninserted_or_retry_the_paste():
    inserter, events, _, _ = fake_inserter()
    def send(key):
        events.append(("send", key))
        if key == "enter":
            raise OSError("injected Enter failure")
    inserter.keyboard.send = send
    result = inserter.insert_text("hello", start_focus="same", send_enter=True)
    assert result.status == "inserted" and result.reason == "enter_failed" and not result.enter_sent
    assert events.count(("send", "ctrl+v")) == events.count(("send", "enter")) == 1


@pytest.mark.parametrize("failure", ["unknown", "cancelled", "guard_error"])
def test_unavailable_or_cancelled_delivery_before_text_never_touches_keyboard(failure):
    inserter, events, focus, _ = fake_inserter()
    def guard():
        if failure == "guard_error":
            raise RuntimeError("cannot observe cancellation")
        return failure != "cancelled"
    focus["value"] = None if failure == "unknown" else "same"
    assert not inserter.insert_text("hello", start_focus="same", send_enter=True, enter_guard=guard).enter_sent
    assert not events
