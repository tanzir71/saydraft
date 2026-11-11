import types

import pytest

from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.dictation import DictationContext
from saydraft.insert.inserter import InsertionResult


def make_processor(*, cleaner=None, history=None, inserter=None, formatter=None):
    events = []
    notifications = []
    cleaner = cleaner or types.SimpleNamespace(process_transcript=lambda raw, ctx: f"clean {raw}")
    history = history or types.SimpleNamespace(append=lambda entry: events.append(("history", entry)) or 1)
    inserter = inserter or types.SimpleNamespace(insert_text=lambda text, **kw: events.append(("insert", text, kw))
                                                or InsertionResult("inserted", "paste"))
    processor = TranscriptProcessor(cleaner=cleaner, formatter=formatter or IdentityFormatter(),
                                    history=history, inserter=inserter, notify=notifications.append)
    return processor, events, notifications


def process(processor, raw="words", **kwargs):
    return processor.process(raw, target=kwargs.pop("target", TargetContext("start-hwnd", "Notepad")),
                             context=DictationContext(mode="balanced", profile="notes"),
                             model="base", **kwargs)


def test_persists_both_versions_before_paste_to_captured_target():
    processor, events, _notifications = make_processor()
    result = process(processor, duration_seconds=3.25)
    assert [event[0] for event in events] == ["history", "insert"]
    entry = events[0][1]
    assert (entry.raw_text, entry.cleaned_text, entry.app_name) == ("words", "clean words", "Notepad")
    assert (entry.mode, entry.profile, entry.duration_seconds, entry.model) == ("balanced", "notes", 3.25, "base")
    assert events[1] == ("insert", "clean words", {"start_focus": "start-hwnd", "app_title": "Notepad"})
    assert result.history_id == 1
    assert processor.last_result is result


def test_repeated_dictation_is_never_silently_suppressed():
    processor, events, _notifications = make_processor()
    process(processor)
    process(processor)
    assert [event[0] for event in events] == ["history", "insert", "history", "insert"]


def test_history_only_note_never_calls_inserter():
    processor, events, _notifications = make_processor()
    result = process(processor, insert_text=False)
    assert [event[0] for event in events] == ["history"]
    assert result.insertion.reason == "history_only"


def test_focus_change_preserves_history_and_notifies():
    inserter = types.SimpleNamespace(insert_text=lambda *a, **kw: InsertionResult("skipped_focus_changed", "none"))
    processor, events, notifications = make_processor(inserter=inserter)
    result = process(processor)
    assert events[0][1].cleaned_text == "clean words"
    assert result.insertion.status == "skipped_focus_changed"
    assert notifications == ["Copied to history; focus changed before insertion."]


@pytest.mark.parametrize("failure", ["exception", "empty"])
def test_cleanup_failure_preserves_raw_words(failure):
    def clean(raw, context):
        if failure == "exception":
            raise RuntimeError("model failed")
        return ""
    processor, events, _notifications = make_processor(cleaner=types.SimpleNamespace(process_transcript=clean))
    result = process(processor)
    assert result.cleaned_text == "words"
    assert events[0][1].raw_text == events[0][1].cleaned_text == "words"


def test_formatting_failure_falls_back_to_cleaned_text():
    def broken_formatter(*args):
        raise ValueError("formatter failed")
    processor, _events, _notifications = make_processor(formatter=types.SimpleNamespace(format=broken_formatter))
    assert process(processor).cleaned_text == "clean words"


def test_failed_history_never_pastes_and_keeps_all_failed_results():
    def broken_history(entry):
        raise OSError("disk full")
    processor, events, notifications = make_processor(history=types.SimpleNamespace(append=broken_history))
    first = process(processor, "first dictation")
    second = process(processor, "second dictation")
    assert events == []
    assert first.insertion.reason == second.insertion.reason == "history_unavailable"
    assert [result.raw_text for result in processor.pending_results] == ["first dictation", "second dictation"]
    assert len(notifications) == 2


def test_password_field_refuses_insertion_after_history():
    processor, events, _notifications = make_processor()
    result = process(processor, target=TargetContext("start-hwnd", "Login", is_password=True))
    assert result.insertion.reason == "password_field"
    assert [event[0] for event in events] == ["history"]


def test_unknown_target_refuses_insertion():
    processor, events, _notifications = make_processor()
    result = process(processor, target=TargetContext())
    assert result.insertion.reason == "unknown_target"
    assert [event[0] for event in events] == ["history"]


def test_insertion_error_leaves_both_versions_in_history():
    def broken_insert(*args, **kwargs):
        raise OSError("paste blocked")
    processor, events, _notifications = make_processor(inserter=types.SimpleNamespace(insert_text=broken_insert))
    result = process(processor)
    assert result.insertion.reason == "insertion_error"
    assert events[0][1].raw_text == "words"
    assert events[0][1].cleaned_text == "clean words"


def test_snippet_expansion_preserves_literal_backslashes_and_is_not_recursive():
    processor, _events, _notifications = make_processor()
    processor.snippets = {"path": r"C:\team\notes", "alias": "path"}
    assert process(processor, "path alias").cleaned_text == r"clean C:\team\notes path"
