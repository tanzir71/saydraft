"""Revocable selection review and local answers, independent of dictation audio."""

from dataclasses import dataclass, field
import logging
import threading

from saydraft.cleanup.llm.ask import build_ask_messages
from saydraft.models.command import ask_choice, installed_command_config
from saydraft.models.hardware import latest_report
from .ask import AskProcessor, AskResult, capture_ask_source
from .session import SessionState as State

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AskReviewRequest:
    ticket: object
    source: object


@dataclass(frozen=True)
class AskStatusRequest:
    ticket: object
    job: object
    phase: str
    result: AskResult | None = None


@dataclass(frozen=True)
class AskAnswerRequest:
    ticket: object
    job: object
    delivery: object
    result: AskResult


@dataclass
class _Capture:
    services: object
    current: object
    cancelled: threading.Event = field(default_factory=threading.Event)


@dataclass
class _Review:
    services: object
    request: AskReviewRequest
    delivery: object
    cancelled: threading.Event = field(default_factory=threading.Event)
    latest_job: object = None


@dataclass
class _Job:
    review: _Review
    token: object = field(default_factory=object)
    delivery: object = field(default_factory=object)
    cancelled: threading.Event = field(default_factory=threading.Event)
    editor: object = None
    closed: bool = False
    close_lock: object = field(default_factory=threading.Lock)


class AskController:
    def __init__(self, worker, *, report_loader=latest_report, config_resolver=installed_command_config):
        self.worker, self.report_loader, self.config_resolver = worker, report_loader, config_resolver
        self._lock = threading.RLock()  # Metadata only; never held across native or storage I/O.
        self.pending = self.review = self.active = None
        self._delivery = object()

    @property
    def busy(self):
        return self.pending is not None or self.active is not None

    def invalidate_answer(self):
        with self._lock:
            self._delivery = object()

    def _choice(self, services):
        config = services.config
        tier = config.get('app', {}).get('tier', 'auto')
        report = None
        if config.get('labs', {}).get('ask_mode') is True and (
                tier == 'auto' or tier == 'pro' and config.get('command', {}).get('backend', 'auto') == 'auto'):
            try:
                report = self.report_loader()
            except Exception:
                pass
        return ask_choice(config, report)

    def _capture_current(self, intent):
        w = self.worker
        return (self.pending is intent and not intent.cancelled.is_set() and not w._closing
                and intent.services is w.services and w._pending_config is None
                and w._request_current(intent.current))

    def _review_current(self, review):
        w = self.worker
        return (self.review is review and review is not None and not review.cancelled.is_set()
                and not w._closing and review.services is w.services and w._pending_config is None
                and w.services.config.get('labs', {}).get('ask_mode') is True)

    def _job_current(self, job):
        return (self.active is job and not job.cancelled.is_set() and self._review_current(job.review)
                and job.review.latest_job is job.token)

    def review_is_current(self, request):
        review = self.review
        return (type(request) is AskReviewRequest and self._review_current(review)
                and request.ticket is review.request.ticket)

    def review_can_present(self, request):
        review = self.review
        return (self.review_is_current(request) and review.delivery is self._delivery
                and self._presentation_idle())

    def status_is_current(self, request):
        review = self.review
        return (type(request) is AskStatusRequest and self._review_current(review)
                and request.ticket is review.request.ticket and request.job is review.latest_job)

    def answer_is_current(self, request):
        review = self.review
        return (type(request) is AskAnswerRequest and self._review_current(review)
                and request.ticket is review.request.ticket and request.job is review.latest_job
                and request.delivery is self._delivery and self._presentation_idle())

    def _presentation_idle(self):
        w = self.worker
        return (not w._capturing_context
                and not w.session.active and self.pending is None and not w._benchmarking
                and not w._model_storage_busy and not w.microphone_test.active
                and not w.shortcut_capture.active and not w.practice.active)

    def _admissible(self, prefix):
        w = self.worker
        return not w.busy or (type(prefix) is int and prefix > 0 and prefix == w.session.session_id
            and w.session.state == State.CANCELLED and w._inflight <= 1 and not self.busy
            and not w.command.busy and not w._capturing_context and not w._retrying_history
            and not w._benchmarking and not w._model_storage_busy and not w.microphone_test.active
            and not w.shortcut_capture.active and not w.practice.active)

    def request(self, current, *, prefix_session_id=None):
        """Native action thread only; the GUI receives an already revoked snapshot."""
        w = self.worker
        if not w._lock.acquire(blocking=False):
            return False
        try:
            if w._closing or w._pending_config is not None or not w._request_current(current) or not self._admissible(prefix_session_id):
                return False
            intent = _Capture(w.services, current)
            with self._lock:
                self.pending = intent
                self._delivery = object()
        finally:
            w._lock.release()
        queued = False
        try:
            choice = self._choice(intent.services)
            if choice.reason != 'ready':
                if self._capture_current(intent):
                    w.emit('notification_requested', 'Needs Pro tier: Ask uses a larger local editing model. '
                        'Check performance or choose Pro in Models.' if choice.reason == 'needs_pro' else
                        'Enable Ask about selected text in Settings → Labs first.')
                return False
            w.corrections.cancel()
            captured = capture_ask_source(intent.services.context, current=lambda: self._capture_current(intent))
            if captured.source is None:
                if self._capture_current(intent):
                    w.emit('notification_requested', 'Ask needs readable selected text in a non-password field. '
                           'Select a shorter passage if this app cannot expose the full selection.')
                return False
            with w._lock:
                if not self._capture_current(intent):
                    return False
                w._submit(self._open_review, intent, captured.source)
                queued = True
            return True
        except Exception:
            logger.warning('Ask selection review unavailable')
            return False
        finally:
            if not queued:
                self._finish_capture(intent)

    def _finish_capture(self, intent):
        with self._lock:
            if self.pending is intent:
                self.pending = None
        w = self.worker
        with w._lock:
            if w._pending_config is not None and not w.busy and not w._closing:
                w._submit(lambda: None)

    def _open_review(self, intent, source):
        w, previous, request = self.worker, None, None
        try:
            with w._lock:
                if not self._capture_current(intent) or w.session.active:
                    return
                request = AskReviewRequest(object(), source)
                with self._lock:
                    previous = self.review
                    if previous is not None:
                        previous.cancelled.set()
                    self.review = _Review(intent.services, request, self._delivery)
            if previous is not None:
                w.emit('ask_retired', previous.request)
            if self.review_is_current(request):
                w.emit('ask_review_requested', request)
        finally:
            self._finish_capture(intent)

    def submit(self, request, question, action='question'):
        w = self.worker
        if not w._lock.acquire(blocking=False):
            return False
        try:
            if w.busy or not self.review_is_current(request):
                return False
            try:
                build_ask_messages(self.review.request.source.text, question, action)
            except ValueError:
                return False
            job = _Job(self.review)
            with self._lock:
                self.active = job
                self.review.latest_job = job.token
                self._delivery = job.delivery
            try:
                w._submit(self._answer, job, question, action)
            except Exception:
                with self._lock:
                    if self.active is job:
                        self.active = None
                return False
            return True
        finally:
            w._lock.release()

    def _status(self, job, phase, result=None):
        if self._job_current(job):
            self.worker.emit('ask_status_changed', AskStatusRequest(job.review.request.ticket, job.token, phase, result))

    @staticmethod
    def _close_editor(job):
        with job.close_lock:
            if job.editor is None or job.closed:
                return
            editor, job.closed = job.editor, True
        try:
            editor.close()
        except Exception:
            logger.warning('Ask model retirement unavailable; native process slot remains authoritative')

    def cancel(self, request=None):
        """GUI-safe retirement: metadata fences first; model shutdown off-thread."""
        retired, job = None, None
        with self._lock:
            review = self.review
            if request is not None and (type(request) is not AskReviewRequest or review is None
                                        or request.ticket is not review.request.ticket):
                return False
            self._delivery = object()
            if request is None and self.pending is not None:
                self.pending.cancelled.set()
            if review is not None:
                review.cancelled.set()
                retired, self.review = review.request, None
            if self.active is not None:
                job = self.active
                job.cancelled.set()
        if retired is not None:
            self.worker.emit('ask_retired', retired)
        if job is not None and job.editor is not None:
            threading.Thread(target=self._close_editor, args=(job,), name='Saydraft-Ask-stop', daemon=True).start()
        return True

    def _answer(self, job, question, action):
        w, services = self.worker, job.review.services
        result = AskResult(None, 'cancelled', action=action)
        try:
            if not self._job_current(job):
                return
            self._status(job, 'preparing')
            choice = self._choice(services)
            if choice.reason != 'ready':
                result = AskResult(None, choice.reason, action=action)
                return
            config = self.config_resolver(choice, threads=services.config['llm'].get('threads') or 4)
            if not self._job_current(job):
                return
            if config is None:
                result = AskResult(None, 'model_missing', action=action)
                return
            editor = services.cleaner.llm.command_session(config, choice.model_id)
            with self._lock:
                job.editor = editor
            if editor is None:
                result = AskResult(None, 'unavailable', action=action)
                return
            if not self._job_current(job):
                return
            if editor.prepare(cancelled=lambda: not self._job_current(job)) != 'ready':
                result = AskResult(None, 'unavailable', action=action)
                return
            if not self._job_current(job):
                return
            self._status(job, 'answering')
            def current():
                return self._job_current(job)
            def run(operation):
                return operation() if current() else None
            def persist(operation):
                with w._lock:
                    return operation() if current() else None
            def present(answer):
                if current():
                    w.emit('ask_answer_requested', AskAnswerRequest(job.review.request.ticket, job.token, job.delivery, answer))
            processor = AskProcessor(editor=editor, history=services.history, present=present)
            result = processor.process(job.review.request.source, question, action=action,
                current=current, run_current=run, persist_current=persist)
            if result.history_id is not None:
                w.emit('history_updated', result.history_id)
        except Exception:
            logger.warning('Local Ask answer unavailable')
            result = AskResult(None, 'unavailable', action=action)
        finally:
            self._close_editor(job)
            self._status(job, 'finished', result)
            with self._lock:
                if self.active is job:
                    self.active = None
