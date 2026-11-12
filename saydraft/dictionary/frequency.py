"""Bundled common-word membership; no downloads or inference dependencies."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "assets/dictionary/frequency"
MAX_COMPRESSED = 2_000_000
MAX_EXPANDED = 8_000_000
ALIASES = {"no": "nb", "bs": "sh", "hr": "sh", "sr": "sh", "tl": "fil"}


def normalize_word(word: str) -> str:
    """Lookup only: never use this spelling as the learned dictionary entry."""
    word = unicodedata.normalize("NFKC", word).casefold().replace("’", "'")
    return "".join(c for c in word if c != "ـ" and not (
        unicodedata.category(c) == "Mn" and "ARABIC" in unicodedata.name(c, "")))


def language_code(language: str) -> str | None:
    if (not isinstance(language, str) or len(language) > 64
            or not re.fullmatch(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*", language)):
        return None
    base = language.replace("_", "-").split("-", 1)[0].lower()
    return ALIASES.get(base, base)


@lru_cache(maxsize=1)
def _manifest() -> dict:
    with (ROOT / "manifest.json").open("rb") as stream:
        raw = stream.read(64_001)
    if len(raw) > 64_000:
        raise ValueError("Frequency manifest exceeds limit")
    data = json.loads(raw)
    if data["format"] != 1 or not isinstance(data["languages"], dict):
        raise ValueError("Unsupported frequency manifest")
    return data


def common_words(language: str) -> frozenset[str] | None:
    """None means unavailable, so correction learning must decline to guess."""
    code = language_code(language)
    if code is None:
        return None
    return _load(code)


@lru_cache(maxsize=4)
def _load(code: str) -> frozenset[str] | None:
    try:
        entry = _manifest()["languages"].get(code)
        if entry is None:
            return None
        with (ROOT / f"{code}.txt.gz").open("rb") as stream:
            packed = stream.read(MAX_COMPRESSED + 1)
        if (len(packed) > MAX_COMPRESSED or len(packed) != entry["bytes"]
                or hashlib.sha256(packed).hexdigest() != entry["sha256"]):
            return None
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
            raw = stream.read(MAX_EXPANDED + 1)
        if len(raw) > MAX_EXPANDED or not raw.endswith(b"\n"):
            return None
        words = raw.decode("utf-8").splitlines()
        result = frozenset(words)
        if len(result) != entry["words"] or len(result) != len(words) or "" in result:
            return None
        return result
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        return None


def is_common(word: str, language: str) -> bool | None:
    words = common_words(language)
    return None if words is None else normalize_word(word) in words
