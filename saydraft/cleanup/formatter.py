"""Deterministic punctuation and layout at verified replacement boundaries."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import replace
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
    r"(?<![\w.])(?:(?:[A-Za-z]\.){2,}|(?:etc|Inc|Ltd|Corp)\.)(?=\s+[A-Z])")
_FIRST_WORD = re.compile(r"^[ \t\r\n]*[([“‘\"¿¡]*([^\W\d_]+(?:['’][^\W\d_]+)*)", re.UNICODE)
_WORDS = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
_LOWER_STARTERS = frozenset(("the a an and or but if as at by for from in into of on to with this that these those "
    "it its it's they their them we we're you your you're our hello thanks thank please yes no not can could "
    "should would let let's here here's there now next send make need want have has is are was were be been "
    "do does did don't doesn't").split())


def layout_hints(context: DictationContext, source: str, text: str,
                 snippets: Iterable[str] = ()) -> DictationContext:
    """Keep snippet casing and recover cleanup-added capitals without storing source words."""
    if not context.before_caret_known:
        return replace(context, source_initial_lower="", literal_prefix=False)
    literal = any(value and text.startswith(value) for value in snippets)
    first = _FIRST_WORD.match(text)
    if first and re.search(r"(?<!\w)cap[ \t]+" + re.escape(first[1]) + r"(?!\w)", source, re.IGNORECASE):
        literal = True  # An explicit spoken capitalization command wins over inline casing.
    initial = ""
    if first:
        matches = [word for word in _WORDS.findall(source) if word.casefold() == first[1].casefold()]
        if matches and all(word[0].islower() for word in matches):
            initial = matches[0][0]
    return replace(context, source_initial_lower=initial, literal_prefix=literal)


def _wordish(char):
    return char.isalnum() or unicodedata.category(char).startswith("M")


def _spaceless(char):
    code = ord(char)
    return (0x3040 <= code <= 0x30FF or 0x3400 <= code <= 0x9FFF or 0x20000 <= code <= 0x323AF
            or 0x0E00 <= code <= 0x0EFF or 0x1000 <= code <= 0x109F or 0x1780 <= code <= 0x17FF)


def _gap(left, right):
    if not left or not right:
        return False
    a, b = left[-1], right[0]
    if (a.isspace() or b.isspace() or a in "\u200b\u200c\u200d" or b in "\u200b\u200c\u200d"
            or unicodedata.category(b).startswith("M") or _spaceless(a) or _spaceless(b)):
        return False
    if b in ",.;:!?。।۔،؛؟！？)]}’”'\"" or a in "([{‘“/@#\\_" or unicodedata.category(a) == "Sc":
        return False
    if a in "-–—" and len(left) > 1 and not left[-2].isspace():
        return False
    if a in "'\"" and (len(left) == 1 or left[-2].isspace() or left[-2] in "([{"):
        return False
    if a in ".," and len(left) > 1 and left[-2].isdigit() and b.isdigit():
        return False
    if unicodedata.category(a) == unicodedata.category(b) == "So":
        return False
    return (_wordish(a) or a in ")]}'’”\".!?:;-" or unicodedata.category(a) == "So") and (
        _wordish(b) or b in "([{'‘“\"¿¡" or unicodedata.category(b) in ("Sc", "So"))


def _sentence_start(before, text):
    if text.lstrip(" \t").startswith(("\n", "\r")) or before.rstrip(" \t").endswith(("\n", "\r")):
        return True
    tail = before.rstrip(" \t([{'‘“\"" + _CLOSERS)
    if not tail or re.search(r"(?:^|\n)[ \t]*(?:[-*•]|\d+[.)])[ \t]*$", before):
        return True
    if any(match.end() == len(tail) for match in ABBREVIATION.finditer(tail)):
        return False
    return tail[-1] in _TERMINALS


def caret_layout(text: str, context: DictationContext, *, glossary: Glossary | None = None) -> str:
    """Add boundary gaps and adjust only the initial word; never edit surrounding text."""
    if (not text or context.mode == "raw" or context.profile == "code/comments" or context.app_group == "code"
            or context.selection_truncated):
        return text
    before_ok = context.before_caret_known and context.selection_known
    after_ok = context.after_caret_known and context.selection_known
    if not before_ok and not after_ok:
        return text
    before, after, selection = context.before_caret, context.after_caret, context.selection
    left_fragment = bool(selection and before and _wordish(before[-1]) and _wordish(selection[0]))
    right_fragment = bool(selection and after and _wordish(selection[-1]) and _wordish(after[0]))
    first = _FIRST_WORD.match(text)
    if before_ok and first and not context.literal_prefix:
        from saydraft.dictation.glossary import protect_terms
        from saydraft.dictation.protect import protect_spans
        view = protect_terms(text, glossary)[0] if glossary is not None else text
        view = protect_spans(view)[0]
        word = first[1]
        protected = view[:first.end()] != text[:first.end()]
        second = re.match(r"[ \t]+([^\W\d_]+)", text[first.end():])
        title_phrase = bool(second and word.istitle() and second[1].istitle())
        if not protected and word != "I" and not word.startswith(("I'", "I’")) and not (len(word) > 1 and word.isupper()):
            mixed = any(char.isupper() for char in word[1:])
            initial = word[0]
            if mixed and context.source_initial_lower:
                initial = context.source_initial_lower
            elif not mixed and not title_phrase:
                if _sentence_start(before, text) and not (left_fragment or right_fragment):
                    original = context.source_initial_lower or initial
                    initial = "İ" if original == "i" and context.language in ("tr", "az") else original.upper()
                elif context.source_initial_lower:
                    initial = context.source_initial_lower
                elif not (left_fragment or right_fragment) and word.casefold().replace("’", "'") in _LOWER_STARTERS:
                    initial = initial.lower()
            if len(initial) == 1:
                text = text[:first.start(1)] + initial + text[first.start(1) + 1:]
    prefix = ""
    if before_ok and not left_fragment:
        if _LIST.match(text) and before and not before.endswith(("\n", "\r")):
            prefix = "\n"
        elif _gap(before, text):
            prefix = " "
    suffix = " " if after_ok and not right_fragment and _gap(text, after) else ""
    return prefix + text + suffix


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
