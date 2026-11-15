"""CTranslate2 Whisper models, including the multilingual turbo fallback."""

from dataclasses import replace

from saydraft.audio.vad_silero import optional_silero
from saydraft.stt.whisper_engine import WhisperEngine, WhisperEngineConfig

TURBO_MODEL = "large-v3-turbo"


class WhisperCT2Engine(WhisperEngine):
    @property
    def model_id(self):
        return f"whisper-{self.config.model_size}"

    def set_language(self, language):
        self.config = replace(self.config, language=language)

    def with_language(self, language):
        return WhisperCT2Engine(replace(self.config, language=language, local_files_only=True),
            model_factory=lambda *args, **kwargs:
                self._model if self._model is not None else self.model_factory(*args, **kwargs))

    def prepare(self):
        """Initialize native sessions before capture, keeping the entire clip intact."""
        self._load_model()
        if self.config.silence_trim and not self._vad_checked:
            self._silero_vad = optional_silero() if self.config.silero_threshold == 0.5 else optional_silero(threshold=self.config.silero_threshold)
            self._vad_checked = True


__all__ = ["WhisperCT2Engine", "WhisperEngineConfig", "TURBO_MODEL"]
