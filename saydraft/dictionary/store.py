"""Atomic glossary edits and narrowly scoped, revision-checked learning Undo."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import threading
import unicodedata
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_LOCKS = tuple(threading.RLock() for _ in range(64))
_METADATA = "_saydraft_learning"
_IMPORTS = "_saydraft_imports"
_CATEGORIES = ("user_terms", "protected_terms", "replacements")
_LIMIT = 4 * 1024 * 1024


class DictionaryConflict(ValueError):
    def __init__(self):
        super().__init__("Dictionary changed. Use Reload Dictionary before editing it again.")


@dataclass(frozen=True)
class DictionarySnapshot:
    data: dict
    revision: str | None

    @property
    def editable(self):
        return {key: copy.deepcopy(value) for key, value in self.data.items() if key not in (_METADATA, _IMPORTS)}


@dataclass(frozen=True)
class LearningReceipt:
    term: str
    key: str
    revision: str
    dictionary: str
    previous_term: str | None = None
    previous_learned: bool = False


def _path_lock(path):
    path = Path(path).resolve()
    return path, _LOCKS[hash(os.path.normcase(str(path))) % len(_LOCKS)]


def _bytes(path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(_LIMIT + 1)
    except FileNotFoundError:
        return None
    if len(raw) > _LIMIT:
        raise ValueError("Dictionary exceeds the 4 MB editing limit.")
    return raw


def _revision(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _validate(data):
    if not isinstance(data, dict):
        raise ValueError("Dictionary must be a JSON object.")
    for name in ("user_terms", "protected_terms"):
        if not isinstance(data.get(name, []), list) or any(
                not isinstance(term, str) or not term for term in data.get(name, [])):
            raise ValueError(f"Dictionary {name} must be a list of nonempty strings.")
    pairs = data.get("replacements", {})
    if not isinstance(pairs, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in pairs.items()):
        raise ValueError("Dictionary replacements must contain string pairs.")
    if not isinstance(data.get(_METADATA, {}), dict):
        raise ValueError("Dictionary learning metadata must be an object.")
    if not isinstance(data.get(_IMPORTS, {}), dict):
        raise ValueError("Dictionary import metadata must be an object.")


def _snapshot(path):
    raw = _bytes(path)
    try:
        data = json.loads(raw.decode("utf-8-sig")) if raw is not None else {}
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Dictionary could not be read. Repair its JSON before editing.") from exc
    _validate(data)
    return DictionarySnapshot(data, _revision(raw))


def read_dictionary(path) -> DictionarySnapshot:
    path, lock = _path_lock(path)
    with lock:
        return _snapshot(path)


def _payload(data):
    _validate(data)
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(payload) > _LIMIT:
        raise ValueError("Dictionary exceeds the 4 MB editing limit.")
    return payload


def _write(path, data, revision):
    payload = _payload(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if _revision(_bytes(path)) != revision:
            raise DictionaryConflict()
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _key(term):
    return unicodedata.normalize("NFC", term).casefold()


def _record(term):
    return {"term": term, "revision": uuid.uuid4().hex}


def term_key(term):
    return _key(term)


def _contains(data, category, record, index=None):
    if not isinstance(record, dict) or not isinstance(record.get("term"), str):
        return False
    term = record["term"]
    if category == "replacements":
        return term in data.get(category, {}) and data[category][term] == record.get("value")
    return term in (index[category] if index is not None else data.get(category, []))


def entry_source(snapshot, category, term, value=None):
    """Expose a source label without exposing learning receipt tokens."""
    if snapshot is None:
        return "Manual"
    key = _key(term)
    learned = snapshot.data.get(_METADATA, {}).get(key)
    if category == "user_terms" and isinstance(learned, dict) and learned.get("term") == term:
        return "Learned"
    records = snapshot.data.get(_IMPORTS, {}).get(category, {})
    record = records.get(key) if isinstance(records, dict) else None
    if isinstance(record, dict) and record.get("term") == term:
        if category != "replacements" or record.get("value") == value:
            return "Imported"
    return "Manual"


def _preserved_imports(snapshot, data, learned, index):
    output = {}
    for category in _CATEGORIES:
        records = snapshot.data.get(_IMPORTS, {}).get(category, {})
        if not isinstance(records, dict):
            continue
        for key, record in records.items():
            if _contains(data, category, record, index):
                output.setdefault(category, {})[key] = copy.deepcopy(record)
            elif category == "user_terms" and isinstance(record, dict) and isinstance(record.get("term"), str):
                # A learned capitalization change may be undone back to the
                # imported spelling. Preserve that origin while Undo is valid.
                active = learned.get(key)
                if (isinstance(active, dict) and _contains(data, category, active, index)
                        and _key(record["term"]) == key):
                    output.setdefault(category, {})[key] = copy.deepcopy(record)
    return output


def _set_imports(data, records):
    records = {category: values for category, values in records.items() if values}
    if records:
        data[_IMPORTS] = records
    else:
        data.pop(_IMPORTS, None)


def _metadata(data, values):
    if values:
        data[_METADATA] = values
    else:
        data.pop(_METADATA, None)


def add_term(path, term, *, learned=False) -> LearningReceipt | None:
    """Manual claims revoke learning Undo; learned case changes can be undone."""
    term = re.sub(r"\s+", " ", term).strip() if isinstance(term, str) else ""
    if not term:
        return None
    path, lock = _path_lock(path)
    with lock:
        snapshot = _snapshot(path)
        data = copy.deepcopy(snapshot.data)
        terms = data.setdefault("user_terms", [])
        data.setdefault("protected_terms", [])
        data.setdefault("replacements", {})
        key = _key(term)
        matches = [i for i, value in enumerate(terms) if _key(value) == key]
        records = data.get(_METADATA, {}).copy()
        previous = terms[matches[0]] if matches else None
        # Ambiguous duplicates and protected words are never changed by learning.
        if learned and (len(matches) > 1 or any(_key(t) == key for t in data["protected_terms"])):
            return None
        if learned and previous == term:
            return None
        if matches:
            if learned:
                terms[matches[0]] = term
        else:
            terms.append(term)
        previous_record = records.get(key)
        if learned:
            record = records[key] = _record(term)
            receipt = LearningReceipt(term, key, record["revision"], str(path), previous,
                isinstance(previous_record, dict) and previous_record.get("term") == previous)
        else:
            records.pop(key, None)
            imports = copy.deepcopy(data.get(_IMPORTS, {}))
            imported = imports.get("user_terms", {})
            if isinstance(imported, dict):
                imported.pop(key, None)
            _set_imports(data, imports)
            receipt = None
        _metadata(data, records)
        if data != snapshot.data:
            _write(path, data, snapshot.revision)
        return receipt


def undo_learning(path, receipt: LearningReceipt) -> bool:
    path, lock = _path_lock(path)
    if str(path) != receipt.dictionary:
        return False
    with lock:
        snapshot = _snapshot(path)
        data = copy.deepcopy(snapshot.data)
        records = data.get(_METADATA, {}).copy()
        if records.get(receipt.key) != {"term": receipt.term, "revision": receipt.revision}:
            return False
        terms = data.get("user_terms", [])
        matches = [i for i, term in enumerate(terms) if _key(term) == receipt.key]
        if len(matches) != 1 or terms[matches[0]] != receipt.term:
            return False
        if receipt.previous_term is None:
            terms.pop(matches[0])
        else:
            terms[matches[0]] = receipt.previous_term
        records.pop(receipt.key)
        if receipt.previous_learned:
            # A restored value gets a fresh revision: old Undo actions stay revoked.
            records[receipt.key] = _record(receipt.previous_term)
        _metadata(data, records)
        _write(path, data, snapshot.revision)
        return True


def _edited_data(snapshot, data, *, imports=None, manual_claims=()):
    data = copy.deepcopy(data)
    _validate(data)
    index = {category: Counter(data.get(category, [])) for category in ("user_terms", "protected_terms")}
    records = snapshot.data.get(_METADATA, {}).copy()
    for key, record in list(records.items()):
        if (not isinstance(record, dict) or not isinstance(record.get("term"), str)
                or index["user_terms"][record["term"]] != 1):
            records.pop(key)
    claims = list(manual_claims)
    for category, term in claims:
        if category not in _CATEGORIES or not isinstance(term, str):
            raise ValueError("Invalid Dictionary source update.")
        if category == "user_terms":
            records.pop(_key(term), None)
    _metadata(data, records)  # The editor cannot resurrect revoked learning receipts.
    origins = _preserved_imports(snapshot, data, records, index)
    for category, values in (imports or {}).items():
        if category not in _CATEGORIES or not isinstance(values, dict):
            raise ValueError("Invalid Dictionary import source.")
        for key, record in values.items():
            if not _contains(data, category, record, index) or _key(record["term"]) != key:
                raise ValueError("Imported Dictionary entry no longer matches its source update.")
            if category != "user_terms" or key not in records:
                origins.setdefault(category, {})[key] = copy.deepcopy(record)
    for category, term in claims:
        origins.get(category, {}).pop(_key(term), None)
    _set_imports(data, origins)
    return data


def validate_dictionary_edit(snapshot, data, *, imports=None, manual_claims=()):
    """Validate a complete staged edit, including its private metadata budget."""
    try:
        _payload(_edited_data(snapshot, data, imports=imports, manual_claims=manual_claims))
    except RecursionError as exc:
        raise ValueError("Dictionary nesting is too deep to edit.") from exc


def save_dictionary(path, data, *, expected_revision, imports=None, manual_claims=()):
    """Save an edited Settings snapshot; unchanged terms keep their provenance."""
    path, lock = _path_lock(path)
    with lock:
        snapshot = _snapshot(path)
        if snapshot.revision != expected_revision:
            raise DictionaryConflict()
        data = _edited_data(snapshot, data, imports=imports, manual_claims=manual_claims)
        _write(path, data, snapshot.revision)
        return read_dictionary(path)
