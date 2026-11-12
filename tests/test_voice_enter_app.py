import json
from types import SimpleNamespace

import pytest

from saydraft.core.interfaces import TargetContext
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.history import DictationHistoryStore
from tests.test_processing import make_processor
from tests.test_voice_enter import fake_inserter


def setup_processor(*, enabled=True, cleaner=None, history=None):
    inserter, keys, focus, _ = fake_inserter()
    cleaner = cleaner or DictationPipeline(DictationConfig())
    processor, events, notifications = make_processor(cleaner=cleaner, history=history, inserter=inserter)
    processor.voice_enter_enabled = enabled
    return processor, events, keys, notifications


def run(processor, text="hello press enter", *, context=None, target=None, **kw):
    return processor.process(text, target=target or TargetContext("same", "Fixture"),
        context=context or DictationContext(), model="fixture", **kw)


def test_original_raw_and_command_metadata_are_persisted_before_paste_and_enter(tmp_path):
    history = DictationHistoryStore(tmp_path / "history.db")
    processor, _, keys, _ = setup_processor(history=history)
    original = processor.inserter.keyboard.send
    def send(key):
        row = history.list_recent()[0]
        assert row.raw_text == "hello press enter" and row.cleaned_text == "Hello"
        assert json.loads(row.edits_json) == [{"type": "voice_enter", "requested": True}]
        original(key)
    processor.inserter.keyboard.send = send
    result = run(processor)
    assert result.insertion.enter_sent and result.cleaned_text == "Hello"
    assert keys == [("copy", "Hello"), ("send", "ctrl+v"), ("copy", "before"), ("send", "enter")]


@pytest.mark.parametrize("context, extra, expected", [
    (DictationContext(mode="raw"), {}, "hello"),
    (DictationContext(profile="code/comments"), {}, "hello"),
    (DictationContext(), {"target": TargetContext("same", "IDE", app_group="code")}, "hello"),
])
def test_enabled_delivery_is_separate_from_raw_or_code_cleanup(context, extra, expected):
    processor, _, _, _ = setup_processor()
    result = run(processor, context=context, **extra)
    assert result.cleaned_text == expected and result.insertion.enter_sent


@pytest.mark.parametrize("context, extra", [
    (DictationContext(), {}), (DictationContext(profile="email"), {}),
    (DictationContext(profile="notes"), {}),
    (DictationContext(), {"target": TargetContext("same", "Mail", app_group="email")}),
    (DictationContext(), {"target": TargetContext("same", "Document", app_group="docs")}),
    (DictationContext(), {"insert_text": False}),
])
def test_default_off_email_docs_and_history_only_cannot_submit(context, extra):
    processor, events, keys, _ = setup_processor(enabled=bool(extra or context.profile != "general"))
    result = run(processor, context=context, **extra)
    assert "press enter" in result.cleaned_text.lower() and not result.insertion.enter_sent
    assert ("send", "enter") not in keys and events[0][1].edits_json == "[]"


@pytest.mark.parametrize("source, expansion, expected_enter", [
    ("signature", "Hello press enter", False),
    ("signature press enter", "Thanks. Talk soon.", True),
    ("signature press enter", "Hello press enter", True),
])
def test_snippet_expansion_cannot_create_or_multiply_delivery_intent(source, expansion, expected_enter):
    processor, _, keys, _ = setup_processor()
    processor.snippets = {"signature": expansion}
    result = run(processor, source)
    assert result.cleaned_text == expansion
    assert result.insertion.enter_sent == expected_enter
    assert keys.count(("send", "enter")) == int(expected_enter)


def test_cleanup_generated_command_stays_text_and_cleanup_failure_preserves_source_intent():
    cleaner = SimpleNamespace(process_transcript=lambda text, context: "Hello press enter")
    processor, _, keys, _ = setup_processor(cleaner=cleaner)
    assert not run(processor, "hello").insertion.enter_sent
    assert ("send", "enter") not in keys
    def failed(text, context):
        raise OSError("injected cleanup failure")
    cleaner.process_transcript = failed
    result = run(processor)
    assert result.cleaned_text == "hello" and result.insertion.enter_sent


def test_snippets_are_protected_from_fillers_itn_model_edits_and_duplicate_email_punctuation():
    processor, _, _, _ = setup_processor()
    processor.snippets = {"um": "Regards.", "one": "one one one", "sig": "other", "other": "recursive"}
    assert run(processor, "um", context=DictationContext(profile="email")).cleaned_text == "Regards."
    assert run(processor, "one", context=DictationContext(mode="aggressive")).cleaned_text == "one one one"
    assert run(processor, "sig").cleaned_text == "other"


def test_snippet_values_never_reach_the_model_and_cannot_be_lost_with_a_changed_placeholder():
    calls = []
    def model_clean(text, **kw):
        calls.append(text)
        return text.replace("__SPAN_", "__BAD_"), "ok"
    pipeline = DictationPipeline(DictationConfig(), llm_cleaner=SimpleNamespace(available=lambda: True, clean=model_clean))
    processor, _, _, _ = setup_processor(cleaner=pipeline)
    processor.snippets = {"sig": "Never remove this damn thing."}
    assert run(processor, "sig").cleaned_text == "Never remove this damn thing."
    assert "sig" not in calls[0].casefold() and "damn" not in calls[0] and "__SPAN_" in calls[0]
    assert pipeline.last_llm_decision == "rejected:glossary_changed"


def test_accepted_model_terminal_period_does_not_duplicate_a_snippet_stop_or_erase_ellipsis():
    pipeline = DictationPipeline(DictationConfig(), llm_cleaner=SimpleNamespace(available=lambda: True,
        clean=lambda text, **kw: (text + ".", "ok")))
    processor, _, _, _ = setup_processor(cleaner=pipeline)
    processor.snippets = {"sig": "Regards."}
    assert run(processor, "sig", context=DictationContext(profile="email")).cleaned_text == "Regards."
    assert pipeline.last_llm_decision == "accepted"
    from saydraft.core.preferences import restore_snippets
    assert restore_snippets("__SPAN_0__...", {"__SPAN_0__": "Wait."}) == "Wait...."


@pytest.mark.parametrize("failure", ["history", "password", "unknown", "cancel"])
def test_delivery_guards_still_refuse_enter_and_paste_after_source_command_is_parsed(failure):
    processor, _, keys, _ = setup_processor()
    if failure == "history":
        processor.history.append = lambda entry: (_ for _ in ()).throw(OSError("full"))
    target = TargetContext(None if failure == "unknown" else "same", "Fixture", is_password=failure == "password")
    result = run(processor, target=target, enter_guard=lambda: failure != "cancel")
    assert result.insertion.status != "inserted" and not result.insertion.enter_sent and not keys
    assert result.raw_text == "hello press enter" and result.cleaned_text == "Hello"


def test_uncertain_native_enter_delivery_does_not_claim_that_no_key_reached_the_app():
    processor, _, keys, notifications = setup_processor()
    original = processor.inserter.keyboard.send
    def send(key):
        original(key)
        if key == "enter":
            raise OSError("partial native delivery")
    processor.inserter.keyboard.send = send
    result = run(processor)
    assert result.insertion.status == "inserted" and result.insertion.reason == "enter_failed"
    assert keys.count(("send", "ctrl+v")) == 1
    assert notifications == ["Text inserted; Enter delivery could not be confirmed."]


def test_worker_cancel_during_paste_suppresses_enter_and_next_session_resets_the_signal():
    import threading
    from tests.test_session_worker import make_worker

    processor, events, keys, _ = setup_processor()
    worker, clock, _, _, _, _ = make_worker(processor=(processor, events, []))
    worker.services.asr.transcribe = lambda audio: "hello press enter"
    worker.services.context.capture = lambda: TargetContext("same", "Fixture")
    sleepers, threads = [], []
    def sleep(seconds):
        sleepers.append(seconds)
        if len(sleepers) == 2:
            thread = threading.Thread(target=worker.cancel)
            threads.append(thread)
            thread.start()
            assert worker._cancel_request.wait(1)
    processor.inserter.sleep = sleep
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    for thread in threads:
        thread.join(1)
        assert not thread.is_alive()
    assert worker.last_result.insertion.reason == "enter_cancelled"
    assert keys.count(("send", "ctrl+v")) == 1 and ("send", "enter") not in keys
    processor.inserter.sleep = lambda seconds: None
    worker.start_recording()
    clock.now = 2
    worker.stop_recording()
    assert worker.last_result.insertion.enter_sent and keys.count(("send", "enter")) == 1
    worker.shutdown()
