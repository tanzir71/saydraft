"""Conservative final punctuation policy; caret-aware layout follows in P5.4."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from saydraft.text_entities import ABBREVIATION

if TYPE_CHECKING:
    from saydraft.dictation.types import DictationContext
    from saydraft.dictation.glossary import Glossary

_PERIODS = ".。।۔"
_TERMINALS = _PERIODS + "!?！？؟…"
_CLOSERS = '\"\'”’)]}'
_LIST = re.compile(r"(?m)^[ \t]*(?:[-*•]|\d+[.)])[ \t]+\S")
_DECIMAL = re.compile(r"(?<!\w)\d+(?:[.,]\d+)+(?!\w)")
_INITIAL = re.compile(r"(?<!\w)[A-Z][a-z]+[ \t]+(?:[A-Z]\.[ \t]+)+(?=[A-Z][a-z])")
_AMBIGUOUS_ABBREVIATION = re.compile(
    r"(?<!\w)(?:(?:[A-Za-z]\.){2,}|(?:etc|Inc|Ltd|Corp)\.)(?=\s+[A-Z])")


def final_punctuation(text: str, context: DictationContext, *,
                      drop_message_period: bool = True, glossary: Glossary | None = None) -> str:
    """Remove only a single sentence's external period; preserve protected data."""
    if not text or context.mode == "raw" or context.profile == "code/comments" or context.app_group == "code":
        return text
    body = text.rstrip()
    suffix = text[len(body):]
    if not body:
        return text
    if context.profile == "email":
        # Inspect restored punctuation: a quote, abbreviation or Unicode stop may
        # already terminate the sentence. Lists keep their existing layout.
        terminal = body.rstrip(_CLOSERS)
        if terminal and terminal[-1] not in _TERMINALS + ":;" and not _LIST.search(body):
            return body + "." + suffix
        return text
    messaging = context.app_group in ("messages", "work_chat") or (
        context.profile == "chat" and context.app_group in ("", "general"))
    if (not drop_message_period or not messaging or context.profile == "notes"
            or context.app_group in ("email", "docs") or body[-1] not in _PERIODS
            or "\n" in body or "\r" in body or _LIST.search(body)):
        return text
    if len(body) < 2 or body[-2] in _TERMINALS or not any(char.isalnum() for char in body):
        return text
    if _AMBIGUOUS_ABBREVIATION.search(body):
        return text

    # Local imports keep this formatter independently importable while the
    # dictation package re-exports its pipeline.
    from saydraft.dictation.glossary import protect_terms
    from saydraft.dictation.protect import protect_spans

    view = protect_terms(body, glossary)[0] if glossary is not None else body
    view, spans = protect_spans(view)
    if any(value.startswith(('"', '“')) and sum(char in _TERMINALS for char in value) > 1
           for value in spans.values()):
        return text
    view = ABBREVIATION.sub("TOKEN", view)
    view = _INITIAL.sub("TOKEN", view)
    view = _DECIMAL.sub("TOKEN", view)
    # A final period inside a literal/glossary/abbreviation is not ours to trim.
    # Any other sentence stop is evidence of multiple sentences, including
    # scripts without spaces between sentences. Ambiguous input stays unchanged.
    if not view or view[-1] not in _PERIODS or any(char in _TERMINALS for char in view[:-1]):
        return text
    return body[:-1] + suffix
