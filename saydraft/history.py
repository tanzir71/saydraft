"""SQLite-backed dictation history."""

from __future__ import annotations

import os
import sqlite3
import json
from contextlib import contextmanager
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .data.db import HISTORY_METADATA, migrate_database

_HISTORY_FIELDS = ("app_name", "raw_text", "cleaned_text", "mode", "profile", "duration_seconds", "model")
_ALL_FIELDS = (*_HISTORY_FIELDS, *HISTORY_METADATA)


@dataclass(frozen=True)
class WeeklyStats:
    start: date
    end: date
    dictations: int
    words: int
    audio_seconds: float
    duration_complete: bool = True

    @property
    def words_per_minute(self):
        return self.words * 60 / self.audio_seconds if self.duration_complete and self.audio_seconds > 0 else None

    @property
    def seconds_saved(self):
        return max(0., self.words * 60 / 40 - self.audio_seconds) if self.duration_complete else None


@dataclass(frozen=True)
class HistoryEntry:
    app_name: str | None
    raw_text: str
    cleaned_text: str
    mode: str
    profile: str
    duration_seconds: float | None
    model: str
    app_exe: str | None = None
    app_group: str | None = None
    style: str | None = None
    intensity: int | None = None
    language: str | None = None
    asr_model: str | None = None
    llm_model: str | None = None
    llm_decision: str | None = None
    timings_json: str = "{}"
    edits_json: str = "[]"
    audio_path: str | None = None


@dataclass(frozen=True)
class HistoryRow:
    id: int
    created_at: str
    app_name: str | None
    raw_text: str
    cleaned_text: str
    mode: str
    profile: str
    duration_seconds: float | None
    model: str
    app_exe: str | None = None
    app_group: str | None = None
    style: str | None = None
    intensity: int | None = None
    language: str | None = None
    asr_model: str | None = None
    llm_model: str | None = None
    llm_decision: str | None = None
    timings_json: str = "{}"
    edits_json: str = "[]"
    audio_path: str | None = None


def default_history_path(local_appdata: str | os.PathLike[str] | None = None) -> Path:
    base = Path(local_appdata) if local_appdata is not None else _default_local_appdata()
    return base / "Saydraft" / "history.db"


class DictationHistoryStore:
    def __init__(self, db_path: str | os.PathLike[str] | None = None, *, import_paths=None):
        self.db_path = Path(db_path) if db_path is not None else default_history_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migration = migrate_database(self.db_path, import_paths=import_paths)

    def append(self, entry: HistoryEntry) -> int:
        values = {name: getattr(entry, name) for name in _ALL_FIELDS}
        values["asr_model"] = entry.asr_model or entry.model
        timings = json.loads(entry.timings_json)
        processing_seconds = sum(float(timings.get(stage, 0) or 0)
                                 for stage in ("vad", "stt", "lid", "rules", "llm", "insert"))
        with self._connect() as conn:
            edits = json.loads(entry.edits_json)
            retry = False
            for item in edits if isinstance(edits, list) else []:
                if (isinstance(item, dict) and item.get("type") == "asr_retry" and
                        type(item.get("source_history_id")) is int and entry.audio_path):
                    retry = conn.execute("SELECT 1 FROM dictations WHERE id=? AND audio_path=?",
                                         (item["source_history_id"], entry.audio_path)).fetchone() is not None
                    if retry:
                        break
            cursor = conn.execute(
                f"INSERT INTO dictations ({', '.join(_ALL_FIELDS)}) VALUES ({', '.join('?' for _ in _ALL_FIELDS)})",
                tuple(values[name] for name in _ALL_FIELDS),
            )
            conn.execute("""INSERT INTO stats_daily(day, dictations, words, audio_seconds, processing_seconds)
                SELECT date(created_at, 'localtime'), ?, ?, ?, ? FROM dictations WHERE id=?
                ON CONFLICT(day) DO UPDATE SET dictations=dictations+excluded.dictations,
                words=words+excluded.words, audio_seconds=audio_seconds+excluded.audio_seconds,
                processing_seconds=processing_seconds+excluded.processing_seconds""",
                (0 if retry else 1, 0 if retry else len(entry.cleaned_text.split()),
                 0 if retry else float(entry.duration_seconds or 0), processing_seconds, cursor.lastrowid))
            return int(cursor.lastrowid)

    def list_recent(self, *, limit: int = 100) -> list[HistoryRow]:
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, created_at, {', '.join(_ALL_FIELDS)} FROM dictations
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [HistoryRow(*row) for row in rows]

    def last_transcript(self) -> str | None:
        """Read the latest nonblank saved result without loading raw text or full rows."""
        with self._connect() as conn:
            for (text,) in conn.execute("SELECT cleaned_text FROM dictations ORDER BY id DESC"):
                if isinstance(text, str) and text.strip():
                    return text  # Preserve exact stored whitespace, punctuation and casing.
        return None

    def weekly_stats(self, *, today=None) -> WeeklyStats:
        """Local Monday–Sunday aggregates, without loading any transcript text."""
        today = today or date.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        with self._connect() as conn:
            row = conn.execute("""SELECT coalesce(sum(dictations),0), coalesce(sum(words),0),
                coalesce(sum(audio_seconds),0) FROM stats_daily WHERE day>=? AND day<=?""",
                (start.isoformat(), end.isoformat())).fetchone()
            unknown = conn.execute("""SELECT count(*) FROM dictations
                WHERE (duration_seconds IS NULL OR duration_seconds<=0)
                AND date(created_at,'localtime')>=? AND date(created_at,'localtime')<=?""",
                (start.isoformat(), end.isoformat())).fetchone()[0]
        return WeeklyStats(start, end, int(row[0]), int(row[1]), float(row[2]), not unknown)

    def update_timings(self, row_id: int, timings: dict[str, float]) -> None:
        """Complete timing metadata after insertion, retaining the earlier text record."""
        with self._connect() as conn:
            existing = conn.execute("SELECT created_at, timings_json FROM dictations WHERE id=?", (row_id,)).fetchone()
            if existing is None:
                return
            old = json.loads(existing[1])
            stages = ("vad", "stt", "lid", "rules", "llm", "insert")
            delta = sum(float(timings.get(stage, 0)) - float(old.get(stage, 0)) for stage in stages)
            conn.execute("UPDATE dictations SET timings_json=? WHERE id=?", (json.dumps(timings), row_id))
            conn.execute("UPDATE stats_daily SET processing_seconds=processing_seconds+? WHERE day=date(?, 'localtime')",
                         (delta, existing[0]))

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def _default_local_appdata() -> Path:
    configured = os.environ.get("LOCALAPPDATA")
    if configured:
        return Path(configured)
    return Path.home() / "AppData" / "Local"
