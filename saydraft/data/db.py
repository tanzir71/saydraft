"""Additive SQLite migrations, consistent backups and copy-only imports."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)
SCHEMA_VERSION = 3
HISTORY_METADATA = {
    "app_exe": "TEXT", "app_group": "TEXT", "style": "TEXT", "intensity": "INTEGER",
    "language": "TEXT", "asr_model": "TEXT", "llm_model": "TEXT", "llm_decision": "TEXT",
    "timings_json": "TEXT NOT NULL DEFAULT '{}'", "edits_json": "TEXT NOT NULL DEFAULT '[]'",
    "audio_path": "TEXT",
}
_BASE_HISTORY = """CREATE TABLE IF NOT EXISTS dictations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    app_name TEXT, raw_text TEXT NOT NULL, cleaned_text TEXT NOT NULL,
    mode TEXT NOT NULL, profile TEXT NOT NULL, duration_seconds REAL, model TEXT NOT NULL
)"""
_TABLES = {
    "notes": """CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
        search_text TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision > 0))""",
    "note_state": """CREATE TABLE IF NOT EXISTS note_state (
        name TEXT PRIMARY KEY, note_id TEXT NOT NULL)""",
    "dictionary": """CREATE TABLE IF NOT EXISTS dictionary (
        id INTEGER PRIMARY KEY, term TEXT NOT NULL, normalized TEXT NOT NULL,
        kind TEXT NOT NULL, replacement TEXT, source TEXT NOT NULL DEFAULT 'manual',
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        UNIQUE(normalized, kind))""",
    "snippets": """CREATE TABLE IF NOT EXISTS snippets (
        id INTEGER PRIMARY KEY, trigger TEXT NOT NULL, normalized TEXT NOT NULL UNIQUE,
        expansion TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual')""",
    "styles": """CREATE TABLE IF NOT EXISTS styles (
        id INTEGER PRIMARY KEY, match TEXT NOT NULL UNIQUE, app_group TEXT NOT NULL DEFAULT 'general',
        tone TEXT NOT NULL DEFAULT 'neutral', intensity INTEGER, mode TEXT, profile TEXT,
        settings_json TEXT NOT NULL DEFAULT '{}')""",
    "stats_daily": """CREATE TABLE IF NOT EXISTS stats_daily (
        day TEXT PRIMARY KEY, dictations INTEGER NOT NULL DEFAULT 0,
        words INTEGER NOT NULL DEFAULT 0, audio_seconds REAL NOT NULL DEFAULT 0,
        processing_seconds REAL NOT NULL DEFAULT 0)""",
    "legacy_imports": """CREATE TABLE IF NOT EXISTS legacy_imports (
        source_path TEXT NOT NULL, sha256 TEXT NOT NULL,
        imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        PRIMARY KEY(source_path, sha256))""",
}


@dataclass(frozen=True)
class MigrationReport:
    from_version: int
    to_version: int
    backup_path: Path | None
    imported: dict[str, int]


def _backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = path.with_name(f"{path.name}.bak-{stamp}-{uuid.uuid4().hex[:8]}")
    with target.open("xb"):
        pass
    with closing(sqlite3.connect(target)) as backup, closing(sqlite3.connect(path, timeout=10)) as source:
        # The migration connection already owns the writer reservation. A
        # separate reader can copy its pre-change snapshot without waiting on
        # that connection's active write transaction.
        source.backup(backup)
    return target


def migrate_database(path: str | Path, *, import_paths: dict[str, Path] | None = None) -> MigrationReport:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    try:
        # Serialize competing initializers before inspecting schema metadata.
        connection.execute('BEGIN IMMEDIATE')
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError("This history database requires a newer version of Saydraft")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns = {row[1] for row in connection.execute("PRAGMA table_info(dictations)")}
        indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        for table, required in (("notes", {"id", "kind", "title", "body", "search_text", "created_at", "updated_at", "revision"}),
                                ("note_state", {"name", "note_id"})):
            if table in tables:
                info = {row[1]: row for row in connection.execute(f'PRAGMA table_info("{table}")')}
                primary = 'id' if table == 'notes' else 'name'
                if (not required.issubset(info) or {name for name, row in info.items() if row[5]} != {primary}
                        or any(not info[name][3] for name in required - {primary})
                        or any(info[name][2].upper() != ('INTEGER' if name == 'revision' else 'TEXT') for name in required)):
                    raise ValueError("Unrecognized Notes schema; existing data has been preserved")
        needs_schema = (version < SCHEMA_VERSION or not set(HISTORY_METADATA).issubset(columns)
                        or not set(_TABLES).issubset(tables) or "idx_dictations_audio_path" not in indexes
                        or "idx_notes_updated" not in indexes)
        backup_path = _backup(path) if needs_schema and tables else None
        with connection:
            connection.execute(_BASE_HISTORY)
            for name, declaration in HISTORY_METADATA.items():
                if name not in columns:
                    connection.execute(f'ALTER TABLE dictations ADD COLUMN "{name}" {declaration}')
            for statement in _TABLES.values():
                connection.execute(statement)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_dictations_audio_path ON dictations(audio_path) WHERE audio_path IS NOT NULL")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC, id DESC)")
            connection.execute("UPDATE dictations SET asr_model = model WHERE asr_model IS NULL")
            if "stats_daily" not in tables:
                _backfill_stats(connection)
            imported = _import_sources(connection, import_paths or {
                "glossary": path.parent / "glossary.json", "snippets": path.parent / "snippets.txt",
                "profiles": path.parent / "app_profiles.json",
            })
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return MigrationReport(version, SCHEMA_VERSION, backup_path, imported)
    finally:
        connection.close()


def _backfill_stats(connection):
    daily = defaultdict(lambda: [0, 0, 0.0])
    for day, cleaned, duration in connection.execute(
        "SELECT date(created_at, 'localtime'), cleaned_text, duration_seconds FROM dictations WHERE mode != 'command'"
    ):
        values = daily[day or "unknown"]
        values[0] += 1
        values[1] += len(cleaned.split())
        values[2] += float(duration or 0)
    connection.executemany(
        "INSERT INTO stats_daily(day, dictations, words, audio_seconds) VALUES (?, ?, ?, ?)",
        [(day, *values) for day, values in daily.items()],
    )


def _import_sources(connection, paths):
    imported = {}
    for kind, source in paths.items():
        if kind == "snippets":
            from saydraft.snippets import CANONICAL_SOURCE
            if connection.execute("SELECT 1 FROM legacy_imports WHERE source_path=?", (CANONICAL_SOURCE,)).fetchone():
                continue  # A managed live table must never resurrect deleted legacy entries.
        source = Path(source)
        if not source.is_file():
            continue
        try:
            if kind == "snippets":
                from saydraft.snippets import MAX_BYTES
                with source.open("rb") as stream:
                    content = stream.read(MAX_BYTES + 1)
                if len(content) > MAX_BYTES:
                    logger.warning("Skipped oversized legacy snippets; its source file is preserved")
                    continue
            else:
                content = source.read_bytes()
        except OSError:
            logger.warning("Could not read legacy %s; its source file is preserved", kind)
            continue
        digest = hashlib.sha256(content).hexdigest()
        if connection.execute("SELECT 1 FROM legacy_imports WHERE source_path=? AND sha256=?",
                              (str(source.resolve()), digest)).fetchone():
            continue
        before = connection.total_changes
        try:
            text = content.decode("utf-8-sig")
            if kind == "glossary":
                _import_glossary(connection, json.loads(text))
            elif kind == "snippets":
                from saydraft.snippets import parse_document, trigger_key
                for trigger, expansion in parse_document(text).items():
                    connection.execute("INSERT OR IGNORE INTO snippets(trigger, normalized, expansion, source) VALUES (?, ?, ?, 'import')",
                                       (trigger, trigger_key(trigger), expansion))
            elif kind == "profiles":
                _import_profiles(connection, json.loads(text))
            else:
                raise ValueError("unsupported legacy source")
        except (ValueError, TypeError):
            logger.warning("Skipped invalid legacy %s; its source file is preserved", kind)
            continue
        imported[kind] = connection.total_changes - before
        connection.execute("INSERT INTO legacy_imports(source_path, sha256) VALUES (?, ?)",
                           (str(source.resolve()), digest))
    return imported


def _import_glossary(connection, data):
    if not isinstance(data, dict):
        raise ValueError("glossary must be a JSON object")
    for kind, key in (("user", "user_terms"), ("protected", "protected_terms")):
        terms = data.get(key, [])
        for term in terms if isinstance(terms, list) else []:
            if isinstance(term, str) and term.strip():
                term = term.strip()
                connection.execute("INSERT OR IGNORE INTO dictionary(term, normalized, kind, source) VALUES (?, ?, ?, 'import')",
                                   (term, term.casefold(), kind))
    replacements = data.get("replacements", {})
    for term, replacement in (replacements.items() if isinstance(replacements, dict) else []):
        if isinstance(term, str) and isinstance(replacement, str) and term.strip():
            connection.execute("INSERT OR IGNORE INTO dictionary(term, normalized, kind, replacement, source) VALUES (?, ?, 'replacement', ?, 'import')",
                               (term.strip(), term.strip().casefold(), replacement))


def _import_profiles(connection, data):
    if not isinstance(data, list):
        raise ValueError("profiles must be a JSON array")
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get("match"), str):
            continue
        def string(key, default):
            return entry.get(key) if isinstance(entry.get(key), str) else default
        mode = string("mode", "balanced")
        connection.execute("""INSERT OR IGNORE INTO styles
            (match, app_group, tone, intensity, mode, profile, settings_json) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entry["match"], string("app_group", "general"), string("tone", "neutral"),
             {"raw": 0, "balanced": 1, "aggressive": 3}.get(mode, 1), mode,
             string("profile", "general"), json.dumps(entry, ensure_ascii=False)))
