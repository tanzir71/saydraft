from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from saydraft.text_boundaries import whole_word_match
from saydraft.dictionary.store import add_term

@dataclass(frozen=True)
class Glossary:
    user_terms: Tuple[str, ...] = ()
    protected_terms: Tuple[str, ...] = ()
    replacements: Tuple[Tuple[str, str], ...] = ()

    def all_protected(self) -> Tuple[str, ...]:
        combined = list(self.protected_terms)
        for t in self.user_terms:
            if t not in combined:
                combined.append(t)
        combined.sort(key=len, reverse=True)
        return tuple(combined)


def load_glossary(path: str) -> Glossary:
    try:
        if not path:
            return Glossary()
        if not os.path.exists(path):
            return Glossary()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) if f.readable() else {}
        if not isinstance(data, dict):
            return Glossary()
        user_terms = data.get("user_terms", [])
        protected_terms = data.get("protected_terms", [])
        replacements = data.get("replacements", {})

        if not isinstance(user_terms, list):
            user_terms = []
        if not isinstance(protected_terms, list):
            protected_terms = []
        if not isinstance(replacements, dict):
            replacements = {}

        normalized_replacements: List[Tuple[str, str]] = []
        for k, v in replacements.items():
            if isinstance(k, str) and isinstance(v, str) and k:
                normalized_replacements.append((k, v))

        return Glossary(
            user_terms=tuple([t for t in user_terms if isinstance(t, str) and t]),
            protected_terms=tuple([t for t in protected_terms if isinstance(t, str) and t]),
            replacements=tuple(normalized_replacements),
        )
    except Exception:
        return Glossary()


def learn_word(path: str | os.PathLike[str], term: str) -> Glossary:
    add_term(path, term)
    return load_glossary(os.fspath(path))


def apply_replacements(text: str, glossary: Glossary) -> str:
    if not text or not glossary.replacements:
        return text
    out = text
    for src, dst in glossary.replacements:
        pattern = r"\b" + re.escape(src) + r"\b"
        out = re.sub(pattern, dst, out, flags=re.IGNORECASE)
    return out


def protect_terms(text: str, glossary: Glossary) -> Tuple[str, Dict[str, str]]:
    protected = glossary.all_protected()
    if not text or not protected:
        return text, {}

    mapping: Dict[str, str] = {}
    idx = 0
    terms = [re.escape(term) for term in protected if term.strip()]
    if not terms:
        return text, {}
    pattern = re.compile("|".join(terms), re.IGNORECASE)

    def protect(match):
        nonlocal idx
        if not whole_word_match(text, match):
            return match[0]
        while f"__GLOSSARY_{idx}__" in text:
            idx += 1
        placeholder = f"__GLOSSARY_{idx}__"
        idx += 1
        mapping[placeholder] = match[0]  # Preserve each occurrence's original casing.
        return placeholder

    return pattern.sub(protect, text), mapping


def restore_terms(text: str, mapping: Dict[str, str]) -> str:
    if not text or not mapping:
        return text
    pattern = re.compile("|".join(re.escape(token) for token in mapping))
    return pattern.sub(lambda match: mapping[match[0]], text)

