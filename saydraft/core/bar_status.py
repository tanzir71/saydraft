"""Generation-tagged, text-free presentation events for the dictation Bar."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging
import threading

logger = logging.getLogger(__name__)


class BarPhase(StrEnum):
    PREPARING = "preparing"
    LISTENING = "listening"
    PROCESSING = "processing"
    INSERTED = "inserted"
    NOT_INSERTED = "not_inserted"
    ERROR = "error"
    IDLE = "idle"


@dataclass(frozen=True)
class BarUpdate:
    generation: int
    phase: BarPhase
    reason: str = ""
    saved: bool = False


class BarStatus:
    """A separate generation is needed before target capture creates a session.

    The short private mutex never covers Qt delivery, field context or model work.
    Receivers must recheck is_current when queued events reach the GUI thread.
    """

    def __init__(self, callback=None):
        self.callback = callback
        self._lock = threading.Lock()
        self._generation = 0
        self._binding = None
        self._active = False

    def is_current(self, generation: int) -> bool:
        return type(generation) is int and generation == self._generation

    def begin(self) -> int:
        with self._lock:
            self._generation += 1
            generation = self._generation
            self._binding = None
            self._active = True
        self.publish(generation, BarPhase.PREPARING)
        return generation

    def bind(self, session_id: int, generation: int) -> None:
        with self._lock:
            if self.is_current(generation):
                self._binding = session_id, generation

    def cancel(self) -> None:
        with self._lock:
            if not self._active:
                return  # Hotkey reconfiguration must preserve a terminal warning.
            self._generation += 1
            generation = self._generation
            self._binding = None
            self._active = False
        self._deliver(BarUpdate(generation, BarPhase.IDLE, reason="cancelled"))

    def session(self, session_id: int, phase: BarPhase, **kwargs) -> None:
        with self._lock:
            binding = self._binding
        if binding is not None and binding[0] == session_id:
            self.publish(binding[1], phase, **kwargs)

    def publish(self, generation: int, phase: BarPhase, *, reason="", saved=False) -> None:
        with self._lock:
            if not self.is_current(generation) or not self._active:
                return
            if phase in (BarPhase.INSERTED, BarPhase.NOT_INSERTED, BarPhase.ERROR, BarPhase.IDLE):
                self._active = False
        self._deliver(BarUpdate(generation, phase, reason, saved))

    def _deliver(self, update: BarUpdate) -> None:
        if self.callback is None or not self.is_current(update.generation):
            return
        try:
            self.callback(update)
        except Exception:
            logger.debug("Bar receiver unavailable", exc_info=True)
