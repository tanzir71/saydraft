import threading
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.client import CleanupReply
from saydraft.cleanup.llm.preparation import PromptPreparation
from saydraft.cleanup.llm.prompts import PromptHints
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from tests.test_cleanup_streaming import DONE, FakeModel, cleaner, frame


class DeferredThreads:
    def __init__(self):
        self.pending = []

    def __call__(self, *, target, **kwargs):
        return SimpleNamespace(start=lambda: self.pending.append(target))

    def run(self):
        self.pending.pop(0)()


def fixture(reply="prepared", *, prepare=True):
    threads, calls = DeferredThreads(), []
    manager = SimpleNamespace(generation=1, prepare=lambda: prepare)
    client = SimpleNamespace(manager=manager, prepare_prompt=lambda **kw: (
        calls.append(kw) or CleanupReply(None, reply)))
    return PromptPreparation(client, thread_factory=threads), threads, manager, calls


def test_latest_style_is_coalesced_and_preparation_contains_no_user_context():
    prep, threads, manager, calls = fixture()
    assert prep.request(PromptHints(app="private app", before_caret="private words", post_rules=True))
    assert prep.request(PromptHints(style="formal", post_rules=True))
    assert len(threads.pending) == 1 and prep.status["state"] == "warming"
    threads.run()
    assert calls == [{"style": "formal", "post_rules": True, "app": "", "group": "general", "timeout": 60}]
    assert prep.ready(PromptHints(style="formal", post_rules=True)) and prep.wait(0)
    assert not prep.ready(PromptHints(post_rules=True))
    assert prep.request(PromptHints(style="formal", post_rules=True)) and not threads.pending
    manager.generation = 2
    assert not prep.ready(PromptHints(style="formal", post_rules=True))
    assert prep.status["state"] == "unprepared" and prep.status["reason"] == "instance_changed"
    assert prep.request(PromptHints(style="formal", post_rules=True))
    threads.run()
    assert len(calls) == 2 and prep.ready(PromptHints(style="formal", post_rules=True))


def test_app_prefix_is_bounded_and_reprepared_without_warming_caret_or_glossary():
    prep, threads, _manager, calls = fixture()
    hints = PromptHints(app="a" * 200, group="g" * 80, before_caret="private caret", post_rules=True)
    prep.request(hints)
    threads.run()
    assert calls[0]["app"] == "a" * 120 and calls[0]["group"] == "g" * 40
    assert "private caret" not in repr(calls) and "a" * 120 not in repr(prep.status)
    assert prep.ready(hints) and not prep.ready(PromptHints(app="different", post_rules=True))


def test_style_changed_during_probe_is_prepared_after_current_work_without_another_thread():
    prep, threads, _manager, calls = fixture()
    original = prep.client.prepare_prompt

    def probe(**kwargs):
        if not calls:
            prep.request(PromptHints(style="casual", post_rules=True))
        return original(**kwargs)

    prep.client.prepare_prompt = probe
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert [call["style"] for call in calls] == ["neutral", "casual"] and not threads.pending
    assert prep.ready(PromptHints(style="casual", post_rules=True))


def test_failed_protocol_is_not_retried_in_same_instance_but_new_instance_can_prepare():
    prep, threads, manager, calls = fixture("prompt_incomplete")
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert not prep.ready(PromptHints(post_rules=True))
    assert not prep.request(PromptHints(post_rules=True)) and len(calls) == 1 and not threads.pending
    manager.generation = 2
    assert prep.request(PromptHints(post_rules=True))
    threads.run()
    assert len(calls) == 2


def test_missing_model_and_closed_queued_preparation_cannot_publish_ready():
    prep, threads, _manager, calls = fixture(prepare=False)
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert prep.status["reason"] == "model_not_ready" and not calls
    prep.request(PromptHints(post_rules=True))
    prep.close()
    threads.run()
    assert prep.status["state"] == "closed" and not prep.request(PromptHints(post_rules=True)) and not calls


@pytest.mark.parametrize("chunks,reason", [
    ([frame("Ready", finish="length"), DONE], "prepared"),
    ([frame("Ready", finish="stop"), DONE], "prepared"),
    ([frame("Ready", finish="length")], "prompt_incomplete"),
    ([frame(finish="tool_calls", tool_calls=[{"id": "fixture"}]), DONE], "prompt_incomplete"),
])
def test_static_probe_requires_complete_stream_and_never_returns_generated_text(chunks, reason):
    model = FakeModel(chunks)
    reply = cleaner(model).prepare_prompt(style="formal")
    assert reply.text is None and reply.reason == reason
    path, request = model.requests[-1]
    assert path == "/v1/chat/completions" and request["payload"]["max_tokens"] == 1
    message = request["payload"]["messages"][-1]["content"]
    assert '<transcript>Ready</transcript>' in message and 'style: "formal"' in message


def test_actual_pipeline_keeps_rules_while_background_probe_blocks_then_uses_prepared_client():
    started, release = threading.Event(), threading.Event()
    user_calls = []
    manager = SimpleNamespace(generation=1, prepare=lambda: True, close=lambda: setattr(manager, "generation", None))

    def probe(**kwargs):
        started.set()
        if not release.wait(3):
            return CleanupReply(None, "timeout")
        return CleanupReply(None, "prepared")

    client = SimpleNamespace(manager=manager, prepare_prompt=probe, clean=lambda text, **kw: (
        user_calls.append(text) or CleanupReply(text, "ok")))
    cfg = LocalLLMConfig(enabled=True, model_path="unit-fixture-not-a-model")
    local = LocalLLMCleaner(cfg, manager_factory=lambda cfg: manager, client_factory=lambda *a, **kw: client)
    pipeline = DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=local)
    try:
        assert pipeline.warm_for_context(DictationContext()) and started.wait(1)
        assert pipeline.process_transcript("send 2 files", DictationContext()) == "Send 2 files"
        assert pipeline.last_llm_decision == "prompt_warming" and not user_calls
        release.set()
        assert local._preparation.wait(2)
        assert pipeline.process_transcript("send 2 files", DictationContext()) == "Send 2 files"
        assert pipeline.last_llm_decision == "accepted" and len(user_calls) == 1
    finally:
        release.set()
        pipeline.close()
    assert local._preparation.status["state"] == "closed"


@pytest.mark.parametrize("context", [DictationContext(mode="raw"), DictationContext(profile="code/comments"),
                                     DictationContext(app_group="code")])
def test_raw_and_code_context_warming_never_constructs_a_model(context):
    local = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path="unused"),
        manager_factory=lambda cfg: pytest.fail("Raw/Code must not construct runtime"))
    assert not local.warm_for_context(context)


def test_close_during_probe_refuses_late_readiness():
    prep, threads, _manager, _calls = fixture()
    prep.client.prepare_prompt = lambda **kw: (prep.close() or CleanupReply(None, "prepared"))
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert prep.status["reason"] == "closed" and not prep.ready(PromptHints(post_rules=True))


def test_instance_replacement_during_probe_cannot_publish_readiness_for_the_successor():
    prep, threads, manager, _calls = fixture()
    prep.client.prepare_prompt = lambda **kw: (setattr(manager, "generation", 2) or CleanupReply(None, "prepared"))
    prep.request(PromptHints(post_rules=True))
    threads.run()
    assert prep.status["reason"] == "instance_changed" and not prep.ready(PromptHints(post_rules=True))
