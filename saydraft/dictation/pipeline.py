from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from saydraft.cleanup.code_mode import render_code
from saydraft.cleanup.formatter import caret_layout, final_punctuation, layout_hints
from saydraft.cleanup.styles import rule_options, style_for
from .glossary import Glossary, apply_replacements, learn_word, load_glossary, protect_terms, restore_terms
from .llm_local import LocalLLMConfig, LocalLLMCleaner
from .protect import protect_spans, restore_spans
from .rules import apply_rules
from .types import DictationContext
from .validation import validate_llm_output

@dataclass(frozen=True)
class DictationConfig:
    glossary_path: str = ""
    llm: LocalLLMConfig = LocalLLMConfig()
    drop_message_period: bool = True


_options_for = rule_options  # Compatibility for callers of the former private helper.


class DictationPipeline:
    def __init__(self, cfg: DictationConfig, llm_cleaner: Optional[LocalLLMCleaner] = None):
        self.cfg = cfg
        self.glossary: Glossary = load_glossary(cfg.glossary_path) if cfg.glossary_path else Glossary()
        self.llm = llm_cleaner if llm_cleaner is not None else LocalLLMCleaner(cfg.llm)
        self.last_timings: dict[str, float] = {"rules": 0.0, "llm": 0.0}
        self.last_llm_decision = "disabled"
        self.last_llm_model = None

    def reload_glossary(self):
        self.glossary = load_glossary(self.cfg.glossary_path) if self.cfg.glossary_path else Glossary()

    def warm(self):
        warm = getattr(self.llm, "warm", None)
        return warm() if warm is not None else False

    def warm_for_context(self, context):
        if (context.mode == "raw" or context.profile == "code/comments" or context.app_group == "code"
                or style_for(context).intensity == 1):
            return False
        warm = getattr(self.llm, "warm_for_context", None)
        return warm(context) if warm is not None else self.warm()

    def close(self):
        close = getattr(self.llm, "close", None)
        if close is not None:
            close()

    def benchmark(self):
        measure = getattr(self.llm, "benchmark", None)
        return measure() if measure is not None else []

    def learn_word(self, term: str) -> Glossary:
        if not self.cfg.glossary_path:
            normalized = term.strip()
            if normalized and normalized not in self.glossary.user_terms:
                self.glossary = Glossary(
                    user_terms=(*self.glossary.user_terms, normalized),
                    protected_terms=self.glossary.protected_terms,
                    replacements=self.glossary.replacements,
                )
            return self.glossary

        self.glossary = learn_word(self.cfg.glossary_path, term)
        return self.glossary

    def format_final(self, text: str, context: DictationContext) -> str:
        text = final_punctuation(text, context, drop_message_period=self.cfg.drop_message_period,
                                 glossary=self.glossary)
        return caret_layout(text, context, glossary=self.glossary)

    def process_for_delivery(self, raw_text: str, context: DictationContext) -> str:
        return self.process_transcript(raw_text, context, finalize=False)

    def process_transcript(self, raw_text: str, context: DictationContext, *, finalize: bool = True) -> str:
        self.last_timings = {"rules": 0.0, "llm": 0.0}
        self.last_llm_decision = "disabled"
        self.last_llm_model = None
        if not raw_text:
            return ""

        text = raw_text
        text = apply_replacements(text, self.glossary)
        protected_text, mapping = protect_terms(text, self.glossary)
        protected_text, span_mapping = protect_spans(protected_text, protected_tokens=mapping)

        rules_started = time.perf_counter()
        code = context.mode != "raw" and (context.profile == "code/comments" or context.app_group == "code")
        rule_clean = render_code(protected_text) if code else apply_rules(protected_text, _options_for(context))
        self.last_timings["rules"] = time.perf_counter() - rules_started

        bypass = context.mode == "raw" or code
        if bypass or style_for(context).intensity == 1:
            self.last_llm_decision = "bypassed" if bypass else "skip_verbatim"
            out = restore_spans(rule_clean, span_mapping)
            out = restore_terms(out, mapping)
            return self.format_final(out, layout_hints(context, raw_text, out)) if not bypass and finalize else out

        llm_ok_text: Optional[str] = None
        llm_started = time.perf_counter()
        if self.llm.available():
            self.last_llm_model = getattr(self.llm, "model_id", None) or "Local cleanup"
            after_rules = getattr(self.llm, "clean_after_rules", None)
            contextual = getattr(self.llm, "clean_with_context", None)
            if after_rules is not None:
                candidate, status = after_rules(rule_clean, context=context, raw_text=protected_text,
                    glossary=(*self.glossary.user_terms, *self.glossary.protected_terms))
            elif contextual is not None:
                candidate, status = contextual(rule_clean, context=context,
                    glossary=(*self.glossary.user_terms, *self.glossary.protected_terms))
            else:
                candidate, status = self.llm.clean(rule_clean, tone_hint=style_for(context).tone)
            self.last_llm_decision = status
            if candidate:
                validation = validate_llm_output(rule_clean, candidate, mode=context.mode,
                    glossary=(*self.glossary.user_terms, *self.glossary.protected_terms), intensity=style_for(context).intensity)
                if validation.ok:
                    llm_ok_text = candidate
                    self.last_llm_decision = "accepted"
                else:
                    self.last_llm_decision = f"rejected:{validation.reason}"
        self.last_timings["llm"] = time.perf_counter() - llm_started

        final_text = llm_ok_text if llm_ok_text is not None else rule_clean
        final_text = restore_spans(final_text, span_mapping)
        final_text = restore_terms(final_text, mapping)
        return self.format_final(final_text, layout_hints(context, raw_text, final_text)) if finalize else final_text


_DEFAULT_PIPELINE: Optional[DictationPipeline] = None


def process_transcript(raw_text: str, context: DictationContext, cfg: Optional[DictationConfig] = None) -> str:
    global _DEFAULT_PIPELINE
    if cfg is not None or _DEFAULT_PIPELINE is None:
        if _DEFAULT_PIPELINE is not None:
            _DEFAULT_PIPELINE.close()
        _DEFAULT_PIPELINE = DictationPipeline(cfg or DictationConfig())
    return _DEFAULT_PIPELINE.process_transcript(raw_text, context)

