"""Explicit History retries share warm weights and never download models."""

import copy

from dataclasses import dataclass

from .router import ALL_LANGUAGES, ASR_MODELS


@dataclass(frozen=True)
class RetryOptions:
    model_id: str = ALL_LANGUAGES
    cleanup: str = "current"

    def __post_init__(self):
        if self.model_id not in ASR_MODELS or self.cleanup not in ("current", "off", "on"):
            raise ValueError("Choose a listed speech model and cleanup option")


def installed_retry_models():
    from saydraft.model_download import find_installed_model
    from saydraft.models.manifest import load_manifest

    return tuple((model["id"], model["label"]) for model in load_manifest()["models"]
        if model.get("role", "asr") == "asr" and model["id"] in ASR_MODELS
        and find_installed_model(model["id"]) is not None)


class AllLanguagesRetry:
    def __init__(self, config, primary, *, factory=None):
        self.config = config
        self.primary = primary
        self.factory = factory
        self._engines = {}
        self.model_id = ALL_LANGUAGES
        self.last_language = None
        self.last_timings = {}

    def transcribe(self, audio):
        return self.transcribe_with_model(audio, ALL_LANGUAGES)

    def transcribe_with_model(self, audio, model_id):
        RetryOptions(model_id)
        routed_retry = getattr(self.primary, "retry_with_model", None)
        if routed_retry is not None:
            text = routed_retry(audio, model_id)
            engine = self.primary
        else:
            if model_id not in self._engines:
                if getattr(self.primary, "model_id", None) == model_id:
                    language_view = getattr(self.primary, "with_language", None)
                    engine = language_view("auto") if language_view is not None else self.primary
                else:
                    from .selection import create_asr, select_model

                    config = copy.deepcopy(self.config)
                    select_model(config, model_id)
                    config["stt"]["language"] = "auto"
                    config["stt"]["local_files_only"] = True
                    engine = (self.factory or create_asr)(config)
                if len(self._engines) >= 2:
                    self._engines.pop(next(iter(self._engines)))
                self._engines[model_id] = engine
            engine = self._engines.pop(model_id)
            self._engines[model_id] = engine
            prepare = getattr(engine, "prepare", None)
            if prepare is not None:
                prepare()
            text = engine.transcribe(audio)
        self.model_id = model_id
        self.last_language = getattr(engine, "last_language", None)
        self.last_timings = dict(getattr(engine, "last_timings", {}))
        return text
