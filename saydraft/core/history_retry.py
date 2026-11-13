"""Request-local cleanup choices for retained-audio History review."""

import copy
from dataclasses import replace
from types import SimpleNamespace

from saydraft.cleanup.styles import style_for
from saydraft.dictation.pipeline import DictationPipeline
from saydraft.dictation.llm_local import LocalLLMCleaner
from .processing import ProcessingCancelled


class RetryCleanup:
    def __init__(self, *, factory=LocalLLMCleaner):
        self.factory, self._owned = factory, None

    def processor(self, original, context, choice, *, cancelled):
        if cancelled():
            raise ProcessingCancelled()
        if choice == "current":
            return original
        base = original.cleaner
        if not isinstance(base, DictationPipeline):
            raise ValueError("The configured cleaner does not support retry options")
        llm = SimpleNamespace(available=lambda: False)
        if choice == "on":
            llm = base.llm
            if not base.cfg.llm.enabled:
                if self._owned is None:
                    self._owned = self.factory(replace(base.cfg.llm, enabled=True))
                llm = self._owned
            if cancelled():
                self.close()
                raise ProcessingCancelled()
            prepare = getattr(llm, "prepare_for_review", None)
            if (prepare is not None and context.mode != "raw" and context.profile != "code/comments"
                    and context.app_group != "code" and style_for(context).intensity != 1):
                prepare(context, cancelled=cancelled)
            if cancelled():
                self.close()
                raise ProcessingCancelled()
        # Share read-only glossary data and all delivery/persistence ports, while
        # keeping per-result timings/decisions separate from live dictation.
        view = DictationPipeline(replace(base.cfg, glossary_path=""), llm_cleaner=llm)
        view.glossary = base.glossary
        processor = copy.copy(original)
        processor.cleaner = view
        return processor

    def close(self):
        owned, self._owned = self._owned, None
        if owned is not None:
            owned.close()
