"""Frozen, reviewed text -> local answer -> History -> independent Scratchpad.

Selection admission and lease retirement happen before the question UI takes
focus. This boundary has no document, clipboard, recording or insertion port.
"""

from dataclasses import dataclass, replace
import hashlib
import json
import logging
import time

from saydraft.cleanup.llm.ask import AskReply, build_ask_messages, validate_answer
from saydraft.history import HistoryEntry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AskSource:
    text: str
    app_title: str | None = None
    app_exe: str = ''
    app_group: str = ''


@dataclass(frozen=True)
class AskCapture:
    source: AskSource | None
    reason: str


def capture_ask_source(context, *, current):
    """Action-thread only: verify readable UIA text, then revoke its lease.

    The returned snapshot contains plain values, never native proxies. The
    caller reserves this capture and rechecks its ticket before showing the UI.
    Clipboard fallback is explicitly disabled even when Command enables it.
    """
    from saydraft.context.foreground import SelectedContext
    if not current():
        return AskCapture(None, 'cancelled')
    captured, result = None, AskCapture(None, 'selection_unavailable')
    try:
        captured = context.capture_selection(lease_seconds=10, allow_copy=False)
        if not current():
            result = AskCapture(None, 'cancelled')
        elif type(captured) is not SelectedContext:
            pass
        elif captured.selection.status != 'ready':
            result = AskCapture(None, captured.selection.status)
        elif captured.selection.origin != 'uia':
            result = AskCapture(None, 'unsupported')
        elif reason := context.verify_selection(captured, for_write=False):
            result = AskCapture(None, reason)
        elif current():
            build_ask_messages(captured.selection.text, 'Review the selected text.')
            target = captured.target
            result = AskCapture(AskSource(captured.selection.text, target.app_title,
                                         target.app_exe, target.app_group), 'ready')
    except Exception:
        logger.warning('Ask selection could not be reviewed safely')
    finally:
        if captured is not None:
            try:
                revoked = context.cancel_selection(captured) is True
            except Exception:
                revoked = False
            if not revoked and result.source is not None:
                result = AskCapture(None, 'selection_unavailable')
    return result if current() else AskCapture(None, 'cancelled')


@dataclass(frozen=True)
class AskResult:
    text: str | None
    reason: str
    history_id: int | None = None
    action: str = 'question'


class AskProcessor:
    def __init__(self, *, editor, history, present, clock=time.perf_counter):
        self.editor, self.history, self.present, self.clock = editor, history, present, clock

    def process(self, source, question, *, action='question', current, run_current, persist_current):
        """The caller fences admission/persistence and every queued UI callback.

        Store the question and complete answer; retain only hash/length
        provenance for the reviewed selection. Failed or partial generation
        leaves the question UI available for retry. Cancellation drops late
        presentation; an already committed History answer stays recoverable.
        """
        if not current():
            return AskResult(None, 'cancelled')
        if type(source) is not AskSource:
            return AskResult(None, 'invalid_request')
        try:
            build_ask_messages(source.text, question, action)
        except ValueError:
            return AskResult(None, 'invalid_request')
        started = self.clock()
        try:
            reply = self.editor.ask_about(source.text, question, action=action, cancelled=lambda: not current())
        except Exception:
            logger.warning('Local selected-text question unavailable')
            return AskResult(None, 'unavailable' if current() else 'cancelled', action=action)
        seconds = max(0, self.clock() - started)
        if not current():
            return AskResult(None, 'cancelled', action=action)
        if type(reply) is not AskReply:
            return AskResult(None, 'invalid_reply', action=action)
        if reply.reason != 'ok':
            return AskResult(None, reply.reason, action=action)
        if not reply.stream_complete:
            return AskResult(None, 'incomplete', action=action)
        checked = validate_answer(source.text, question, reply.text)
        if not checked.ok:
            return AskResult(None, checked.reason, action=action)
        entry = HistoryEntry(source.app_title, question, reply.text, 'ask', 'ask', None, '',
            app_exe=source.app_exe, app_group=source.app_group, language='und',
            llm_model=self.editor.model_id, llm_decision='ask_answered',
            timings_json=json.dumps({'llm': seconds}), edits_json=json.dumps([{
                'type': 'ask', 'action': action, 'validator': 'ask-v1',
                'source_sha256': hashlib.sha256(source.text.encode('utf-8')).hexdigest(),
                'source_utf16_units': len(source.text.encode('utf-16-le')) // 2,
                'input_tokens': reply.input_tokens, 'output_limit': reply.output_limit,
            }]))
        try:
            identifier = persist_current(lambda: self.history.append(entry))
        except Exception:
            identifier = None
            result = AskResult(reply.text, 'history_unavailable', action=action)
        else:
            if identifier is None or not current():
                return AskResult(None, 'cancelled', action=action)
            result = AskResult(reply.text, 'ok', identifier, action)
        if not current():
            return AskResult(None, 'cancelled', identifier, action)
        try:
            run_current(lambda: self.present(result))
        except Exception:
            logger.warning('Local answer window unavailable')
            result = replace(result, reason='display_unavailable')
        return result if current() else AskResult(None, 'cancelled', identifier, action)
