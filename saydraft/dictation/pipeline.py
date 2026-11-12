from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from saydraft.cleanup.code_mode import render_code
from saydraft.cleanup.formatter import final_punctuation
from .glossary import Glossary, apply_replacements, learn_word, load_glossary, protect_terms, restore_terms
from .llm_local import LocalLLMConfig, LocalLLMCleaner
from .protect import protect_spans, restore_spans
from .rules import RuleOptions, apply_rules
from .types import DictationContext
from .validation import validate_llm_output

PROFILE_TONE_HINTS = {
    "email": "formal",
    "chat": "casual",
    "notes": "terse",
}


@dataclass(frozen=True)
class DictationConfig:
    glossary_path: str = ""
    llm: LocalLLMConfig = LocalLLMConfig()
    drop_message_period: bool = True


def _options_for(context: DictationContext) -> RuleOptions:
    if context.mode == "raw":
        return RuleOptions(
            remove_fillers=False,
            remove_repetitions=False,
            handle_self_corrections=False,
            normalize_punctuation=False,
            normalize_capitalization=False,
            normalize_whitespace=True,
            enable_list_formatting=False,
            convert_spoken_punctuation=False,
            convert_spoken_newlines=False,
            final_period=False,
        )

    enable_list = context.profile in ("notes", "email")
    newlines = context.profile in ("notes", "email")

    if context.mode == "aggressive":
        return RuleOptions(
            remove_fillers=True,
            aggressive_fillers=True,
            remove_repetitions=True,
            handle_self_corrections=True,
            normalize_punctuation=True,
            normalize_capitalization=True,
            normalize_whitespace=True,
            enable_list_formatting=enable_list,
            convert_spoken_punctuation=True,
            convert_spoken_newlines=newlines,
            final_period=False,
            normalize_itn=True, intensity=context.intensity if context.intensity is not None else 4,
            number_style="compact" if context.profile == "notes" else "prose",
        )

    return RuleOptions(
        remove_fillers=True,
        aggressive_fillers=False,
        remove_repetitions=True,
        handle_self_corrections=False,
        normalize_punctuation=True,
        normalize_capitalization=True,
        normalize_whitespace=True,
        enable_list_formatting=enable_list,
        convert_spoken_punctuation=False,
        convert_spoken_newlines=newlines,
        final_period=False,
        normalize_itn=True, intensity=context.intensity if context.intensity is not None else 3,
        number_style="compact" if context.profile == "notes" else "prose",
    )


def _tone_hint_for(context: DictationContext) -> str:
    return PROFILE_TONE_HINTS.get(context.profile, "neutral")


class DictationPipeline:
    def __init__(self, cfg: DictationConfig, llm_cleaner: Optional[LocalLLMCleaner] = None):
        self.cfg = cfg
        self.glossary: Glossary = load_glossary(cfg.glossary_path) if cfg.glossary_path else Glossary()
        self.llm = llm_cleaner if llm_cleaner is not None else LocalLLMCleaner(cfg.llm)
        self.last_timings: dict[str, float] = {"rules": 0.0, "llm": 0.0}
        self.last_llm_decision = "disabled"

    def reload_glossary(self):
        self.glossary = load_glossary(self.cfg.glossary_path) if self.cfg.glossary_path else Glossary()

    def warm(self):
        warm = getattr(self.llm, "warm", None)
        return warm() if warm is not None else False

    def close(self):
        close = getattr(self.llm, "close", None)
        if close is not None:
            close()

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
        return final_punctuation(text, context, drop_message_period=self.cfg.drop_message_period,
                                 glossary=self.glossary)

    def process_for_delivery(self, raw_text: str, context: DictationContext) -> str:
        return self.process_transcript(raw_text, context, finalize=False)

    def process_transcript(self, raw_text: str, context: DictationContext, *, finalize: bool = True) -> str:
        self.last_timings = {"rules": 0.0, "llm": 0.0}
        self.last_llm_decision = "disabled"
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

        if context.mode == "raw" or context.profile == "code/comments" or context.app_group == "code":
            self.last_llm_decision = "bypassed"
            out = restore_spans(rule_clean, span_mapping)
            return restore_terms(out, mapping)

        llm_ok_text: Optional[str] = None
        llm_started = time.perf_counter()
        if self.llm.available():
            contextual = getattr(self.llm, "clean_with_context", None)
            if contextual is not None:
                candidate, status = contextual(rule_clean, context=context,
                    glossary=(*self.glossary.user_terms, *self.glossary.protected_terms))
            else:
                candidate, status = self.llm.clean(rule_clean, tone_hint=_tone_hint_for(context))
            self.last_llm_decision = status
            if candidate:
                validation = validate_llm_output(rule_clean, candidate, mode=context.mode,
                    glossary=(*self.glossary.user_terms, *self.glossary.protected_terms), intensity=context.intensity)
                if validation.ok:
                    llm_ok_text = candidate
                    self.last_llm_decision = "accepted"
                else:
                    self.last_llm_decision = f"rejected:{validation.reason}"
        self.last_timings["llm"] = time.perf_counter() - llm_started

        final_text = llm_ok_text if llm_ok_text is not None else rule_clean
        final_text = restore_spans(final_text, span_mapping)
        final_text = restore_terms(final_text, mapping)
        return self.format_final(final_text, context) if finalize else final_text


_DEFAULT_PIPELINE: Optional[DictationPipeline] = None


def process_transcript(raw_text: str, context: DictationContext, cfg: Optional[DictationConfig] = None) -> str:
    global _DEFAULT_PIPELINE
    if cfg is not None or _DEFAULT_PIPELINE is None:
        if _DEFAULT_PIPELINE is not None:
            _DEFAULT_PIPELINE.close()
        _DEFAULT_PIPELINE = DictationPipeline(cfg or DictationConfig())
    return _DEFAULT_PIPELINE.process_transcript(raw_text, context)

