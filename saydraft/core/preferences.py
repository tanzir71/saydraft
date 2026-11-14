"""Configuration-derived cleanup profiles and literal snippet expansion."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import unicodedata
from pathlib import Path

from saydraft.dictation.types import DictationContext
from saydraft.paths import resolve_data_path
from saydraft.text_boundaries import whole_word_match
from saydraft.cleanup.styles import select_style, style_fields
from saydraft.context.app_groups import matches_app
from saydraft.snippets import MAX_BYTES, parse_document

logger = logging.getLogger(__name__)


def read_profiles(path: str | Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [entry for entry in data if isinstance(entry, dict)] if isinstance(data, list) else []
    except (OSError, ValueError):
        logger.warning("Could not read app profiles; using default cleanup settings")
        return []


def read_snippets(path: str | Path | None = None) -> dict[str, str]:
    try:
        if path is None:
            from saydraft.data.snippets import SnippetStore
            from saydraft.history import default_history_path
            entries = SnippetStore(default_history_path(), legacy_path=resolve_data_path("snippets.txt")).read().editable
            return entries
        source = Path(path)
        if source.is_file():
            with source.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Snippet file exceeds its import limit")
            return parse_snippets(raw.decode("utf-8-sig"))
    except (OSError, ValueError, sqlite3.Error):
        logger.warning("Could not read snippets; dictation remains available")
    return {}


def parse_snippets(text):
    return parse_document(text)


def protect_snippets(text: str, snippets: dict[str, str], *, originals=None) -> tuple[str, dict[str, str]]:
    """Keep explicit local expansions out of prose cleanup/model generation."""
    if not snippets:
        return text, {}
    keys = sorted(snippets, key=lambda key: len(unicodedata.normalize("NFD", key.casefold())), reverse=True)
    alternatives = []
    for i, key in enumerate(keys):
        forms = {key, key.casefold(), unicodedata.normalize("NFC", key), unicodedata.normalize("NFD", key),
            unicodedata.normalize("NFD", key.casefold())}
        variants = "|".join(re.escape(form) for form in sorted(forms, key=lambda value: (-len(value), value)))
        alternatives.append(f"(?P<S{i}>{variants})")
    pattern = r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)"
    mapping, index = {}, 0
    reserved = set(re.findall(r"__SPAN_\d+__", text))
    def replace(match):
        nonlocal index
        if not whole_word_match(text, match):
            return match[0]
        while f"__SPAN_{index}__" in reserved or f"__SPAN_{index}__" in mapping:
            index += 1
        token = f"__SPAN_{index}__"
        # Regex IGNORECASE also matches I/İ/ı. Use the matched alternative's
        # actual key rather than assuming casefold returns an existing key.
        mapping[token] = snippets[keys[int(match.lastgroup[1:])]]
        if originals is not None:
            originals[token] = match[0]
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
    protected, mapping = protect_snippets(text, snippets)
    if not mapping:
        return text
    # One pass avoids recursive expansion; a callable keeps backslashes literal.
    return re.sub("|".join(re.escape(token) for token in mapping), lambda match: mapping[match[0]], protected)


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
    from saydraft.translation import target_for
    return DictationContext(
        mode=mode, profile=profile, app_title=title, app_group=app_group,
        tone=style.tone, intensity=style.intensity,
        translation_target=target_for(config, app_group, mode=mode, profile=profile),
    )
