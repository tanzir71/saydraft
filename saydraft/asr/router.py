"""Model routing decisions are pure; inference uses only already installed engines."""

from __future__ import annotations

import copy
import logging
import time
import unicodedata
from dataclasses import dataclass

import numpy as np

from .languages import PARAKEET_LANGUAGES, normalize_pins
from .sherpa_parakeet import DEFAULT_MODEL, ENGLISH_MODEL

logger = logging.getLogger(__name__)
ALL_LANGUAGES = "whisper-large-v3-turbo"
ASR_MODELS = frozenset((DEFAULT_MODEL, ENGLISH_MODEL, ALL_LANGUAGES,
                        "whisper-base", "whisper-small", "whisper-medium"))


@dataclass(frozen=True)
class Route:
    model_id: str
    language: str | None
    reason: str


@dataclass(frozen=True)
class Fallback:
    run: bool
    retry_available: bool
    reason: str


def choose_route(pins=(), *, english_max=False, app_group="general", overrides=None):
    pins = normalize_pins(pins)
    forced = (overrides or {}).get(app_group)
    if forced is not None:
        if forced not in ASR_MODELS:
            raise ValueError("Unknown per-app speech model")
        return Route(forced, pins[0] if len(pins) == 1 and forced.startswith("whisper-") else None,
                     "app_override")
    if not pins:
        return Route(DEFAULT_MODEL, None, "auto")
    if pins == ("en",) and english_max:
        return Route(ENGLISH_MODEL, None, "english_max")
    if all(code in PARAKEET_LANGUAGES for code in pins):
        return Route(DEFAULT_MODEL, None, "pinned_supported")
    return Route(ALL_LANGUAGES, pins[0] if len(pins) == 1 else None, "pinned_all_languages")


def low_confidence_reason(text, audio_seconds, language=None):
    if language and language not in PARAKEET_LANGUAGES:
        return "language_outside_set"
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return "empty"
    if audio_seconds >= 8 and len(letters) < 8:
        return "short_for_audio"
    # Greek and Cyrillic are legitimate Parakeet languages. Do not penalize them
    # merely for being non-Latin, as the original roadmap heuristic suggested.
    unsupported = sum(not unicodedata.name(char, "").startswith(("LATIN", "GREEK", "CYRILLIC"))
                      for char in letters)
    if unsupported / len(letters) > 0.4:
        return "unsupported_script"
    return None


def choose_fallback(route, text, audio_seconds, *, language=None, installed=False,
                    predicted_seconds=None, elapsed_seconds=0, budget_seconds=0.8):
    if route.reason != "auto" or route.model_id != DEFAULT_MODEL:
        return Fallback(False, False, "explicit_route")
    reason = low_confidence_reason(text, audio_seconds, language)
    if reason is None:
        return Fallback(False, False, "confident")
    if not installed:
        return Fallback(False, True, "optional_model_missing")
    if (predicted_seconds is None or predicted_seconds < 0 or
            elapsed_seconds + predicted_seconds > budget_seconds):
        return Fallback(False, True, "budget_exceeded")
    return Fallback(True, False, reason)


class AsrRouter:
    def __init__(self, config, *, engine_factory=None, installed=None, clock=time.perf_counter,
                 language_identifier=None):
        from .language_id import AudioLanguageIdentifier

        self.config = config
        self._factory = engine_factory or _engine_for_route
        self._installed = installed or _installed
        self._clock = clock
        self._engines = {}
        self._observed = {}
        self._route = self._choose()
        self.model_id = self._route.model_id
        self.last_language = None
        self.last_timings = {}
        self.last_fallback = None
        self.retry_recommended = False
        self.models_used = []
        self._language_identifier = language_identifier or AudioLanguageIdentifier()
        self.last_lid_language = None

    def _choose(self, app_group="general"):
        stt = self.config["stt"]
        overrides = {item["app_group"]: item["model_id"] for item in stt.get("app_model_overrides", [])}
        return choose_route(stt.get("pinned_languages", []), english_max=stt.get("english_max", False),
                            app_group=app_group, overrides=overrides)

    def set_context(self, target):
        self._route = self._choose(target.app_group)
        self.model_id = self._route.model_id
        self.last_language = None
        self.last_fallback = None
        self.retry_recommended = False
        self.models_used = []
        self.last_lid_language = None

    def _engine(self, route):
        key = route.model_id
        if key not in self._engines:
            if len(self._engines) >= 2:
                oldest = next(iter(self._engines))
                self._engines.pop(oldest)
                self._observed.pop(oldest, None)
            self._engines[key] = self._factory(self.config, route)
        engine = self._engines.pop(key)
        self._engines[key] = engine
        set_language = getattr(engine, "set_language", None)
        if set_language is not None:
            set_language(route.language or "auto")
        return engine

    def prepare(self):
        engine = self._engine(self._route)
        prepare = getattr(engine, "prepare", None)
        if prepare is not None:
            prepare()
        if self._needs_language_id():
            self._language_identifier.prepare()

    def _needs_language_id(self):
        return self._route.reason == "auto" or (
            self._route.reason == "pinned_supported"
            and len(normalize_pins(self.config['stt'].get('pinned_languages', ()))) > 1)

    @property
    def local_model_fingerprint(self):
        return getattr(self._engines.get(self._route.model_id), 'local_model_fingerprint', None)

    def local_model_files_current(self):
        check = getattr(self._engines.get(self._route.model_id), 'local_model_files_current', None)
        return check() if check is not None else None

    def retry_with_all_languages(self, audio):
        return self.retry_with_model(audio, ALL_LANGUAGES)

    def retry_with_model(self, audio, model_id):
        if model_id not in ASR_MODELS:
            raise ValueError("Unknown History speech model")
        engine = self._engine(Route(model_id, None, "manual_retry"))
        prepare = getattr(engine, "prepare", None)
        if prepare is not None:
            prepare()
        started = self._clock()
        text = engine.transcribe(audio)
        self._observed[model_id] = (len(np.asarray(audio)) / 16000, self._clock() - started)
        self.model_id = model_id
        self.last_language = getattr(engine, "last_language", None)
        self.last_timings = dict(getattr(engine, "last_timings", {}))
        return text

    def transcribe(self, audio):
        started = self._clock()
        engine = self._engine(self._route)
        text = engine.transcribe(audio)
        if self._route.model_id not in self.models_used:
            self.models_used.append(self._route.model_id)
        duration = len(np.asarray(audio)) / 16000
        self.model_id = self._route.model_id
        self.last_language = getattr(engine, "last_language", None) or self._route.language
        if self.last_language is None and self._route.reason == 'pinned_supported':
            pins = normalize_pins(self.config['stt'].get('pinned_languages', ()))
            if len(pins) == 1:
                self.last_language = pins[0]
        self.last_timings = dict(getattr(engine, "last_timings", {}))
        elapsed = self._clock() - started
        self._observed[self._route.model_id] = (duration, elapsed)
        self.last_lid_language = None
        if self._needs_language_id() and self.last_language is None:
            lid_started = self._clock()
            self.last_lid_language = self._language_identifier.identify(audio)
            self.last_language = self.last_lid_language
            self.last_timings["lid"] = self._clock() - lid_started
            elapsed = self._clock() - started
        prior = self._observed.get(ALL_LANGUAGES)
        predicted = (prior[1] * max(1, duration / max(prior[0], 0.01)) * 1.3) if (
            prior and ALL_LANGUAGES in self._engines) else None
        decision = choose_fallback(
            self._route, text, getattr(engine, "last_audio_seconds", duration),
            language=self.last_language or self.last_lid_language, installed=self._installed(ALL_LANGUAGES),
            predicted_seconds=predicted, elapsed_seconds=elapsed,
            budget_seconds=self.config["stt"].get("fallback_budget_ms", 800) / 1000)
        self.last_fallback = decision
        self.retry_recommended |= decision.retry_available
        if not decision.run:
            return text
        try:
            fallback = self._engine(Route(ALL_LANGUAGES, None, "fallback"))
            recovered = fallback.transcribe(audio)
            if recovered.strip():
                if ALL_LANGUAGES not in self.models_used:
                    self.models_used.append(ALL_LANGUAGES)
                self.model_id = ALL_LANGUAGES
                self.last_language = getattr(fallback, "last_language", None)
                self.last_timings["stt"] = max(0, self._clock() - started -
                                               self.last_timings.get("vad", 0) -
                                               self.last_timings.get("lid", 0))
                return recovered
        except Exception:
            logger.warning("Multilingual retry failed; preserving primary transcript")
            logger.debug("Multilingual retry detail", exc_info=True)
        self.last_fallback = Fallback(False, True, "retry_failed")
        self.retry_recommended = True
        self.last_timings["stt"] = max(0, self._clock() - started -
                                       self.last_timings.get("vad", 0) - self.last_timings.get("lid", 0))
        return text


def _installed(model_id):
    from saydraft.model_download import find_installed_model

    return find_installed_model(model_id) is not None


def _engine_for_route(config, route):
    from .selection import create_asr, select_model

    configured = copy.deepcopy(config)
    configured["stt"]["routing_enabled"] = False
    configured["stt"]["language"] = route.language or "auto"
    configured["stt"]["local_files_only"] = True
    select_model(configured, route.model_id)
    return create_asr(configured)
