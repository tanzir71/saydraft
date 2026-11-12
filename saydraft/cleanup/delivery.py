"""Parse explicitly enabled delivery commands from the original dictation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from saydraft.text_boundaries import whole_word_match

if TYPE_CHECKING:
    from saydraft.dictation.types import DictationContext

_ENTER = re.compile(r"(?<!\w)press[ \t]+enter[.!。।۔！]?[ \t\r\n]*$", re.IGNORECASE)
_MENTION = {"say", "says", "said", "saying", "type", "typed", "word", "words", "phrase", "command",
            "called", "label", "named", "literal", "to"}


@dataclass(frozen=True)
class DeliveryIntent:
    text: str
    send_enter: bool = False


def _inside_literal(text):
    quote, code, index = "", "", 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if code:
            if text.startswith(code, index):
                index += len(code)
                code = ""
                continue
        elif quote:
            apostrophe = char in "'’" and index and index + 1 < len(text) and (
                text[index - 1].isalnum() and text[index + 1].isalnum())
            if char == quote and not apostrophe:
                quote = ""
        elif char == "`":
            code = "```" if text.startswith("```", index) else "`"
            index += len(code)
            continue
        elif char in '\"“‘' or char == "'" and (not index or not text[index - 1].isalnum()):
            quote = {"“": "”", "‘": "’"}.get(char, char)
        index += 1
    return bool(quote or code)


def trailing_enter(text: str, context: DictationContext, *, enabled: bool = False) -> DeliveryIntent:
    if (enabled is not True or context.app_group in ("email", "docs")
            or context.profile in ("email", "notes")):
        return DeliveryIntent(text)
    match = _ENTER.search(text)
    if match is None or not whole_word_match(text, match):
        return DeliveryIntent(text)
    prefix = text[:match.start()]
    words = re.findall(r"[^\W_]+", prefix.casefold())
    if (not prefix.strip() or _inside_literal(prefix) or words and words[-1] in _MENTION
            or len(words) > 1 and words[-2] in {"can", "could", "would", "should", "did", "do"} and words[-1] == "you"
            or prefix.rstrip().endswith(("/", "\\", "@", "_"))):
        return DeliveryIntent(text)
    if context.app_group == "code" or context.profile == "code/comments":
        if re.match(r"\s*(?:#|//|--|<!--)", prefix.rsplit("\n", 1)[-1]):
            return DeliveryIntent(text)
    content = prefix.rstrip(" \t")
    if content.endswith(","):
        content = content[:-1].rstrip(" \t")
    return DeliveryIntent(content, True) if content.strip() else DeliveryIntent(text)
