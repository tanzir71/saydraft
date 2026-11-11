"""Clean, format, persist, then insert. Each boundary is injected."""

from __future__ import annotations

import logging
import time
import json
import copy
from dataclasses import dataclass, field

from saydraft.history import HistoryEntry
from saydraft.insert.inserter import InsertionResult
from .interfaces import Cleaner, Formatter, HistoryStore, Inserter, TargetContext
from .preferences import expand_snippets
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
                 notify=lambda message: None, clock=time.perf_counter, reporter=None):
        self.cleaner = cleaner
        self.formatter = formatter
        self.history = history
        self.inserter = inserter
        self.snippets = snippets or {}
        self.notify = notify
        self.clock = clock
        self.last_result: ProcessingResult | None = None
        self.pending_results: list[ProcessingResult] = []
        self.reporter = reporter or TimingReporter(notify=notify)

    def process(self, raw_text: str, *, target: TargetContext, context, model: str,
                duration_seconds: float | None = None, insert_text: bool = True,
                insert_action=None, timings: dict | None = None, language: str = "auto",
                audio_path: str | None = None, edits: list | None = None) -> ProcessingResult:
        stages = dict(timings or {})
        notes = tuple(copy.deepcopy(edits or ()))
        cleaned = raw_text
        try:
            cleaned = self.cleaner.process_transcript(raw_text, context) or raw_text
            stages.update(getattr(self.cleaner, "last_timings", {}))
        except Exception:
            logger.warning("Cleanup failed; preserving raw words")
            logger.debug("Cleanup failure detail", exc_info=True)
        try:
            cleaned = expand_snippets(cleaned, self.snippets)
            cleaned = self.formatter.format(cleaned, target) or cleaned
        except Exception:
            logger.warning("Formatting failed; preserving available words")
            logger.debug("Formatting failure detail", exc_info=True)
        entry = HistoryEntry(target.app_title, raw_text, cleaned, context.mode,
                             context.profile, duration_seconds, model,
                             app_exe=target.app_exe, app_group=target.app_group,
                             intensity={"raw": 0, "balanced": 1, "aggressive": 3}.get(context.mode),
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
                return self.inserter.insert_text(cleaned, start_focus=target.focus, app_title=target.app_title)
            try:
                insertion = insert_action(action) if insert_action is not None else action()
            except Exception:
                logger.error("Insertion failed; dictation remains in history")
                logger.debug("Insertion failure detail", exc_info=True)
                insertion = InsertionResult("not_inserted", "none", "insertion_error")
        stages["insert"] = self.clock() - started
        if insertion.status == "skipped_focus_changed":
            self.notify("Copied to history; focus changed before insertion.")
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
