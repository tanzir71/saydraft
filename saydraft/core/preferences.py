"""Configuration-derived cleanup profiles and literal snippet expansion."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from saydraft.dictation.types import DictationContext
from saydraft.paths import resolve_data_path

logger = logging.getLogger(__name__)


def read_profiles(path: str | Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [entry for entry in data if isinstance(entry, dict)] if isinstance(data, list) else []
    except (OSError, ValueError):
        logger.warning("Could not read app profiles; using default cleanup settings")
        return []


def read_snippets(path: str | Path | None = None) -> dict[str, str]:
    snippets = {}
    source = Path(path) if path is not None else resolve_data_path("snippets.txt")
    try:
        if source.is_file():
            for line in source.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                    trigger, expansion = line.split("=", 1)
                    if trigger.strip():
                        snippets[trigger.strip().casefold()] = expansion.strip()
    except (OSError, UnicodeError):
        logger.warning("Could not read snippets; dictation remains available")
    return snippets


def expand_snippets(text: str, snippets: dict[str, str]) -> str:
    if not snippets:
        return text
    # One pass avoids recursive expansion; a callable keeps backslashes literal.
    pattern = r"(?<!\w)(" + "|".join(re.escape(key) for key in sorted(snippets, key=len, reverse=True)) + r")(?!\w)"
    return re.sub(pattern, lambda match: snippets[match[0].casefold()], text, flags=re.IGNORECASE)


def select_context(config: dict, profiles: list[dict], title: str | None) -> DictationContext:
    options = dict(config["dictation"])
    if title:
        for entry in profiles:
            match = entry.get("match")
            if isinstance(match, str) and match and match.casefold() in title.casefold():
                options.update({key: entry[key] for key in ("mode", "profile") if entry.get(key)})
                break
    mode = options.get("mode", "balanced")
    profile = options.get("profile", "general")
    mode = mode.lower() if isinstance(mode, str) else "balanced"
    profile = profile.lower() if isinstance(profile, str) else "general"
    return DictationContext(
        mode=mode if mode in {"raw", "balanced", "aggressive"} else "balanced",
        profile=profile if profile in {"general", "email", "chat", "notes", "code/comments"} else "general",
        app_title=title,
    )
