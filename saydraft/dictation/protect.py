from __future__ import annotations

import re
from typing import Dict, Tuple

from saydraft.text_entities import ABBREVIATION, BARE_DOMAIN, EMAIL

_SPAN_PATTERNS = [
    re.compile(r"```[\s\S]*?```"),
    re.compile(r"`[^`]*?`"),
    re.compile(r"\"[^\"\n]*\""),
    re.compile(r"“[^”\n]*”"),
    re.compile(r"__(?:SPAN|GLOSSARY)_\d+__|⟦T\d+⟧"),
    ABBREVIATION,
    re.compile(r"https?://[^\s<>\"'\])]+", re.IGNORECASE),
    EMAIL,
    re.compile(r"(?<!\w)v\d+(?:\.\d+)+(?!\w)", re.IGNORECASE),
    BARE_DOMAIN,
]
_SPANS = re.compile("|".join(pattern.pattern for pattern in _SPAN_PATTERNS), re.IGNORECASE)
_ENTITIES = re.compile("|".join(pattern.pattern for pattern in _SPAN_PATTERNS[-4:]), re.IGNORECASE)


def protect_spans(text: str, *, protected_tokens=(), entities_only=False) -> Tuple[str, Dict[str, str]]:
    if not text:
        return text, {}

    mapping: Dict[str, str] = {}
    idx = 0

    def protect(match):
        nonlocal idx
        # Leave meridiems visible to the time ITN pass (three p.m. -> 3 PM).
        if match[0] in protected_tokens or match[0].lower() in ("a.m.", "p.m."):
            return match[0]
        original = match[0]
        suffix = ""
        if original.lower().startswith(("http://", "https://")) or BARE_DOMAIN.fullmatch(original):
            trimmed = original.rstrip(".,!?:;")
            suffix, original = original[len(trimmed):], trimmed
        while f"__SPAN_{idx}__" in text:
            idx += 1
        placeholder = f"__SPAN_{idx}__"
        idx += 1
        mapping[placeholder] = original
        return placeholder + suffix

    return (_ENTITIES if entities_only else _SPANS).sub(protect, text), mapping


def restore_spans(text: str, mapping: Dict[str, str]) -> str:
    if not text or not mapping:
        return text
    pattern = re.compile("|".join(re.escape(token) for token in mapping))
    return pattern.sub(lambda match: mapping[match[0]], text)

