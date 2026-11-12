"""Clean, format, persist, then insert. Each boundary is injected."""

from __future__ import annotations

import logging
import time
import json
import copy
from dataclasses import dataclass, field, replace

from saydraft.history import HistoryEntry
from saydraft.cleanup.delivery import DeliveryIntent, trailing_enter
from saydraft.insert.inserter import InsertionResult
from .interfaces import Cleaner, Formatter, HistoryStore, Inserter, TargetContext
from .preferences import protect_snippets, restore_snippets
from .timings import TimingReporter

logger = logging.getLogger(__name__)


class IdentityFormatter:
    def format(self, text: str, target: TargetContext) -> str:
        return text


@dataclass(frozen=True)
class ProcessingResult:
    raw_text: str
    cleaned_text: str
    insertion: InsertionResult
    history_id: int | None = None
    timings: dict[str, float] = field(default_factory=dict)
    audio_path: str | None = None
    edits: tuple[dict, ...] = ()


class TranscriptProcessor:
    def __init__(self, *, cleaner: Cleaner, formatter: Formatter, history: HistoryStore,
                 inserter: Inserter, snippets: dict[str, str] | None = None,
                 notify=lambda message: None, clock=time.perf_counter, reporter=None,
                 voice_enter_enabled: bool = False):
        self.cleaner = cleaner
        self.formatter = formatter
        self.history = history
        self.inserter = inserter
        self.snippets = snippets or {}
        self.voice_enter_enabled = voice_enter_enabled
        self.notify = notify
        self.clock = clock
        self.last_result: ProcessingResult | None = None
        self.pending_results: list[ProcessingResult] = []
        self.reporter = reporter or TimingReporter(notify=notify)

    def process(self, raw_text: str, *, target: TargetContext, context, model: str,
                duration_seconds: float | None = None, insert_text: bool = True,
                insert_action=None, timings: dict | None = None, language: str = "auto",
                audio_path: str | None = None, edits: list | None = None, enter_guard=None) -> ProcessingResult:
        stages = dict(timings or {})
        notes = tuple(copy.deepcopy(edits or ()))
        cleaned = raw_text
        delivery = DeliveryIntent(raw_text)
        snippet_mapping = {}
        try:
            context = replace(context, app_title=target.app_title, app_group=target.app_group,
                              language=language, before_caret=target.before_caret)
            delivery = trailing_enter(raw_text, context, enabled=self.voice_enter_enabled and insert_text)
            if delivery.send_enter:
                notes += ({"type": "voice_enter", "requested": True},)
            cleaned, snippet_mapping = protect_snippets(delivery.text, self.snippets)
            clean = getattr(self.cleaner, "process_for_delivery", self.cleaner.process_transcript)
            cleaned = clean(cleaned, context) or cleaned
            stages.update(getattr(self.cleaner, "last_timings", {}))
        except Exception:
            logger.warning("Cleanup failed; preserving raw words")
            logger.debug("Cleanup failure detail", exc_info=True)
        try:
            cleaned = restore_snippets(cleaned, snippet_mapping)
            cleaned = self.formatter.format(cleaned, target) or cleaned
            format_final = getattr(self.cleaner, "format_final", None)
            if format_final is not None:
                cleaned = format_final(cleaned, context) or cleaned
        except Exception:
            logger.warning("Formatting failed; preserving available words")
            logger.debug("Formatting failure detail", exc_info=True)
        entry = HistoryEntry(target.app_title, raw_text, cleaned, context.mode,
                             context.profile, duration_seconds, model,
                             app_exe=target.app_exe, app_group=target.app_group,
                             intensity=context.intensity if context.intensity is not None else
                             {"raw": 0, "balanced": 3, "aggressive": 4}.get(context.mode),
                             llm_decision=getattr(self.cleaner, "last_llm_decision", None),
                             language=language, asr_model=model, timings_json=json.dumps(stages),
                             audio_path=audio_path, edits_json=json.dumps(notes))
        try:
            history_id = self.history.append(entry)
        except Exception:
            logger.error("Could not save dictation history; insertion refused")
            logger.debug("History failure detail", exc_info=True)
            result = ProcessingResult(raw_text, cleaned, InsertionResult(
                "not_inserted", "none", "history_unavailable"), timings=stages, audio_path=audio_path, edits=notes)
            self.last_result = result  # Keep both versions available for recovery.
            self.pending_results.append(result)
            self.notify("Could not save history. Your dictation is kept in this session; retry saving it.")
            return result
        insertion = InsertionResult("not_inserted", "none", "history_only")
        started = self.clock()
        if target.focus is None and insert_text:
            insertion = InsertionResult("not_inserted", "none", "unknown_target")
        elif target.is_password:
            insertion = InsertionResult("not_inserted", "none", "password_field")
        elif cleaned and insert_text:
            def action():
                options = {"start_focus": target.focus, "app_title": target.app_title}
                if delivery.send_enter:
                    options.update(send_enter=True, enter_guard=enter_guard)
                return self.inserter.insert_text(cleaned, **options)
            try:
                insertion = insert_action(action) if insert_action is not None else action()
            except Exception:
                logger.error("Insertion failed; dictation remains in history")
                logger.debug("Insertion failure detail", exc_info=True)
                insertion = InsertionResult("not_inserted", "none", "insertion_error")
        stages["insert"] = self.clock() - started
        if insertion.status == "skipped_focus_changed":
            self.notify("Copied to history; focus changed before insertion.")
        elif insertion.reason == "target_elevated":
            self.notify("Dictation saved in History. The target is an admin window; automatic insertion is blocked.")
        elif insertion.reason == "modifier_held":
            self.notify("Dictation saved in History. Release Ctrl, Win, Alt and Shift, then retry insertion.")
        elif insertion.reason == "integrity_unavailable":
            self.notify("Dictation saved in History. The target's access level could not be checked.")
        elif delivery.send_enter and insertion.status == "inserted" and not insertion.enter_sent:
            self.notify("Text inserted; Enter was skipped because focus changed." if insertion.reason == "enter_focus_changed"
                        else "Text inserted; Enter was cancelled." if insertion.reason == "enter_cancelled"
                        else "Text inserted; Enter delivery could not be confirmed." if insertion.reason == "enter_failed"
                        else "Text inserted; Enter could not be sent.")
        elif insertion.reason not in ("history_only", "cancelled") and insertion.status != "inserted":
            self.notify("Dictation saved in history; insertion was unavailable.")
        result = ProcessingResult(raw_text, cleaned, insertion, history_id, stages, audio_path, notes)
        self.last_result = result
        update_timings = getattr(self.history, "update_timings", None)
        if update_timings is not None:
            try:
                update_timings(history_id, stages)
            except Exception:
                logger.warning("Could not complete timing metadata; dictation text remains saved")
                logger.debug("Timing metadata failure detail", exc_info=True)
        self.reporter.report(stages, model)
        return result
