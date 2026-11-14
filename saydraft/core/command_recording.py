"""Held instruction capture, distinct from ordinary dictation and its cleanup.

The native action thread reserves/captures the original selected target. One
serial worker retires any cancelled PTT prefix before acknowledging and arming
the new Command session. Pending release never stops an unrelated recording.
"""

from dataclasses import dataclass, field, replace
import json
import logging
import threading
from types import SimpleNamespace

from saydraft.history import HistoryEntry
from saydraft.models.command import command_choice, installed_command_config
from saydraft.models.hardware import latest_report
from saydraft.context.foreground import SelectedContext
from .bar_status import BarPhase
from .command_copy import capture_command_copy
from .command_edit import CommandEditProcessor, CommandEditResult
from .session import SessionInput as Input, SessionState as State

logger = logging.getLogger(__name__)


@dataclass(eq=False)
class _Intent:
    services: object
    choice: object
    held: object
    accepted: object
    bar_generation: int
    cancelled: threading.Event = field(default_factory=threading.Event)
    captured: object = None
    generation: int = 0
    editor: object = None


class CommandRecording:
    def __init__(self, worker, *, report_loader=latest_report, config_resolver=installed_command_config):
        self.worker, self.report_loader, self.config_resolver = worker, report_loader, config_resolver
        self.pending = self.active = None

    @property
    def busy(self):
        return self.pending is not None or self.active is not None

    def owns(self, generation):
        return self.active is not None and self.active.generation == generation

    def _current(self, intent, *, held=False):
        w = self.worker
        valid = not w._closing and not intent.cancelled.is_set() and intent.services is w.services
        if self.active is intent:
            valid = (valid and intent.generation == w.session.session_id and not w._cancel_request.is_set()
                     and w.session.active and (w._pending_config is None or w.session.state != State.ARMING))
        else:
            valid = valid and self.pending is intent and w._pending_config is None
            held = True
        return valid and (not held or w._request_current(intent.held))

    def _admissible(self, prefix):
        w = self.worker
        if not w.busy:
            return True
        # Only the serial finalizer/arm belonging to this cancelled normal
        # prefix may precede a pending Command. Shared recording fields are not
        # reassigned until that job has returned on the same executor.
        return (type(prefix) is int and prefix > 0 and prefix == w.session.session_id
            and w.session.state == State.CANCELLED and w._inflight <= 1
            and not self.busy and not w._capturing_context and not w._retrying_history
            and not w._benchmarking and not w._model_storage_busy and not w.microphone_test.active
            and not w.shortcut_capture.active and not w.practice.active)

    def start(self, held, accepted, *, prefix_session_id=None):
        w = self.worker
        if not w._lock.acquire(blocking=False):
            return False
        try:
            if (w._closing or w._pending_config is not None or not w._request_current(held)
                    or not self._admissible(prefix_session_id)):
                return False
            config = w.services.config
            try:
                tier = config.get('app', {}).get('tier', 'auto')
                report = (self.report_loader() if config.get('labs', {}).get('command_mode') is True
                          and (tier == 'auto' or tier == 'pro' and
                               config.get('command', {}).get('backend', 'auto') == 'auto') else None)
            except Exception:
                report = None
            choice = command_choice(config, report)
            if choice.reason != 'ready':
                w.emit('notification_requested', 'Needs Pro tier: Command Mode uses a larger local editing model. '
                    'Check performance or choose Pro in Settings → Models.' if choice.reason == 'needs_pro' else
                    'Enable experimental Command Mode in Settings → Labs first.')
                return False
            intent = _Intent(w.services, choice, held, accepted, w.bar_status.begin())
            self.pending = intent
            ask = getattr(w, 'ask', None)
            if ask is not None:
                ask.invalidate_answer()
            w._command_recovery_ticket = object()
        finally:
            w._lock.release()
        queued = False
        try:
            w.corrections.cancel()
            if not self._current(intent, held=True):
                return False
            intent.captured = intent.services.context.capture_selection(
                lease_seconds=min(3660, config['recording']['max_seconds'] + 125),
                **({'allow_copy': True} if config.get('command', {}).get('clipboard_fallback') is True else {}))
            if not self._current(intent, held=True):
                return False
            pending_copy = (intent.captured.selection.status == 'copy_pending'
                and intent.captured.selection.origin == 'clipboard'
                and config.get('command', {}).get('clipboard_fallback') is True)
            if intent.captured.selection.status != 'ready' and not pending_copy:
                w.emit('notification_requested', 'This app does not expose its selection. You can enable clipboard-copy '
                    'fallback in Settings → Labs.' if intent.captured.selection.status == 'unsupported' else
                    'Select text before holding Command Mode. The selected field could not be read safely.')
                return False
            if intent.services.context.verify_selection(intent.captured, for_write=False):
                w.emit('notification_requested', 'Command Mode cannot safely read this selection. '
                       'Use a non-password field and select the text again.')
                return False
            with w._lock:
                if not self._current(intent, held=True):
                    return False
                w._submit(self._begin, intent)
                queued = True
            return True
        except Exception:
            logger.warning('Command target unavailable; no instruction capture started')
            if self._current(intent, held=True):
                w.emit('notification_requested', 'Could not read the Command selection. Select the text again.')
            return False
        finally:
            if not queued:
                w.bar_status.publish(intent.bar_generation, BarPhase.IDLE)
                self._retire(intent)
                with w._lock:
                    if w._pending_config is not None and not w.busy and not w._closing:
                        w._submit(lambda: None)

    def _begin(self, intent):
        w = self.worker
        with w._lock:
            if not self._current(intent, held=True) or w.session.active:
                self._retire(intent)
                w.bar_status.publish(intent.bar_generation, BarPhase.IDLE)
                return
            event = w.session.dispatch(Input.START)
            if event is None:
                self._retire(intent)
                return
            intent.generation = event.session_id
            self.pending, self.active = None, intent
            w._cancel_request.clear()
            w._target = intent.captured.target
            w.bar_status.bind(intent.generation, intent.bar_generation)
            if not intent.accepted(intent.generation):
                self._reject(intent)
                return
        self._arm(intent)

    def _reject(self, intent, reason=''):
        w = self.worker
        with w._lock:
            if intent.generation == w.session.session_id:
                w.session.dispatch(Input.FAIL if reason else Input.CANCEL, session_id=intent.generation, reason=reason)
                w.hotkeys._controller.discard_active_recording()
        w.bar_status.session(intent.generation, BarPhase.ERROR if reason else BarPhase.IDLE, reason=reason)
        self._retire(intent)
        w.emit('processing_finished', '')

    def _arm(self, intent):
        w, services = self.worker, intent.services
        stage = 'command'
        started = False
        try:
            if not self._current(intent, held=True):
                self._reject(intent)
                return
            config = self.config_resolver(intent.choice, threads=services.config['llm'].get('threads') or 4)
            if not self._current(intent, held=True):
                self._reject(intent)
                return
            if config is None:
                w.emit('notification_requested', 'Download or resume the Command model and processor in Settings → Labs.')
                self._reject(intent, 'command_model_unavailable')
                return
            config = replace(config, idle_seconds=max(900, services.config['recording']['max_seconds'] + 65))
            intent.editor = services.cleaner.llm.command_session(config, intent.choice.model_id)
            if intent.editor is None or intent.editor.prepare(cancelled=lambda: not self._current(intent, held=True)) != 'ready':
                if self._current(intent, held=True):
                    w.emit('notification_requested', 'The local Command model could not prepare. Check its download and processor in Labs.')
                self._reject(intent, 'command_model_unavailable' if self._current(intent, held=True) else '')
                return
            if not self._current(intent, held=True):
                self._reject(intent)
                return
            if reason := services.context.verify_selection(intent.captured, for_write=False):
                w.emit('notification_requested', 'The Command selection changed while preparing. Select it again.')
                self._reject(intent)
                return
            if not self._current(intent, held=True):
                self._reject(intent)
                return
            set_context = getattr(services.asr, 'set_context', None)
            stage = 'speech'
            if set_context is not None:
                set_context(intent.captured.target)
            prepare = getattr(services.asr, 'prepare', None)
            if prepare is not None:
                prepare()
            if not self._current(intent, held=True):
                self._reject(intent)
                return
            if hasattr(services.recorder, 'chunk_callback'):
                services.recorder.chunk_callback = None
            stage = 'microphone'
            services.recorder.start()
            started = True
            with w._lock:
                if self._current(intent, held=True):
                    event = w.session.dispatch(Input.ARMED, session_id=intent.generation)
                    if event is not None:
                        w.bar_status.session(intent.generation, BarPhase.LISTENING, reason='command')
                        w.emit('recording_started')
                        limits = services.config['recording']
                        if 0 < limits['warning_seconds'] < limits['max_seconds']:
                            w._schedule(limits['warning_seconds'], lambda: w._warn(intent.generation, limits['max_seconds']))
                        w._schedule(limits['max_seconds'], lambda: w._cap(intent.generation))
                        return
            services.recorder.stop()
            started = False
            self._reject(intent)
        except Exception:
            logger.warning('Command instruction could not arm')
            if started:
                try:
                    services.recorder.stop()
                except Exception:
                    pass
            reason = {'command': 'command_model_unavailable', 'speech': 'model_unavailable',
                      'microphone': 'microphone_unavailable'}[stage]
            self._reject(intent, reason if self._current(intent, held=True) else '')

    def cancel(self):
        for intent in (self.pending, self.active):
            if intent is None:
                continue
            intent.cancelled.set()
            self._close_ports(intent)

    @staticmethod
    def _close_ports(intent):
        if intent.captured is not None:
            try:
                intent.services.context.cancel_selection(intent.captured)
            except Exception:
                logger.warning('Command selection retirement unavailable')
        if intent.editor is not None:
            try:
                intent.editor.close()
            except Exception:
                logger.warning('Command model retirement unavailable; process slot remains authoritative')

    def _retire(self, intent):
        intent.cancelled.set()
        self._close_ports(intent)
        with self.worker._lock:
            if self.pending is intent:
                self.pending = None
            if self.active is intent:
                if intent.generation == self.worker.session.session_id and self.worker.session.active:
                    self.worker.session.dispatch(Input.CANCEL, session_id=intent.generation)
                self.active = None

    def finalize(self, generation, duration, discard):
        intent, w = self.active, self.worker
        if intent is None or intent.generation != generation:
            return
        services = intent.services
        audio_path = None
        raw = ''
        persisted = []

        def retain_instruction(reason):
            if not self._current(intent) or persisted:
                return
            entry = HistoryEntry(intent.captured.target.app_title, raw, '', 'command', 'command', duration,
                w._model_id(), asr_model=w._model_id(), llm_model=intent.choice.model_id,
                audio_path=audio_path, llm_decision='edit_failed:' + reason,
                edits_json=json.dumps([{'type': 'command_instruction' if raw else 'command_asr', 'reason': reason}]))
            try:
                with w._lock:
                    if not self._current(intent):
                        return
                    identifier = services.history.append(entry)
                    persisted.append(identifier)
                w.emit('history_updated', identifier)
            except Exception:
                if raw and self._current(intent):
                    w._recover_command_result(generation, CommandEditResult(raw, 'instruction_history_unavailable'))

        try:
            audio = services.recorder.stop()
            if discard or not self._current(intent):
                return
            w.emit('processing_started')
            processing_capture = intent.captured
            if intent.captured.selection.status == 'copy_pending':
                copied = capture_command_copy(intent.captured, context=services.context,
                    inserter=services.inserter, current=lambda: self._current(intent))
                if not self._current(intent):
                    return
                if copied.captured is not None:
                    intent.captured = processing_capture = copied.captured
                else:
                    processing_capture = SelectedContext(intent.captured.target,
                        replace(intent.captured.selection, status=copied.reason, text=''))
            if services.config['recording'].get('retain_audio') and services.audio_store is not None:
                try:
                    audio_path = str(services.audio_store.save(audio, getattr(services.recorder, 'sample_rate', 16000)))
                except Exception:
                    w.emit('notification_requested', 'Could not retain Command audio; instruction recognition will continue.')
            raw = services.asr.transcribe(audio).strip()
            if not self._current(intent):
                return
            if not raw:
                if audio_path:
                    retain_instruction('asr_empty')
                w.session.dispatch(Input.NO_SPEECH, session_id=generation)
                w.bar_status.session(generation, BarPhase.IDLE)
                return
            with w._lock:
                if not self._current(intent):
                    return
                w.session.dispatch(Input.TRANSCRIBED, session_id=generation)

            def current():
                return self._current(intent) and w.session.state in (State.CLEANING, State.INSERTING)

            def run(action):
                return action() if current() else None

            def persist(action):
                with w._lock:
                    identifier = action() if current() else None
                    if identifier is not None:
                        persisted.append(identifier)
                    return identifier

            def insert(text, **options):
                with w._lock:
                    if not current():
                        return None
                    w.session.dispatch(Input.CLEANED, session_id=generation)
                return services.inserter.insert_text(text, **options)

            processor = CommandEditProcessor(editor=intent.editor, selections=services.context, history=services.history,
                inserter=SimpleNamespace(insert_text=insert), recover=lambda result: w._recover_command_result(generation, result))
            result = processor.process(processing_capture, raw, run_current=run, persist_current=persist, current=current,
                asr_model=w._model_id(), language=getattr(services.asr, 'last_language', None) or
                services.config['stt'].get('language', 'auto'), duration_seconds=duration, audio_path=audio_path,
                timings={'record': float(duration or 0), **getattr(services.asr, 'last_timings', {})})
            if not current():
                return
            w.last_command_result = result
            if result.history_id is not None:
                w.emit('history_updated', result.history_id)
            with w._lock:
                if not current():
                    return
                if w.session.state == State.CLEANING:
                    w.session.dispatch(Input.CLEANED, session_id=generation)
                w.session.dispatch(Input.INSERTED if result.reason == 'ok' else Input.NOT_INSERTED,
                                   session_id=generation, reason=result.reason)
            if result.text is None:
                bar_reason = 'command_failed'
            elif result.reason in ('ok', 'insertion_unconfirmed'):
                bar_reason = result.reason
            else:
                bar_reason = 'command_recovery'
            w.bar_status.session(generation, BarPhase.INSERTED if result.reason == 'ok' else BarPhase.NOT_INSERTED,
                                 reason=bar_reason, saved=result.history_id is not None)
            if result.text is None and result.reason != 'cancelled':
                message = {
                    'clipboard_restore_pending': 'Clipboard restoration is pending. Open History and choose Recover clipboard.',
                    'modifier_held': 'Release all shortcut keys so Command can copy the selection.',
                    'copy_timeout': 'Command could not copy the selection. Keep the text selected and try again.',
                }.get(result.reason, 'Command could not finish.')
                w.emit('notification_requested', message + (' Your instruction is saved in History.'
                    if result.history_id is not None else ' Check the instruction recovery window.'))
        except Exception:
            logger.warning('Command instruction processing unavailable')
            if self._current(intent):
                if raw or audio_path:
                    retain_instruction('processing_error' if raw else 'asr_error')
                w.session.dispatch(Input.FAIL, session_id=generation)
                w.bar_status.session(generation, BarPhase.ERROR, reason='command_failed')
                w.emit('notification_requested', 'Command could not finish. Check History and the original field before pasting again.'
                       if raw else 'Could not recognize the Command instruction. No edit was sent.')
        finally:
            if discard or intent.cancelled.is_set() or w.session.state == State.CANCELLED:
                w.bar_status.session(generation, BarPhase.IDLE)
            self._retire(intent)
            w.emit('processing_finished', '')
