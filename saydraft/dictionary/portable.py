"""Bounded portable Dictionary merges and atomic JSON exports."""

import copy
from dataclasses import dataclass

from .store import _CATEGORIES, _bytes, _path_lock, _revision, _validate, _write, read_dictionary, term_key


@dataclass(frozen=True)
class DictionaryImport:
    data: dict
    imports: dict
    added: int
    skipped: int
    conflicts: int


def prepare_import(data, path):
    """Merge new entries; keep existing spellings, pairs and owner extensions."""
    _validate(data)
    snapshot = read_dictionary(path)
    if snapshot.revision is None:
        raise FileNotFoundError("The selected Dictionary file no longer exists.")
    incoming = snapshot.editable
    merged = copy.deepcopy(data)
    imports = {}
    added = skipped = conflicts = 0
    for category in _CATEGORIES:
        values = incoming.get(category, {} if category == "replacements" else [])
        target = merged.setdefault(category, {} if category == "replacements" else [])
        existing = {term_key(term): term for term in target}
        for term in values:
            key = term_key(term)
            if key in existing:
                if category == "replacements" and target[existing[key]] != values[term]:
                    conflicts += 1
                else:
                    skipped += 1
                continue
            record = {"term": term}
            if category == "replacements":
                target[term] = values[term]
                record["value"] = values[term]
            else:
                target.append(term)
            imports.setdefault(category, {})[key] = record
            existing[key] = term
            added += 1
    for name, value in incoming.items():
        if name not in _CATEGORIES and name not in merged:
            merged[name] = copy.deepcopy(value)
    return DictionaryImport(merged, imports, added, skipped, conflicts)


def export_dictionary(path, data):
    """Export public data only, preserving an existing destination on failure."""
    public = {name: copy.deepcopy(value) for name, value in data.items()
        if name not in ("_saydraft_learning", "_saydraft_imports")}
    _validate(public)
    target, lock = _path_lock(path)
    with lock:
        _write(target, public, _revision(_bytes(target)))
