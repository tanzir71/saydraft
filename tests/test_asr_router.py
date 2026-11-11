from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.asr.languages import PARAKEET_LANGUAGES, WHISPER_LANGUAGES, normalize_pins
from saydraft.asr.router import (
    ALL_LANGUAGES, ASR_MODELS, AsrRouter, choose_fallback, choose_route, low_confidence_reason,
)
from saydraft.asr.sherpa_parakeet import DEFAULT_MODEL, ENGLISH_MODEL
from saydraft.config import default_config
from saydraft.models.manifest import get_model


@pytest.mark.parametrize("language,model_id,hint", [
    ("en", DEFAULT_MODEL, None), ("fr", DEFAULT_MODEL, None), ("ru", DEFAULT_MODEL, None),
    ("el", DEFAULT_MODEL, None), ("mt", DEFAULT_MODEL, None),
    ("ar", ALL_LANGUAGES, "ar"), ("bn", ALL_LANGUAGES, "bn"),
    ("zh", ALL_LANGUAGES, "zh"), ("ja", ALL_LANGUAGES, "ja"),
])
def test_single_pin_selects_supported_engine_and_language(language, model_id, hint):
    route = choose_route([language])
    assert (route.model_id, route.language) == (model_id, hint)


def test_language_registry_matches_pinned_parakeet_artifact_and_fallback_vocabulary():
    assert PARAKEET_LANGUAGES == set(get_model(DEFAULT_MODEL)["languages"])
    assert PARAKEET_LANGUAGES <= WHISPER_LANGUAGES
    assert {"bn", "ar", "zh", "yue"} <= WHISPER_LANGUAGES


def test_auto_english_max_and_mixed_pins_follow_the_router_matrix():
    assert choose_route().reason == "auto"
    assert choose_route(["en"], english_max=True).model_id == ENGLISH_MODEL
    assert choose_route(["en", "fr"], english_max=True).model_id == DEFAULT_MODEL
    assert choose_route(["en", "bn", "ar"]).model_id == ALL_LANGUAGES
    assert choose_route(["en", "bn", "ar"]).language is None
    assert normalize_pins(["EN", "fr", "en"]) == ("en", "fr")


@pytest.mark.parametrize("pins", [["xx"], ["en", "fr", "de", "ar"]])
def test_invalid_or_excessive_pins_are_rejected(pins):
    with pytest.raises(ValueError):
        choose_route(pins)


@pytest.mark.parametrize("model_id", sorted(ASR_MODELS))
def test_app_group_override_has_priority(model_id):
    route = choose_route(["bn"], app_group="work_chat", overrides={"work_chat": model_id})
    assert route.model_id == model_id and route.reason == "app_override"
    assert route.language == ("bn" if model_id.startswith("whisper-") else None)


@pytest.mark.parametrize("text,seconds,language,reason", [
    ("", 2, None, "empty"), ("yes", 10, None, "short_for_audio"),
    ("available words", 3, "ar", "language_outside_set"),
    ("مرحبا بالعالم", 2, None, "unsupported_script"),
    ("বাংলা ভাষায় বলুন", 3, None, "unsupported_script"),
    ("Γεια σου κόσμε", 3, None, None), ("Привет мир", 3, None, None),
    ("yes", 1, None, None), ("Normal transcript", 10, None, None),
])
def test_low_confidence_does_not_penalize_supported_greek_or_cyrillic(text, seconds, language, reason):
    assert low_confidence_reason(text, seconds, language) == reason


@pytest.mark.parametrize("installed,predicted,elapsed,budget,run,reason", [
    (False, 0.1, 0.1, 0.8, False, "optional_model_missing"),
    (True, None, 0.1, 0.8, False, "budget_exceeded"),
    (True, 0.5, 0.4, 0.8, False, "budget_exceeded"),
    (True, 0.1, 0.2, 0.8, True, "empty"),
])
def test_fallback_requires_installed_model_and_observed_budget(installed, predicted, elapsed, budget, run, reason):
    decision = choose_fallback(choose_route(), "", 3, installed=installed,
                               predicted_seconds=predicted, elapsed_seconds=elapsed, budget_seconds=budget)
    assert (decision.run, decision.reason) == (run, reason)
    assert decision.retry_available is (not run)


def test_explicit_route_does_not_trigger_automatic_model_switch():
    decision = choose_fallback(choose_route(["en"]), "", 3, installed=True, predicted_seconds=0.1)
    assert not decision.run and not decision.retry_available


class FakeEngine:
    def __init__(self, clock, text, *, language=None, seconds=0.05):
        self.clock, self.text = clock, text
        self.last_language = language
        self.last_timings = {"stt": seconds}
        self.seconds = seconds
        self.prepared = 0
        self.fail = False
        self.language_hints = []

    def prepare(self):
        self.prepared += 1

    def set_language(self, hint):
        self.language_hints.append(hint)

    def transcribe(self, audio):
        self.clock.now += self.seconds
        if self.fail:
            raise RuntimeError("native recognition failed")
        return self.text


def make_router():
    clock = SimpleNamespace(now=0.0)
    primary = FakeEngine(clock, "available words", language="ar", seconds=0.1)
    multilingual = FakeEngine(clock, "مرحبا بالعالم", language="ar")
    calls = []

    def factory(config, route):
        calls.append(route)
        return multilingual if route.model_id == ALL_LANGUAGES else primary

    config = default_config()
    config["stt"]["app_model_overrides"] = [{"app_group": "chat", "model_id": ALL_LANGUAGES}]
    router = AsrRouter(config, engine_factory=factory, installed=lambda model: True, clock=lambda: clock.now)
    return router, primary, multilingual, calls


def warm_multilingual(router):
    router.set_context(SimpleNamespace(app_group="chat"))
    router.prepare()
    router.transcribe(np.ones(16000, dtype=np.float32))
    router.set_context(SimpleNamespace(app_group="general"))


def test_cold_optional_model_is_not_loaded_for_automatic_retry():
    router, primary, multilingual, calls = make_router()
    router.prepare()
    assert router.transcribe(np.ones(16000, dtype=np.float32)) == "available words"
    assert len(calls) == 1 and multilingual.prepared == 0
    assert router.retry_recommended and router.last_fallback.reason == "budget_exceeded"


def test_warm_budgeted_retry_reuses_model_and_reports_actual_engine_language():
    router, primary, multilingual, calls = make_router()
    warm_multilingual(router)
    router.prepare()
    assert router.transcribe(np.ones(16000, dtype=np.float32)) == "مرحبا بالعالم"
    assert router.model_id == ALL_LANGUAGES and router.last_language == "ar"
    assert len(calls) == 2  # No second Whisper model for a changed language hint.
    assert router.models_used == [DEFAULT_MODEL, ALL_LANGUAGES]
    assert multilingual.language_hints[-1] == "auto"
    assert not router.retry_recommended


def test_failed_retry_retains_primary_words_and_offers_manual_retry():
    router, primary, multilingual, calls = make_router()
    warm_multilingual(router)
    multilingual.fail = True
    assert router.transcribe(np.ones(16000, dtype=np.float32)) == "available words"
    assert router.model_id == DEFAULT_MODEL
    assert router.retry_recommended and router.last_fallback.reason == "retry_failed"


def test_engine_cache_evicts_old_models_and_their_timing_estimates():
    router, primary, multilingual, calls = make_router()
    warm_multilingual(router)
    router.prepare()
    router.config["stt"]["app_model_overrides"].append({"app_group": "other", "model_id": ENGLISH_MODEL})
    router.set_context(SimpleNamespace(app_group="other"))
    router.prepare()
    assert len(router._engines) == 2
    assert ALL_LANGUAGES not in router._engines
    assert ALL_LANGUAGES not in router._observed


def test_audio_language_evidence_detects_fluent_wrong_language_and_counts_in_budget():
    router, primary, _multilingual, _calls = make_router()
    primary.last_language = None
    prepared = []

    def identify(audio):
        primary.clock.now += 0.7
        return "bn"

    router._language_identifier = SimpleNamespace(prepare=lambda: prepared.append(True), identify=identify)
    warm_multilingual(router)
    router.prepare()
    assert prepared == [True]
    assert router.transcribe(np.ones(16000)) == "available words"
    assert router.last_language == "bn" and router.last_lid_language == "bn"
    assert router.last_timings["lid"] == pytest.approx(0.7)
    assert router.last_fallback.reason == "budget_exceeded" and router.retry_recommended


def test_warm_retry_uses_audio_language_evidence_and_keeps_stage_totals():
    router, primary, _multilingual, _calls = make_router()
    primary.last_language = None
    router._language_identifier = SimpleNamespace(prepare=lambda: None, identify=lambda audio: "ar")
    warm_multilingual(router)
    router.prepare()
    assert router.transcribe(np.ones(16000)) == "مرحبا بالعالم"
    assert router.last_fallback.reason == "language_outside_set"
    assert sum(router.last_timings.values()) == pytest.approx(0.15)


def test_pinned_language_skips_audio_classifier_and_automatic_retry():
    router, primary, _multilingual, _calls = make_router()
    router.config["stt"]["pinned_languages"] = ["en"]
    router.set_context(SimpleNamespace(app_group="general"))
    router._language_identifier = SimpleNamespace()  # No prepare/identify methods allowed.
    primary.last_language = None
    router.prepare()
    assert router.transcribe(np.ones(16000)) == "available words"
    assert router.last_fallback.reason == "explicit_route" and router.last_lid_language is None
