"""Generate, persist, then replace an explicitly captured selected-text lease.

The caller owns Labs/Pro admission, recording and a current-session executor.
This boundary never sends the spoken instruction through dictation cleanup.
"""

import json
import logging
import time
from dataclasses import dataclass, replace

from saydraft.cleanup.llm.edit import validate_edit_output
from saydraft.history import HistoryEntry
from saydraft.insert.inserter import InsertionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandEditResult:
    text: str | None
    reason: str
    history_id: int | None = None
    insertion: InsertionResult | None = None
    confirmation_reason: str = ""


@dataclass(frozen=True)
class CommandRecoveryRequest:
    generation: int
    ticket: object
    result: CommandEditResult


class CommandEditProcessor:
    def __init__(self, *, editor, selections, history, inserter, recover, clock=time.perf_counter):
        self.editor, self.selections, self.history = editor, selections, history
        self.inserter, self.recover, self.clock = inserter, recover, clock

    def process(self, captured, instruction, *, run_current, current, asr_model="", language="auto",
                persist_current=None, duration_seconds=None, audio_path=None, timings=None):
        """Admission is rechecked at each boundary and by the delivery guards.

        `persist_current` admits a durable write under the caller's session mutex.
        `run_current` must not hold a GUI/session mutex across clipboard or UIA I/O.
        Both return None without starting the action when the session is retired.
        Recovery gets a standalone result; it must never replace a live NoteDraft.
        Every exit releases this lease only, including editor/history failures.
        """
        persist_current = persist_current or run_current
        stages = dict(timings or {})

        def failed(reason):
            if not current():
                return CommandEditResult(None, 'cancelled')
            if type(instruction) is not str or not instruction.strip():
                return CommandEditResult(None, reason)
            # A failed edit retains the recognized instruction, not an
            # unvalidated replacement or newly read document/password contents.
            entry = HistoryEntry(captured.target.app_title, instruction, '', 'command', 'command',
                duration_seconds, asr_model, app_exe=captured.target.app_exe,
                app_group=captured.target.app_group, language=language, asr_model=asr_model,
                llm_model=self.editor.model_id, llm_decision='edit_failed:' + reason,
                timings_json=json.dumps(stages), audio_path=audio_path,
                edits_json=json.dumps([{'type': 'command_instruction', 'reason': reason}], ensure_ascii=False))
            try:
                identifier = persist_current(lambda: self.history.append(entry))
            except Exception:
                if current():
                    run_current(lambda: self.recover(CommandEditResult(instruction, 'instruction_history_unavailable')))
                return CommandEditResult(None, reason if current() else 'cancelled')
            return CommandEditResult(None, reason, identifier) if identifier is not None and current() else CommandEditResult(None, 'cancelled')

        def guard(*, for_write=True):
            if not current():
                return "cancelled"
            try:
                reason = self.selections.verify_selection(captured, for_write=for_write)
            except Exception:
                reason = "field_unavailable"
            return reason if current() else "cancelled"

        try:
            if not current():
                return CommandEditResult(None, "cancelled")
            if captured.selection.status != "ready":
                return failed(captured.selection.status)
            # Read-only text can still produce a rewrite for Copy. Changed or
            # sensitive selections must not be sent to the model.
            if reason := guard(for_write=False):
                return failed(reason)
            started = self.clock()
            try:
                reply = self.editor.edit_selection(captured.selection.text, instruction, cancelled=lambda: not current())
            except Exception:
                return failed("unavailable")
            seconds = self.clock() - started
            stages['llm'] = seconds
            if not current():
                return CommandEditResult(None, "cancelled")
            if reply.reason != "ok" or reply.text is None:
                return failed(reply.reason)
            checked = validate_edit_output(captured.selection.text, instruction, reply.text)
            if not checked.ok:
                return failed(checked.reason)
            target = captured.target
            entry = HistoryEntry(target.app_title, captured.selection.text, reply.text, "command", "command",
                duration_seconds, asr_model, app_exe=target.app_exe, app_group=target.app_group, language=language,
                asr_model=asr_model, llm_model=self.editor.model_id, llm_decision="edit_validated",
                timings_json=json.dumps(stages), audio_path=audio_path, edits_json=json.dumps([{
                    "type": "command_edit", "instruction": instruction, "validator": "edit-v1",
                    "selection_source": getattr(captured.selection, 'origin', 'uia'),
                    "input_tokens": reply.input_tokens, "output_limit": reply.output_limit}], ensure_ascii=False))
            try:
                identifier = persist_current(lambda: self.history.append(entry))
            except Exception:
                result = CommandEditResult(reply.text, "history_unavailable")
                if current():
                    run_current(lambda: self.recover(result))
                return result if current() else CommandEditResult(None, "cancelled")
            if identifier is None or not current():
                return CommandEditResult(None, "cancelled")
            started = self.clock()
            try:
                if getattr(captured.selection, 'origin', 'uia') == 'clipboard':
                    # Complete copied text lacks anchored endpoints. Keep the
                    # validated edit and offer Copy without a blind paste.
                    inserted = InsertionResult('not_inserted', 'none', 'copy_only')
                else:
                    inserted = run_current(lambda: self.inserter.insert_text(reply.text,
                        start_focus=target.focus, app_title=target.app_title, paste_only=True,
                        enter_guard=current, field_guard=guard))
            except Exception:
                inserted = InsertionResult("not_inserted", "none", "insertion_error")
            if not current() or inserted is None:
                return CommandEditResult(None, "cancelled", identifier)
            confirmation = ""
            if inserted.status == "inserted":
                try:
                    confirmation = run_current(lambda: self.selections.confirm_replacement(captured, reply.text))
                except Exception:
                    confirmation = "field_unavailable"
                if confirmation is None or not current():
                    return CommandEditResult(None, "cancelled", identifier)
                if confirmation:
                    # The key may already have written text. Recovery must ask
                    # the user to check the target before copying/pasting again.
                    inserted = replace(inserted, status="not_inserted", reason="insertion_unconfirmed")
            stages["insert"] = self.clock() - started
            result = CommandEditResult(reply.text, "ok" if inserted.status == "inserted" else inserted.reason,
                                       identifier, inserted, confirmation)
            try:
                self.history.update_timings(identifier, stages)
            except Exception:
                pass  # Earlier complete text/provenance remains the delivery prerequisite.
            if inserted.status != "inserted" and current():
                run_current(lambda: self.recover(result))
            return result
        finally:
            try:
                self.selections.cancel_selection(captured)
            except Exception:
                logger.warning('Command selection retirement unavailable')
