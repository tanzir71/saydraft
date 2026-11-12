"""Session lifecycle for optional correction evidence; no field reads on callers."""

import threading
from dataclasses import dataclass

from saydraft.dictionary.alignment import CorrectionCandidate, suggest_correction
from saydraft.dictionary.store import LearningReceipt


@dataclass(frozen=True)
class CorrectionSuggestion:
    epoch: int
    generation: int
    candidate: CorrectionCandidate


@dataclass(frozen=True)
class DictionaryChange:
    status: str
    receipt: LearningReceipt | None = None


@dataclass
class _Observation:
    epoch: int
    generation: int
    context: object
    ticket: object
    state: str = "preparing"
    language: str = "auto"
    queued: bool = False


class CorrectionController:
    def __init__(self, *, executor, current, emit, known_terms=lambda: ()):
        self.executor, self.current, self.emit, self.known_terms = executor, current, emit, known_terms
        self._lock = threading.Lock()
        self._epoch, self._scope, self._published = 0, None, None

    @staticmethod
    def _retire(scope):
        if scope is not None:
            try:
                scope.context.cancel_observation(scope.ticket)
            except Exception:
                pass

    def cancel(self, generation=None, *, expected=None):
        with self._lock:
            scope = self._scope
            if expected is not None and scope is not expected:
                return
            if generation is not None and (scope is None or scope.generation != generation):
                return
            self._epoch += 1
            epoch = self._epoch
            self._scope, self._published = None, None
        self._retire(scope)
        return epoch

    def prepare(self, generation, context, target, *, enabled, lease_seconds):
        epoch = self.cancel()
        prepare = getattr(context, "prepare_observation", None)
        if not enabled or prepare is None or not self.current(generation):
            return
        try:
            ticket = prepare(target, lease_seconds=lease_seconds)
            if ticket is None:
                return
            scope = _Observation(epoch, generation, context, ticket)
            with self._lock:
                accepted = epoch == self._epoch and self.current(generation)
                if accepted:
                    self._scope = scope
            if not accepted:
                self._retire(scope)
        except Exception:
            pass  # Optional learning cannot interrupt recording or expose provider errors.

    def _get(self, generation):
        with self._lock:
            scope = self._scope
            return scope if scope and scope.generation == generation and self.current(generation) else None

    def reserve(self, generation):
        scope = self._get(generation)
        if scope is None or scope.state == "reserved":
            return
        try:
            accepted = scope.context.reserve_observation(scope.ticket)
        except Exception:
            accepted = False
        with self._lock:
            keep = accepted and self._scope is scope and self.current(generation)
            if keep:
                scope.state = "reserved"
        if not keep:
            self._retire(scope)

    def hook(self, generation):
        return (lambda: self.reserve(generation)) if self._get(generation) is not None else None

    def complete(self, generation, text, result, language):
        scope = self._get(generation)
        if scope is None:
            return
        try:
            accepted = (scope.state == "reserved" and result.status == "inserted"
                and scope.context.commit_observation(scope.ticket, text))
        except Exception:
            accepted = False
        with self._lock:
            keep = accepted and self._scope is scope and self.current(generation)
            if keep:
                scope.state, scope.language = "watching", language
        if not keep:
            self._retire(scope)

    def finish(self, generation):
        with self._lock:
            scope = self._scope
        if (scope is not None and scope.generation == generation
                and (scope.state != "watching" or not self.current(generation))):
            self.cancel(generation)

    def poll(self):
        with self._lock:
            scope = self._scope
            if (scope is None or scope.state != "watching" or scope.queued
                    or not scope.ticket.done.is_set() or not self.current(scope.generation)):
                return
            scope.queued = True
        try:
            self.executor.submit(self._consume, scope)  # One queued task; never wait on UI/native work here.
        except Exception:
            self.cancel(scope.generation, expected=scope)

    def _consume(self, scope):
        try:
            if self._get(scope.generation) is not scope:
                return
            observed = scope.context.take_observation(scope.ticket)
            candidate = (suggest_correction(observed.original, observed.current, scope.language,
                known_terms=self.known_terms()) if observed is not None else None)
            with self._lock:
                accepted = self._scope is scope and self.current(scope.generation)
                if accepted:
                    self._scope = None
                    self._published = (CorrectionSuggestion(scope.epoch, scope.generation, candidate)
                        if candidate is not None else None)
                published = self._published if accepted else None
            if published is not None:
                self.emit("dictionary_suggestion", published)
        except Exception:
            self.cancel(scope.generation, expected=scope)

    def is_current(self, suggestion):
        with self._lock:
            return (self._published is suggestion and suggestion is not None
                and suggestion.epoch == self._epoch and self.current(suggestion.generation))

    def claim(self, suggestion):
        with self._lock:
            if (suggestion is None or self._published is not suggestion
                    or suggestion.epoch != self._epoch or not self.current(suggestion.generation)):
                return False
            self._published = None
            return True

    def claim_current(self, suggestion):
        with self._lock:
            return suggestion.epoch == self._epoch and self.current(suggestion.generation)
