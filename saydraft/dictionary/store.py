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
from dataclasses import dataclass
from pathlib import Path

_LOCKS = tuple(threading.RLock() for _ in range(64))
_METADATA = "_saydraft_learning"
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
        return {key: copy.deepcopy(value) for key, value in self.data.items() if key != _METADATA}


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


def _snapshot(path):
    raw = _bytes(path)
    try:
        data = json.loads(raw.decode("utf-8")) if raw is not None else {}
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Dictionary could not be read. Repair its JSON before editing.") from exc
    _validate(data)
    return DictionarySnapshot(data, _revision(raw))


def read_dictionary(path) -> DictionarySnapshot:
    path, lock = _path_lock(path)
    with lock:
        return _snapshot(path)


def _write(path, data, revision):
    _validate(data)
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(payload) > _LIMIT:
        raise ValueError("Dictionary exceeds the 4 MB editing limit.")
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


def save_dictionary(path, data, *, expected_revision):
    """Save an edited Settings snapshot; unchanged terms keep their provenance."""
    path, lock = _path_lock(path)
    with lock:
        snapshot = _snapshot(path)
        if snapshot.revision != expected_revision:
            raise DictionaryConflict()
        data = copy.deepcopy(data)
        _validate(data)
        records = snapshot.data.get(_METADATA, {}).copy()
        for key, record in list(records.items()):
            if not isinstance(record, dict) or data.get("user_terms", []).count(record.get("term")) != 1:
                records.pop(key)
        _metadata(data, records)  # The editor cannot resurrect revoked learning receipts.
        _write(path, data, snapshot.revision)
        return read_dictionary(path)
