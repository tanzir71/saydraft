"""Configuration-derived cleanup profiles and literal snippet expansion."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from saydraft.dictation.types import DictationContext
from saydraft.paths import resolve_data_path
from saydraft.text_boundaries import whole_word_match
from saydraft.cleanup.styles import select_style, style_fields
from saydraft.context.app_groups import matches_app

logger = logging.getLogger(__name__)


def read_profiles(path: str | Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [entry for entry in data if isinstance(entry, dict)] if isinstance(data, list) else []
    except (OSError, ValueError):
        logger.warning("Could not read app profiles; using default cleanup settings")
        return []


def read_snippets(path: str | Path | None = None) -> dict[str, str]:
    source = Path(path) if path is not None else resolve_data_path("snippets.txt")
    try:
        if source.is_file():
            return parse_snippets(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        logger.warning("Could not read snippets; dictation remains available")
    return {}


def parse_snippets(text):
    snippets = {}
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            trigger, expansion = line.split("=", 1)
            if trigger.strip():
                snippets[trigger.strip().casefold()] = expansion.strip()
    return snippets


def protect_snippets(text: str, snippets: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Keep explicit local expansions out of prose cleanup/model generation."""
    if not snippets:
        return text, {}
    pattern = r"(?<!\w)(" + "|".join(re.escape(key) for key in sorted(snippets, key=len, reverse=True)) + r")(?!\w)"
    mapping, index = {}, 0
    reserved = set(re.findall(r"__SPAN_\d+__", text))
    def replace(match):
        nonlocal index
        if not whole_word_match(text, match):
            return match[0]
        while f"__SPAN_{index}__" in reserved or f"__SPAN_{index}__" in mapping:
            index += 1
        token = f"__SPAN_{index}__"
        mapping[token] = snippets[match[0].casefold()]
        index += 1
        return token
    return re.sub(pattern, replace, text, flags=re.IGNORECASE), mapping


def restore_snippets(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    pattern = "(" + "|".join(re.escape(token) for token in mapping) + r")([.。।۔](?![.。।۔]))?"
    def expand(match):
        value, stop = mapping[match[1]], match[2] or ""
        terminal = value.rstrip().rstrip('\"\'”’)]}')
        if stop and terminal.endswith((".", "。", "।", "۔", "?", "!", "؟", "？", "！", "…")):
            stop = ""
        return value + stop
    return re.sub(pattern, expand, text)


def expand_snippets(text: str, snippets: dict[str, str]) -> str:
    if not snippets:
        return text
    # One pass avoids recursive expansion; a callable keeps backslashes literal.
    pattern = r"(?<!\w)(" + "|".join(re.escape(key) for key in sorted(snippets, key=len, reverse=True)) + r")(?!\w)"
    return re.sub(pattern, lambda match: snippets[match[0].casefold()], text, flags=re.IGNORECASE)


def select_context(config: dict, profiles: list[dict], title: str | None, *,
                   app_group="general", app_exe="", app_site="") -> DictationContext:
    options = dict(config["dictation"])
    override = {}
    for entry in profiles[:128]:
        if not matches_app(entry, app_exe, app_site, title=title, allow_title=True):
            continue
        legacy = {key: entry[key].lower() for key, allowed in (
            ("mode", {"raw", "balanced", "aggressive"}),
            ("profile", {"general", "email", "chat", "notes", "code/comments"}))
            if isinstance(entry.get(key), str) and entry[key].lower() in allowed}
        if style_fields(entry) or legacy:
            override = entry
            options.update(legacy)
            break
    mode = options.get("mode", "balanced")
    profile = options.get("profile", "general")
    mode = mode.lower() if isinstance(mode, str) else "balanced"
    profile = profile.lower() if isinstance(profile, str) else "general"
    mode = mode if mode in {"raw", "balanced", "aggressive"} else "balanced"
    profile = profile if profile in {"general", "email", "chat", "notes", "code/comments"} else "general"
    style = select_style({**options, "mode": mode, "profile": profile}, app_group, override)
    return DictationContext(
        mode=mode, profile=profile, app_title=title, app_group=app_group,
        tone=style.tone, intensity=style.intensity,
    )
