from types import SimpleNamespace

from dictation.llm_local import LocalLLMConfig, LocalLLMCleaner, build_cleanup_prompt
from dictation.types import DictationContext


def test_cleanup_prompt_includes_style_and_plain_text_contract():
    prompt = build_cleanup_prompt("hello world", tone_hint="formal")

    assert 'style: "formal"' in prompt
    assert "Return JSON" not in prompt
    assert "<transcript>hello world</transcript>" in prompt


def make_cleaner(tmp_path, *, enabled=True, reply=None):
    events = []
    manager = SimpleNamespace(warm=lambda: events.append("warm") or True,
                              close=lambda: events.append("close"))

    def manager_factory(config):
        events.append(("construct", config))
        return manager

    def client_factory(owner, **kwargs):
        def clean(text, **options):
            events.append(("clean", text, options))
            return reply or SimpleNamespace(text="Hello world.", reason="ok")
        return SimpleNamespace(manager=owner, clean=clean)

    cfg = LocalLLMConfig(enabled=enabled, model_path=str(tmp_path / "manual.gguf"), backend="vulkan",
                         timeout_ms=125, n_threads=2, n_gpu_layers=17)
    return LocalLLMCleaner(cfg, manager_factory=manager_factory, client_factory=client_factory), events


def test_construction_is_inactive_and_disabled_cleaner_never_constructs_runtime(tmp_path):
    cleaner, events = make_cleaner(tmp_path, enabled=False)
    assert not events and not cleaner.available() and not cleaner.warm()
    assert cleaner.clean("words") == (None, "disabled")
    cleaner.close()
    assert not events


def test_background_warm_and_contextual_cleanup_reuse_owned_client_without_legacy_python_model(tmp_path):
    cleaner, events = make_cleaner(tmp_path)
    assert cleaner.available() and not events
    assert cleaner.warm()
    context = DictationContext("aggressive", "email", "Mail", "email", "ar", "existing words")
    assert cleaner.clean_with_context("hello world", context=context, glossary=("Saydraft",)) == ("Hello world.", "ok")
    assert cleaner.clean("hello world", tone_hint="casual")[1] == "ok"
    constructed = [event[1] for event in events if isinstance(event, tuple) and event[0] == "construct"]
    assert len(constructed) == 1
    assert (constructed[0].backend, constructed[0].threads, constructed[0].context_size) == ("vulkan", 2, 4096)
    options = events[2][2]
    assert options["timeout"] == 0.125 and options["glossary"] == ("Saydraft",)
    hints = options["hints"]
    assert (hints.app, hints.group, hints.style, hints.intensity, hints.language, hints.before_caret) == (
        "Mail", "email", "formal", 4, "ar", "existing words")
    cleaner.close()
    before = len(events)
    assert not cleaner.warm() and cleaner.clean("late words") == (None, "disabled")
    assert len(events) == before and events[-1] == "close"


def test_runtime_or_client_initialization_failure_returns_fallback_and_closes_created_manager(tmp_path):
    events = []
    manager = SimpleNamespace(close=lambda: events.append("close"))

    def unavailable(*args, **kwargs):
        raise OSError("private path and model metadata")

    cleaner = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path=str(tmp_path / "manual.gguf")),
        manager_factory=lambda cfg: manager, client_factory=unavailable)
    assert cleaner.clean("words") == (None, "unavailable") and events == ["close"]
    assert not cleaner.warm() and events == ["close", "close"]


def test_closure_while_cleaning_refuses_late_candidate(tmp_path):
    cleaner, _events = make_cleaner(tmp_path)
    cleaner.warm()

    def late(*args, **kwargs):
        cleaner.close()
        return SimpleNamespace(text="late words", reason="ok")

    cleaner._client.clean = late
    assert cleaner.clean("words") == (None, "closed")


def test_explicit_context_intensity_overrides_legacy_mode_in_prompt_hints(tmp_path):
    cleaner, events = make_cleaner(tmp_path)
    cleaner.clean_with_context("hello world", context=DictationContext(mode="aggressive", intensity=2))
    assert events[-1][0] == "clean" and events[-1][2]["hints"].intensity == 2
    cleaner.close()

