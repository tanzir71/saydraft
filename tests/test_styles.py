from dataclasses import replace

import pytest

from saydraft.cleanup.styles import GROUP_DEFAULTS, TONES, rule_options, style_for
from saydraft.config import default_config, load_config, save_config
from saydraft.core.preferences import select_context
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline


def test_style_corpus_covers_every_group_tone_and_level():
    from saydraft.eval import load_eval_corpus, run_eval
    from itertools import product
    cases = [case for case in load_eval_corpus() if case.id.startswith("style-v1-")]
    assert {(c.app_group, c.tone, c.intensity) for c in cases} == set(product(GROUP_DEFAULTS, TONES, range(1, 5)))
    assert len(cases) == 84 and run_eval(cases).failed == 0


def test_saved_style_matrix_and_app_override_precedence(tmp_path):
    cfg = default_config()
    cfg["dictation"]["styles"] = {"work_chat": {"tone": "formal", "intensity": 2}}
    path = tmp_path / "config.json"
    save_config(cfg, path)
    cfg = load_config(config_path=path)
    profiles = [{"exe": "slack.exe", "tone": "invented", "mode": "bad", "intensity": True},
        {"exe": "slack.exe", "site": "other.example", "tone": "casual", "intensity": 4},
        {"exe": "slack.exe", "tone": "very_casual", "intensity": 1}]
    context = select_context(cfg, profiles, "Workspace", app_group="work_chat", app_exe="SLACK.EXE")
    assert (context.tone, context.intensity, context.app_group) == ("very_casual", 1, "work_chat")
    inherited = select_context(cfg, profiles, None, app_group="work_chat", app_exe="teams.exe")
    assert (inherited.tone, inherited.intensity) == ("formal", 2)


def test_site_override_needs_exact_captured_host_and_legacy_title_profile_survives():
    cfg = default_config()
    profiles = [{"exe": "chrome.exe", "site": "mail.google.com", "tone": "formal", "intensity": 2},
        {"match": "Personal", "profile": "chat", "mode": "aggressive"}]
    site = select_context(cfg, profiles, "Inbox", app_exe="chrome.exe", app_site="mail.google.com")
    assert (site.tone, site.intensity) == ("formal", 2)
    title = select_context(cfg, profiles, "Personal Inbox", app_exe="chrome.exe", app_site="other.example")
    assert (title.profile, title.mode, title.tone, title.intensity) == ("chat", "aggressive", "casual", 4)


def test_invalid_matrix_fields_are_removed_without_changing_valid_preferences(tmp_path):
    cfg = default_config()
    cfg["dictation"]["styles"] = {"email": {"tone": "formal", "intensity": True, "prompt": "ignored"},
        "messages": {"tone": "invented", "intensity": 4}, "docs": [], "unknown": {"intensity": 1}}
    saved = save_config(cfg, tmp_path / "config.json")
    assert saved["dictation"]["styles"] == {"messages": {"intensity": 4}, "email": {"tone": "formal"}}


@pytest.mark.parametrize("group,tone", list(GROUP_DEFAULTS.items()))
def test_default_app_groups_select_the_documented_tone(group, tone):
    context = select_context(default_config(), [], None, app_group=group)
    assert (context.tone, context.intensity) == (tone, 3)


def test_four_levels_keep_words_light_cleanup_repetition_and_polished_fillers_distinct():
    pipeline = DictationPipeline(DictationConfig())
    text = "um like hello hello world."
    assert [pipeline.process_transcript(text, DictationContext(tone="casual", intensity=level))
        for level in range(1, 5)] == ["um like hello hello world.", "Like hello hello world.",
            "Like hello world.", "Hello world."]


def test_tone_casing_punctuation_and_protected_data_are_independent_of_group():
    pipeline = DictationPipeline(DictationConfig())
    context = DictationContext(app_group="messages", intensity=3, tone="formal")
    assert pipeline.process_transcript('send "iPhone" to a@example.com.', context) == 'Send "iPhone" to a@example.com.'
    assert pipeline.process_transcript("hello world.", replace(context, tone="casual")) == "Hello world"
    assert pipeline.process_transcript("hello world.", replace(context, tone="very_casual")) == "hello world"
    assert pipeline.process_transcript("hello world", context) == "Hello world."


@pytest.mark.parametrize("tone,text,expected", [
    ("very_casual", "one apples two Bananas", "1. apples\n2. Bananas"),
    ("very_casual", "bullet apples bullet Bananas", "- apples\n- Bananas"),
    ("formal", "one iPhone two NASA", "1. iPhone\n2. NASA"),
    ("formal", "one ßeta two apples", "1. ßeta\n2. Apples"),
])
def test_lists_follow_casing_policy_without_rewriting_names_or_expanding_letters(tone, text, expected):
    pipeline = DictationPipeline(DictationConfig())
    assert pipeline.process_transcript(text, DictationContext(app_group="docs", tone=tone, intensity=3)) == expected


def test_verbatim_raw_and_code_do_not_call_or_warm_the_prose_model():
    class Forbidden:
        def available(self):
            raise AssertionError("Must bypass prose model")
        def warm_for_context(self, context):
            raise AssertionError("Must bypass prose preparation")
    pipeline = DictationPipeline(DictationConfig(), llm_cleaner=Forbidden())
    for context in (DictationContext(intensity=1, tone="formal"), DictationContext(mode="raw", tone="formal"),
            DictationContext(app_group="code", tone="formal")):
        assert not pipeline.warm_for_context(context)
        pipeline.process_transcript("um hello hello", context)


def test_prompt_preparation_request_gate_and_history_share_selected_style(tmp_path):
    from types import SimpleNamespace as NS
    from saydraft.core.interfaces import TargetContext
    from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
    from saydraft.dictation.llm_local import LocalLLMCleaner, LocalLLMConfig
    from saydraft.history import DictationHistoryStore
    hints = []
    local = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path="authored", prepare_prompt=False))
    local._warm = lambda value: hints.append(value) or True
    local._clean = lambda text, value, *args, **kw: (hints.append(value) or text, "accepted")
    context = DictationContext(app_group="work_chat", tone="very_casual", intensity=2)
    assert local.warm_for_context(context)
    store = DictationHistoryStore(tmp_path / "history.db")
    pipeline = DictationPipeline(DictationConfig(), llm_cleaner=local)
    processor = TranscriptProcessor(cleaner=pipeline, formatter=IdentityFormatter(), history=store, inserter=NS())
    processor.process("hello team", target=TargetContext(app_group="work_chat"), context=context,
        model="authored", insert_text=False)
    row = store.list_recent()[0]
    assert [hint.style for hint in hints] == ["very_casual", "very_casual"]
    assert [hint.intensity for hint in hints] == [2, 2] and (row.style, row.intensity) == ("very_casual", 2)
    assert row.raw_text == row.cleaned_text == "hello team"
    assert style_for(context).intensity == rule_options(context).intensity == 2


def test_session_freezes_override_for_warm_cleanup_and_history_before_insertion():
    from tests.test_session_worker import make_worker
    from saydraft.core.interfaces import TargetContext
    worker, clock, executor, events, _signals, _keyboard = make_worker(queued=True)
    captured = []
    worker.services.context.capture = lambda: TargetContext("fixture", "Workspace", app_group="work_chat", app_exe="slack.exe")
    worker.services.profiles = [{"exe": "slack.exe", "tone": "very_casual", "intensity": 2}]
    worker.services.cleaner.warm_for_context = lambda context: captured.append(context)
    assert worker.start_recording()
    worker.services.profiles.clear()  # The recording keeps the settings captured at start.
    executor.drain()
    clock.now = 1
    worker.stop_recording()
    executor.drain()
    entry = next(event[1] for event in events if event[0] == "history")
    assert (captured[-1].tone, captured[-1].intensity) == (entry.style, entry.intensity) == ("very_casual", 2)
    assert [event[0] for event in events] == ["history", "insert"]
    worker.shutdown()
