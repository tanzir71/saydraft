"""One translation owner for a normal dictation session, independent of cleanup."""

from dataclasses import dataclass, replace
import json
import logging
import threading
import time

from saydraft.history import HistoryEntry
from saydraft.insert.inserter import InsertionResult
from saydraft.models.command import installed_command_config, translation_choice
from saydraft.models.hardware import latest_report
from saydraft.translation import translate
from .command_edit import CommandEditResult
from .interfaces import insertion_block
from .processing import ProcessingResult
from .session import SessionState as State

logger = logging.getLogger(__name__)


@dataclass
class _Translation:
    generation: int
    target: str
    services: object
    choice: object
    cancelled: threading.Event
    editor: object = None


class TranslationTask:
    def __init__(self, worker, *, report_loader=latest_report, resolver=installed_command_config, clock=time.perf_counter):
        self.worker, self.report_loader, self.resolver = worker, report_loader, resolver
        self.active = None
        self.clock = clock

    def choice(self, config):
        try:
            tier = config['app'].get('tier', 'auto')
            report = self.report_loader() if (tier == 'auto' or
                tier == 'pro' and config.get('command', {}).get('backend', 'auto') == 'auto') else None
        except Exception:
            report = None
        return translation_choice(config, report)

    def reserve(self, generation, target, choice):
        self.active = _Translation(generation, target, self.worker.services, choice, threading.Event())

    def owns(self, generation):
        return self.active is not None and self.active.generation == generation

    def current(self, task):
        w = self.worker
        return (self.active is task and not task.cancelled.is_set() and not w._cancel_request.is_set()
                and not w._closing and w.services is task.services and w.session.session_id == task.generation
                and (w.session.active or w.session.state in (State.DONE, State.NOT_INSERTED)))

    def prepare(self, generation):
        task, w = self.active, self.worker
        if task is None or task.generation != generation:
            return False
        ready = False
        try:
            config = self.resolver(task.choice, threads=task.services.config['llm'].get('threads') or 4)
            if config is None or not self.current(task) or not w._capture_request_current(generation):
                return False
            config = replace(config, idle_seconds=max(900, task.services.config['recording']['max_seconds'] + 65))
            task.editor = task.services.cleaner.llm.command_session(config, task.choice.model_id)
            if task.editor is None:
                return False
            ready = task.editor.prepare(cancelled=lambda: not self.current(task)
                or not w._capture_request_current(generation)) == 'ready'
            return ready and self.current(task)
        except Exception:
            logger.warning('Translation model preparation unavailable')
            return False
        finally:
            if not ready or not self.current(task):
                self.finish(generation)

    def cancel(self):
        task = self.active
        if task is not None:
            task.cancelled.set()
            if task.editor is not None:
                try:
                    task.editor.close()
                except Exception:
                    logger.warning('Translation owner closure unavailable; native process slot remains authoritative')

    def finish(self, generation):
        task = self.active
        if task is not None and task.generation == generation:
            self.cancel()
            self.active = None

    def process(self, generation, raw, *, target, context, model, language, duration, timings,
                audio_path=None, insert_text=True, source_review=False, source_edits=()):
        task, w = self.active, self.worker
        if task is None or task.generation != generation or not self.current(task):
            return None
        stages = dict(timings)
        started = self.clock()
        try:
            if source_review:
                valid, reason, text = False, 'source_requires_review', raw
            else:
                reply = translate(task.editor, raw, task.target, source_language=language,
                                  cancelled=lambda: not self.current(task))
                valid, reason = reply.reason == 'ok' and reply.text is not None, reply.reason
                text = reply.text if valid else raw
        except Exception:
            valid, reason, text = False, 'unavailable', raw
        stages['translation'] = max(0, self.clock() - started)
        if not self.current(task):
            return None
        notes = (*source_edits, {'type': 'translation', 'target_language': task.target, 'source_language': language,
                  'decision': reason, 'validator': 'translation-v1'},)
        entry = HistoryEntry(target.app_title, raw, text, 'translate' if valid else 'translation_failed',
            context.profile, duration, model, app_exe=target.app_exe, app_group=target.app_group,
            language=language, asr_model=model, llm_model=task.choice.model_id,
            llm_decision='translation_' + reason, audio_path=audio_path,
            timings_json=json.dumps(stages), edits_json=json.dumps(notes))

        def recover(body, kind, why):
            if self.current(task):
                w._recover_command_result(generation, CommandEditResult(body, why, task=kind))

        try:
            with w._lock:
                identifier = task.services.history.append(entry) if self.current(task) else None
        except Exception:
            result = ProcessingResult(raw, text, InsertionResult('not_inserted', 'none', 'history_unavailable'),
                                      timings=stages, audio_path=audio_path, edits=notes)
            task.services.processor.pending_results.append(result)
            recover(raw, 'translation_raw', 'history_unavailable')
            if valid and text != raw:
                recover(text, 'translation', 'history_unavailable')
            return result if self.current(task) else None
        if identifier is None or not self.current(task):
            return None
        started = self.clock()
        inserted = InsertionResult('not_inserted', 'none', 'translation_failed' if not valid else 'history_only')
        if valid and insert_text:
            blocked = insertion_block(target)
            if blocked:
                inserted = InsertionResult('not_inserted', 'none', blocked)
            else:
                try:
                    inserted = w._insert_if_current(generation, lambda: task.services.inserter.insert_text(text,
                        start_focus=target.focus, app_title=target.app_title,
                        enter_guard=lambda: self.current(task), field_guard=w._field_guard(target)))
                except Exception:
                    inserted = InsertionResult('not_inserted', 'none', 'insertion_error')
        if inserted is None or not self.current(task):
            return None
        stages['insert'] = max(0, self.clock() - started)
        try:
            task.services.history.update_timings(identifier, stages)
        except Exception:
            pass
        result = ProcessingResult(raw, text, inserted, identifier, stages, audio_path, notes)
        if inserted.status != 'inserted':
            recover(text, 'translation' if valid else 'translation_raw', inserted.reason)
        return result
