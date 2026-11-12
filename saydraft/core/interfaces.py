"""Platform boundaries used by dictation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from collections.abc import Callable

from saydraft.dictation.types import DictationContext
from saydraft.history import HistoryEntry
from saydraft.insert.inserter import InsertionResult


@dataclass(frozen=True)
class TargetContext:
    focus: Any = None
    app_title: str | None = None
    is_password: bool = False
    before_caret: str = ""
    selection: str = ""
    app_exe: str = ""
    app_group: str = "general"
    app_site: str = ""
    process_id: int | None = None
    uia_status: str = "not_requested"
    control_type: int | None = None
    field_id: tuple[int, ...] = ()
    selection_truncated: bool = False
    before_caret_known: bool = False
    selection_known: bool = False
    after_caret: str = ""
    after_caret_known: bool = False


def insertion_block(target: TargetContext) -> str:
    if target.focus is None:
        return "unknown_target"
    if target.is_password:
        return "password_field"
    if target.uia_status == "changed":
        return "focus_changed"
    return "" if target.uia_status in ("ok", "not_requested") else "field_unavailable"


class AsrEngine(Protocol):
    def transcribe(self, audio: Any) -> str: ...


class StreamingAsrEngine(AsrEngine, Protocol):
    def start_stream(self, on_partial: Callable[[str], None]) -> None: ...
    def feed(self, audio: Any) -> None: ...
    def finish_stream(self) -> str: ...


class PreviewStream(Protocol):
    complete: bool
    def feed(self, audio: Any) -> None: ...
    def finish(self) -> str: ...
    def discard(self) -> None: ...


class PreviewModel(Protocol):
    def prepare(self) -> None: ...
    def create_session(self, on_partial: Callable[[str], None]) -> PreviewStream: ...


class Cleaner(Protocol):
    def process_transcript(self, raw_text: str, context: DictationContext) -> str: ...


class Formatter(Protocol):
    def format(self, text: str, target: TargetContext) -> str: ...


class Inserter(Protocol):
    def insert_text(self, text: str, *, start_focus: Any = None,
                    app_title: str | None = None, send_enter: bool = False,
                    enter_guard: Callable[[], bool] | None = None,
                    field_guard: Callable[[], str] | None = None) -> InsertionResult: ...


class ContextProvider(Protocol):
    def capture(self) -> TargetContext: ...


class HistoryStore(Protocol):
    def append(self, entry: HistoryEntry) -> int: ...
    def last_transcript(self) -> str | None: ...


class AudioCapture(Protocol):
    def start(self) -> None: ...
    def stop(self) -> Any: ...
