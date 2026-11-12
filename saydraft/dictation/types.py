from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


CleanupMode = Literal["raw", "balanced", "aggressive"]
FormatProfile = Literal["general", "email", "chat", "notes", "code/comments"]


@dataclass(frozen=True)
class DictationContext:
    mode: CleanupMode = "balanced"
    profile: FormatProfile = "general"
    app_title: Optional[str] = None
    app_group: str = "general"
    language: str = "auto"
    before_caret: str = ""
    intensity: Optional[int] = None
    cleanup_deadline: Optional[float] = None  # Monotonic, ephemeral; never persisted.
    before_caret_known: bool = False
    selection: str = ""
    selection_known: bool = False
    after_caret: str = ""
    after_caret_known: bool = False
    source_initial_lower: str = ""
    literal_prefix: bool = False
    selection_truncated: bool = False

