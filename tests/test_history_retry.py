import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.asr.retry import AllLanguagesRetry, RetryOptions, installed_retry_models
from saydraft.asr.router import ALL_LANGUAGES, AsrRouter
from saydraft.asr.model_ids import DEFAULT_MODEL, ENGLISH_MODEL
from saydraft.asr.whisper_ct2 import WhisperCT2Engine, WhisperEngineConfig
from saydraft.config import default_config
from saydraft.core.history_retry import RetryCleanup
from saydraft.core.processing import TranscriptProcessor, IdentityFormatter
from saydraft.data.audio import AudioStore
from saydraft.dictation.pipeline import DictationConfig, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.dictation.types import DictationContext
from saydraft.history import DictationHistoryStore, HistoryEntry
from tests.test_session_worker import make_worker


class LocalAI:
    model_id = "public-fixture-cleanup"

    def __init__(self, cfg):
        self.cfg, self.prepared, self.calls, self.closed = cfg, [], [], False
        self.on_prepare = self.on_clean = lambda: None

    def available(self):
        return self.cfg.enabled and not self.closed

    def prepare_for_review(self, context, *, cancelled):
        self.prepared.append(context)
        self.on_prepare()
        return not cancelled()

    def clean_after_rules(self, text, **kwargs):
        self.calls.append(text)
        self.on_clean()
        return text, "ok"

    def close(self):
        self.closed = True


def subject(tmp_path, *, enabled=False, queued=True):
    store = DictationHistoryStore(tmp_path / "history.sqlite")
    audio = AudioStore(tmp_path / "audio")
    path = str(audio.save(np.ones(16000, dtype=np.float32), 16000))
    store.append(HistoryEntry("Public editor", "Original public words", "Original public words.",
        "balanced", "notes", 1, DEFAULT_MODEL, app_group="docs", style="formal", intensity=3, audio_path=path))
    row = store.list_recent()[0]
    cfg = LocalLLMConfig(enabled=enabled, model_path="public-fixture.gguf")
    ai = LocalAI(cfg)
    pipeline = DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=ai)
    inserts, notifications = [], []
    processor = TranscriptProcessor(cleaner=pipeline, formatter=IdentityFormatter(), history=store,
        inserter=SimpleNamespace(insert_text=lambda *args, **kwargs: inserts.append(args)), notify=notifications.append)
    worker, _, executor, _, signals, _ = make_worker(queued=queued, processor=(processor, [], notifications))
    worker.services.audio_store, worker.services.history = audio, store
    calls = []
    asr = SimpleNamespace(model_id=ALL_LANGUAGES, last_language="en", last_timings={"stt": .1})
    def recognize(samples, model):
        calls.append(model)
        asr.model_id = model
        return "um hello team"
    asr.transcribe_with_model = recognize
    asr.transcribe = lambda samples: recognize(samples, ALL_LANGUAGES)
    worker.services.retry_asr = asr
    owned = []
    worker._retry_cleanup = RetryCleanup(factory=lambda cfg: owned.append(LocalAI(cfg)) or owned[-1])
    return SimpleNamespace(worker=worker, executor=executor, signals=signals, store=store, row=row,
        ai=ai, owned=owned, calls=calls, inserts=inserts, pipeline=pipeline, notifications=notifications)


@pytest.mark.parametrize("enabled,choice,used", [(False,"current",False),(True,"current",True),
    (True,"off",False),(False,"off",False),(False,"on",True),(True,"on",True)])
def test_retry_model_and_cleanup_choices_preserve_original_audio_settings_and_counts(tmp_path, enabled, choice, used):
    s = subject(tmp_path, enabled=enabled)
    original_config, original_cfg = copy.deepcopy(s.worker.services.config), s.pipeline.cfg
    from pathlib import Path
    audio_bytes = Path(s.row.audio_path).read_bytes()
    assert s.worker.retry_history(s.row, RetryOptions(ENGLISH_MODEL, choice))
    assert not s.worker.start_recording()
    s.executor.drain()
    rows = s.store.list_recent()
    assert len(rows) == 2 and rows[1] == s.row
    result = rows[0]
    assert result.raw_text == "um hello team" and result.asr_model == ENGLISH_MODEL
    assert result.style == "formal" and result.intensity == 3 and result.app_group == "docs"
    assert json.loads(result.edits_json) == [{"type":"asr_retry", "source_history_id":s.row.id,
        "model_id":ENGLISH_MODEL,"cleanup":choice}]
    assert result.llm_decision == ("accepted" if used else "disabled")
    assert result.llm_model == (LocalAI.model_id if used else None)
    assert bool(s.ai.calls or s.owned and s.owned[0].calls) is used
    assert not s.inserts and Path(s.row.audio_path).read_bytes() == audio_bytes
    assert s.worker.services.config == original_config and s.pipeline.cfg == original_cfg
    assert s.store.weekly_stats().dictations == 1
    # The next live cleanup still follows the original setting.
    before = len(s.ai.calls)
    s.pipeline.process_transcript("um hello team", DictationContext(profile="notes", intensity=3))
    assert len(s.ai.calls) == before + int(enabled)
    assert not s.worker.busy
    s.worker.shutdown()
    assert all(ai.closed for ai in s.owned)


@pytest.mark.parametrize("stage", ["queued", "asr", "prepare", "cleanup"])
def test_cancelled_retry_never_saves_partial_review_or_inserts(tmp_path, stage):
    s = subject(tmp_path, enabled=True)
    if stage == "asr":
        def cancelled_asr(samples, model):
            s.worker.cancel_history_retry()
            return "public words"
        s.worker.services.retry_asr.transcribe_with_model = cancelled_asr
    elif stage == "prepare":
        s.ai.on_prepare = s.worker.cancel_history_retry
    elif stage == "cleanup":
        s.ai.on_clean = s.worker.cancel_history_retry
    assert s.worker.retry_history(s.row, RetryOptions(DEFAULT_MODEL, "on"))
    if stage == "queued":
        s.worker.services.audio_store.load = lambda *args: pytest.fail("Cancelled queued retry read audio")
        assert s.worker.cancel_history_retry()
    s.executor.drain()
    assert s.store.list_recent() == [s.row] and not s.inserts
    assert not s.worker.services.processor.pending_results and not s.worker.busy
    assert ("history_retry_finished", 0) in s.signals
    assert not any("History is unavailable" in str(event) for event in s.signals)
    s.worker.shutdown()


def test_shutdown_during_retry_cleanup_construction_retires_the_late_owner(tmp_path):
    s = subject(tmp_path)
    def create(cfg):
        s.worker.shutdown()
        s.owned.append(LocalAI(cfg))
        return s.owned[-1]
    s.worker._retry_cleanup = RetryCleanup(factory=create)
    assert s.worker.retry_history(s.row, RetryOptions(DEFAULT_MODEL, "on"))
    s.executor.drain()
    assert s.owned[0].closed and not s.owned[0].prepared
    assert s.store.list_recent() == [s.row] and not s.inserts


def test_changed_settings_cancel_a_queued_retry_before_rebuilding_services(tmp_path):
    s = subject(tmp_path)
    services = s.worker.services
    s.worker.services_factory = lambda config, **kwargs: replace(services, config=config)
    assert s.worker.retry_history(s.row, RetryOptions(DEFAULT_MODEL, "off"))
    config = copy.deepcopy(services.config)
    config["dictation"]["drop_message_period"] = False
    s.worker.configure(config)
    s.executor.drain()
    assert s.store.list_recent() == [s.row] and not s.calls
    assert s.worker.services.config == config and not s.worker.busy
    s.worker.shutdown()


def test_model_retry_uses_local_factories_bounded_cache_and_never_changes_configuration():
    config, calls = default_config(), []
    config["stt"]["local_files_only"] = False
    original = copy.deepcopy(config)
    def factory(selected):
        calls.append(copy.deepcopy(selected))
        return SimpleNamespace(transcribe=lambda audio: "Public words", last_language="en", last_timings={})
    retry = AllLanguagesRetry(config, SimpleNamespace(), factory=factory)
    for model in (DEFAULT_MODEL, ENGLISH_MODEL, ALL_LANGUAGES, ENGLISH_MODEL):
        assert retry.transcribe_with_model(np.ones(16000), model) == "Public words"
        assert retry.model_id == model
    assert len(calls) == 3 and len(retry._engines) == 2
    assert all(c["stt"]["local_files_only"] and not c["stt"]["routing_enabled"] for c in calls)
    assert config == original


def test_router_manual_model_does_not_change_the_next_live_route():
    config = default_config()
    routes = []
    def factory(cfg, route):
        routes.append(route)
        return SimpleNamespace(transcribe=lambda audio: "Public reasonable words", prepare=lambda: None,
            last_language="en", last_timings={})
    router = AsrRouter(config, engine_factory=factory, installed=lambda model: False)
    router.retry_with_model(np.ones(16000), ENGLISH_MODEL)
    assert router.model_id == ENGLISH_MODEL
    router.transcribe(np.ones(16000))
    assert router.model_id == DEFAULT_MODEL
    assert [route.model_id for route in routes] == [ENGLISH_MODEL, DEFAULT_MODEL]


def test_cold_legacy_whisper_language_view_cannot_download():
    calls = []
    primary = WhisperCT2Engine(WhisperEngineConfig(language="ar", local_files_only=False),
        model_factory=lambda *args, **kwargs: calls.append(kwargs) or object())
    view = primary.with_language("auto")
    view._load_model()
    assert calls[0]["local_files_only"] is True and primary._model is None
    assert primary.config.language == "ar" and primary.config.local_files_only is False


def test_installed_choices_exclude_dependencies_and_unavailable_models(monkeypatch):
    monkeypatch.setattr("saydraft.model_download.find_installed_model", lambda model: "local" if model==DEFAULT_MODEL else None)
    choices = installed_retry_models()
    assert len(choices) == 1 and choices[0][0] == DEFAULT_MODEL


@pytest.mark.parametrize("model,cleanup", [("unknown","off"),("silero-vad-v5","on"),(DEFAULT_MODEL,"unknown")])
def test_invalid_options_are_rejected(model, cleanup):
    with pytest.raises(ValueError):
        RetryOptions(model, cleanup)


def test_explicit_ai_preparation_observes_cancellation_and_keeps_model_paths_private(monkeypatch):
    llm = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path="C:/private-owner/custom.gguf"))
    monkeypatch.setattr(llm, "warm_for_context", lambda context: pytest.fail("Cancelled review warmed a model"))
    assert not llm.prepare_for_review(DictationContext(), cancelled=lambda: True)
    assert llm.model_id == "Local cleanup"


@pytest.mark.parametrize("state", ["ready", "failed", "cancelled", "timeout"])
def test_explicit_preparation_waits_only_for_the_requested_context_and_can_retire(monkeypatch, state):
    import threading
    cancelled = threading.Event()
    llm = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path="public.gguf"))
    seen = []
    def wait(timeout):
        assert 0 < timeout <= .1
        if state == "cancelled":
            cancelled.set()
        return True
    # A preparation belongs to an already constructed client. Stubbing warm
    # must supply that ownership pair rather than creating a new native client.
    llm._client = SimpleNamespace()
    monkeypatch.setattr(llm, "_manager_factory", lambda config: pytest.fail("Unexpected model construction"))
    llm._preparation = SimpleNamespace(wait=wait, ready=lambda hints:
        seen.append(hints) is None and state=="ready")
    monkeypatch.setattr(llm,"warm_for_context",lambda context: True)
    context = DictationContext(app_title="Public editor", app_group="docs", tone="formal", intensity=3)
    assert llm.prepare_for_review(context, cancelled=cancelled.is_set, timeout=0 if state=="timeout" else 1) is (state=="ready")
    if state in ("ready", "failed"):
        assert seen[0].style == "formal" and seen[0].app == "Public editor" and seen[0].group == "docs"


def test_known_cleanup_model_is_recorded_by_catalog_id_without_a_local_path():
    llm = LocalLLMCleaner(LocalLLMConfig(model_path="C:/private-owner/Qwen_Qwen3.5-0.8B-Q4_K_M.gguf"))
    assert llm.model_id == "qwen35-08b-q4-k-m"
