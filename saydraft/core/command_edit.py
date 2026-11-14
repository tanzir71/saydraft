"""Generate, persist, then replace an explicitly captured selected-text lease.

The caller owns Labs/Pro admission, recording and a current-session executor.
This boundary never sends the spoken instruction through dictation cleanup.
"""

import json
import time
from dataclasses import dataclass, replace

from saydraft.cleanup.llm.edit import validate_edit_output
from saydraft.history import HistoryEntry
from saydraft.insert.inserter import InsertionResult


@dataclass(frozen=True)
class CommandEditResult:
    text: str | None
    reason: str
    history_id: int | None = None
    insertion: InsertionResult | None = None
    confirmation_reason: str = ""


class CommandEditProcessor:
    def __init__(self, *, editor, selections, history, inserter, recover, clock=time.perf_counter):
        self.editor, self.selections, self.history = editor, selections, history
        self.inserter, self.recover, self.clock = inserter, recover, clock

    def process(self, captured, instruction, *, run_current, current, asr_model="", language="auto"):
        """`run_current(action)` executes atomically with session cancellation.

        It returns None without running the action when the session is retired.
        Recovery gets a standalone result; it must never replace a live NoteDraft.
        Every exit releases this lease only, including editor/history failures.
        """
        def guard():
            if not current():
                return "cancelled"
            try:
                reason = self.selections.verify_selection(captured, for_write=True)
            except Exception:
                reason = "field_unavailable"
            return reason if current() else "cancelled"

        try:
            if not current():
                return CommandEditResult(None, "cancelled")
            if captured.selection.status != "ready":
                return CommandEditResult(None, captured.selection.status)
            # Read-only/changed/sensitive selections need no model work.
            if reason := guard():
                return CommandEditResult(None, reason)
            started = self.clock()
            try:
                reply = self.editor.edit_selection(captured.selection.text, instruction, cancelled=lambda: not current())
            except Exception:
                return CommandEditResult(None, "unavailable" if current() else "cancelled")
            seconds = self.clock() - started
            if not current():
                return CommandEditResult(None, "cancelled")
            if reply.reason != "ok" or reply.text is None:
                return CommandEditResult(None, reply.reason)
            checked = validate_edit_output(captured.selection.text, instruction, reply.text)
            if not checked.ok:
                return CommandEditResult(None, checked.reason)
            stages = {"llm": seconds}
            target = captured.target
            entry = HistoryEntry(target.app_title, captured.selection.text, reply.text, "command", "command",
                None, asr_model, app_exe=target.app_exe, app_group=target.app_group, language=language,
                asr_model=asr_model, llm_model=self.editor.model_id, llm_decision="edit_validated",
                timings_json=json.dumps(stages), edits_json=json.dumps([{
                    "type": "command_edit", "instruction": instruction, "validator": "edit-v1",
                    "input_tokens": reply.input_tokens, "output_limit": reply.output_limit}], ensure_ascii=False))
            try:
                identifier = run_current(lambda: self.history.append(entry))
            except Exception:
                result = CommandEditResult(reply.text, "history_unavailable")
                if current():
                    run_current(lambda: self.recover(result))
                return result if current() else CommandEditResult(None, "cancelled")
            if identifier is None or not current():
                return CommandEditResult(None, "cancelled")
            started = self.clock()
            try:
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
            self.selections.cancel_selection(captured)
