"""Explicit multilingual retries share warm weights and never download models."""

import copy

from .router import ALL_LANGUAGES


class AllLanguagesRetry:
    def __init__(self, config, primary, *, factory=None):
        self.config = config
        self.primary = primary
        self.factory = factory
        self._engine = None
        self.model_id = ALL_LANGUAGES
        self.last_language = None
        self.last_timings = {}

    def transcribe(self, audio):
        routed_retry = getattr(self.primary, "retry_with_all_languages", None)
        if routed_retry is not None:
            text = routed_retry(audio)
            engine = self.primary
        else:
            if self._engine is None:
                if (getattr(self.primary, "model_id", None) == ALL_LANGUAGES and
                        hasattr(self.primary, "with_language")):
                    self._engine = self.primary.with_language("auto")
                else:
                    from .selection import create_asr, select_model

                    config = copy.deepcopy(self.config)
                    select_model(config, ALL_LANGUAGES)
                    config["stt"]["language"] = "auto"
                    config["stt"]["local_files_only"] = True
                    self._engine = (self.factory or create_asr)(config)
            engine = self._engine
            prepare = getattr(engine, "prepare", None)
            if prepare is not None:
                prepare()
            text = engine.transcribe(audio)
        self.last_language = getattr(engine, "last_language", None)
        self.last_timings = dict(getattr(engine, "last_timings", {}))
        return text
