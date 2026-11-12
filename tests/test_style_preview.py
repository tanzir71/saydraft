import json
from dataclasses import replace

import pytest

from saydraft.config import default_config
from saydraft.core.style_preview import StylePreviewRequest, render_style_preview
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary
from tests.test_session_worker import make_worker


def request(**values):
    cfg = default_config()
    return StylePreviewRequest(1, "um like hello hello world.", DictationContext(tone="casual", app_group="messages"),
        model_settings=json.dumps(cfg["llm"], sort_keys=True), **values)


def test_preview_uses_actual_snippet_enter_and_final_formatting_without_os_or_history():
    value = replace(request(), text="sig press enter", snippets=(("sig", "Thanks, Saydraft."),),
        voice_enter_enabled=True, glossary=Glossary(user_terms=("Saydraft",)))
    result = render_style_preview(value)
    assert result.text == "Thanks, Saydraft" and result.enter_requested
    assert result.request is value
    email = render_style_preview(replace(value, context=replace(value.context, app_group="email", tone="formal")))
    assert "press enter" in email.text and not email.enter_requested


@pytest.mark.parametrize("text", ["", "x" * 4097, None], ids=["empty", "oversized", "wrong_type"])
def test_invalid_preview_never_calls_model(text):
    class Forbidden:
        def available(self):
            raise AssertionError("No model on invalid preview")
    assert render_style_preview(replace(request(), text=text), llm=Forbidden()).decision == "invalid"


def test_ai_preview_is_serial_bounded_and_keeps_active_cleaner_metadata_and_history(caplog):
    worker, _clock, executor, events, signals, _ = make_worker(queued=True)
    calls = []
    class Model:
        def available(self):
            return True
        def warm_for_context(self, context):
            calls.append(("warm", context))
        def clean_with_context(self, text, **kw):
            calls.append(("clean", kw["context"]))
            return text, "ok"
    active = DictationPipeline(DictationConfig(), llm_cleaner=Model())
    active.last_llm_decision = "previous-dictation"
    worker.services.cleaner = active
    value = request()
    assert worker.preview_style(value) and worker.busy
    assert not worker.preview_style(value) and not events
    executor.drain()
    result = [args[0] for name, *args in signals if name == "style_preview_finished"][0]
    assert result.text == "Like hello world" and result.decision == "accepted"
    assert calls[-1][1].cleanup_deadline is not None
    assert active.last_llm_decision == "previous-dictation" and not events
    assert worker.last_result is None and worker.services.processor.last_result is None
    assert worker.services.recorder.started == 0 and "hello" not in caplog.text and not worker.busy
    worker.shutdown()


def test_unapplied_model_settings_and_queued_shutdown_do_not_call_cleaner():
    worker, _clock, executor, events, signals, _ = make_worker(queued=True)
    value = replace(request(), model_settings="different")
    assert worker.preview_style(value) and not worker.busy and not executor.jobs
    assert signals[-1][1].decision == "apply_settings"
    assert worker.preview_style(request())
    worker.shutdown()
    executor.drain()
    assert signals[-1][1].decision == "obsolete" and not events


def test_model_candidate_must_still_pass_the_real_validator():
    class Unsafe:
        def available(self):
            return True
        def clean_with_context(self, text, **kw):
            return text.replace("14", "99"), "ok"
    result = render_style_preview(replace(request(), text="send 14 files"), llm=Unsafe())
    assert result.text == "Send 14 files" and result.decision.startswith("rejected:")
