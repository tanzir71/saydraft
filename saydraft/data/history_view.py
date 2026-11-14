"""Plain-text History presentation and portable exports; no Qt or OS access."""

from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import csv
import io
import json
import os
from pathlib import Path
import re
import tempfile


@dataclass(frozen=True)
class DiffRun:
    kind: str
    text: str


def timestamp_label(value, *, now=None, tz=None):
    """Display legacy UTC SQLite timestamps and ISO timestamps in local time."""
    try:
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        local = moment.astimezone(tz)
    except (TypeError, ValueError, OverflowError, OSError):
        return "Time unavailable"
    today = (now or datetime.now()).astimezone(tz).date()
    day = "Today" if local.date() == today else local.strftime("%d %b" if local.year == today.year else "%d %b %Y")
    return f"{day} · {local:%H:%M}"


def transcript_diff(raw, cleaned):
    """Preserve every character, including whitespace and non-Latin scripts.

    Long entries use a coarse before/after diff to bound GUI-thread work. Small
    changes use token-level matching rather than splitting graphemes into edits.
    """
    if raw == cleaned:
        return [DiffRun("equal", cleaned)] if cleaned else []
    if len(raw) + len(cleaned) > 50_000:
        return [DiffRun(kind, value) for kind, value in (("delete", raw), ("insert", cleaned)) if value]
    before = re.findall(r"\S+\s*|\s+", raw, re.UNICODE)
    after = re.findall(r"\S+\s*|\s+", cleaned, re.UNICODE)
    runs = []
    for kind, a, b, c, d in SequenceMatcher(None, before, after).get_opcodes():
        if kind == "equal":
            runs.append(DiffRun("equal", "".join(after[c:d])))
        else:
            if kind in ("delete", "replace"):
                runs.append(DiffRun("delete", "".join(before[a:b])))
            if kind in ("insert", "replace"):
                runs.append(DiffRun("insert", "".join(after[c:d])))
    return runs


def result_details(row):
    if row.mode == 'command':
        lines = ['Task: Command instruction' if not row.cleaned_text else 'Task: Command edit',
                 f"Speech model: {row.asr_model or row.model or 'Unknown'}",
                 f"Edit model: {row.llm_model or 'None'}", f"Edit outcome: {row.llm_decision or 'Not recorded'}",
                 f"Language: {row.language or 'Not recorded'}"]
        try:
            edits = json.loads(row.edits_json)
        except (TypeError, ValueError):
            edits = []
        for item in edits if isinstance(edits, list) else []:
            if isinstance(item, dict) and item.get('type') == 'command_edit' and type(item.get('instruction')) is str:
                lines.extend(['', 'Instruction:', item['instruction']])
                break
        if not row.cleaned_text and row.raw_text:
            lines.extend(['', 'Recognized instruction:', row.raw_text])
    else:
        lines = [f"Speech model: {row.asr_model or row.model or 'Unknown'}",
             f"Cleanup model: {row.llm_model or 'None'}",
             f"Cleanup decision: {row.llm_decision or 'Not recorded'}",
             f"Language: {row.language or 'Not recorded'}", f"Cleanup mode: {row.mode}",
                 f"Style: {row.style or row.profile} · intensity: {row.intensity or 'Not recorded'}"]
    try:
        timings = json.loads(row.timings_json)
    except (TypeError, ValueError):
        timings = None
    if isinstance(timings, dict) and timings:
        lines.extend(["", "Timings (seconds):", json.dumps(timings, ensure_ascii=False, indent=2)])
    return "\n".join(lines)


def _fenced(text):
    fence = "`" * max(3, 1 + max((len(match) for match in re.findall(r"`+", text)), default=0))
    return f"{fence}text\n{text}" + ("" if text.endswith("\n") else "\n") + f"{fence}\n"


def iter_history_export(rows, format):
    """Serialize the supplied rows only. Export never reads audio or clipboard."""
    if format == "md":
        yield "# Saydraft history\n"
        for row in rows:
            yield "".join([f"\n## Dictation #{row.id}\n\n", _fenced(f"Recorded: {row.created_at}\nApp: {row.app_name or 'Unknown'}"),
                       "\n### Cleaned\n\n", _fenced(row.cleaned_text), "\n### Raw\n\n", _fenced(row.raw_text),
                       "\n### Details\n\n", _fenced(result_details(row))])
        return
    if format != "csv":
        raise ValueError("Choose Markdown or CSV")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    columns = ("id", "created_at", "app_name", "cleaned_text", "raw_text", "mode", "profile", "duration_seconds",
               "asr_model", "llm_model", "llm_decision", "language", "style", "intensity", "timings_json", "edits_json")
    writer.writerow(columns)
    yield output.getvalue()
    for row in rows:
        output.seek(0)
        output.truncate(0)
        values = []
        for name in columns:
            value = getattr(row, name)
            if name == "asr_model":
                value = value or row.model
            # CSV commonly opens in a spreadsheet: treat every user string as
            # text even when its first meaningful character is a formula marker.
            if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
        yield output.getvalue()


def export_history(rows, format):
    return "".join(iter_history_export(rows, format))


class HistoryExportCancelled(Exception):
    pass


def save_history_export(path, rows, format, *, cancelled=lambda: False):
    """Replace an explicitly selected destination only after a complete write."""
    if format not in ("md", "csv"):
        raise ValueError("Choose Markdown or CSV")
    destination = Path(path)
    temporary = None
    count = 0
    def check():
        if cancelled():
            raise HistoryExportCancelled()
    def counted():
        nonlocal count
        for row in rows:
            check()
            count += 1
            yield row
    try:
        check()
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=destination.parent,
                prefix=f".{destination.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            for text in iter_history_export(counted(), format):
                check()
                stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        check()
        os.replace(temporary, destination)
        return count
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
