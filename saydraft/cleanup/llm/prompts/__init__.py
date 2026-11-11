"""Versioned text-only cleanup contract and bounded untrusted context."""

from __future__ import annotations

import html
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from itertools import islice
from pathlib import Path

STYLES = frozenset(("neutral", "formal", "casual", "very_casual"))
_LEGACY = r"__(?:GLOSSARY|SPAN)_\d+__"
_TOKEN = r"⟦T\d+⟧"
_PROTECTED = re.compile(f"{_LEGACY}|{_TOKEN}")


@dataclass(frozen=True)
class PromptHints:
    app: str = ""
    group: str = "general"
    style: str = "neutral"
    intensity: int = 3
    language: str = "auto"
    before_caret: str = ""

    def __post_init__(self):
        if self.style not in STYLES or type(self.intensity) is not int or not 1 <= self.intensity <= 4:
            raise ValueError("Unsupported cleanup style or intensity")


def _json(value):
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _text(value, limit, *, tail=False):
    value = value if isinstance(value, str) else ""
    return value[-limit:] if tail else value[:limit]


def user_message(text, hints, glossary=()):
    fields = {"app": _text(hints.app, 120), "group": _text(hints.group, 40),
              "style": hints.style, "intensity": hints.intensity, "lang": _text(hints.language, 24),
              "before_caret": _text(hints.before_caret, 120, tail=True)}
    header = "[" + " | ".join(f"{key}: {_json(value)}" for key, value in fields.items()) + "]"
    terms, seen = [], set()
    for term in islice(glossary, 200):
        term = term.strip()[:120] if isinstance(term, str) else ""
        if term and term.casefold() not in seen:
            terms.append(term)
            seen.add(term.casefold())
            if len(terms) == 40:
                break
    return f"{header}\nGlossary: {_json(terms)}\n<transcript>{html.escape(text, quote=False)}</transcript>"


@lru_cache(maxsize=1)
def _resources():
    root = Path(__file__).resolve().parent
    return (root / "system.txt").read_text(encoding="utf-8").strip(), json.loads(
        (root / "examples.json").read_text(encoding="utf-8"))


def build_messages(text, *, hints=None, glossary=()):
    hints = hints or PromptHints()
    system, examples = _resources()
    messages = [{"role": "system", "content": system}]
    for example in examples:
        output = example.get(hints.style, example.get("output", ""))
        if hints.style in ("casual", "very_casual"):
            output = output.removesuffix(".")
        messages.extend((
            {"role": "user", "content": user_message(example["input"], PromptHints(style=hints.style))},
            {"role": "assistant", "content": output}))
    messages.append({"role": "user", "content": user_message(text, hints, glossary)})
    return messages


def output_token_limit(input_tokens):
    if type(input_tokens) is not int or input_tokens < 0:
        raise ValueError("Input token count must be a nonnegative integer")
    return math.ceil(input_tokens * 1.25) + 16


@dataclass(frozen=True)
class ProtectedPrompt:
    text: str
    mapping: tuple[tuple[str, str], ...]

    def restore(self, candidate):
        if re.findall(_TOKEN, candidate) != re.findall(_TOKEN, self.text) or re.search(_LEGACY, candidate):
            return None
        remaining = candidate
        for token, _original in self.mapping:
            remaining = remaining.replace(token, "")
        if "⟦T" in remaining:
            return None
        for token, original in self.mapping:
            candidate = candidate.replace(token, original)
        return candidate


def bridge_protected(text):
    originals, index = {}, 0

    def replace(match):
        nonlocal index
        original = match[0]
        if original not in originals:
            while f"⟦T{index}⟧" in text:
                index += 1
            originals[original] = f"⟦T{index}⟧"
            index += 1
        return originals[original]

    converted = _PROTECTED.sub(replace, text)
    return ProtectedPrompt(converted, tuple((token, original) for original, token in originals.items()))
