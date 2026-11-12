"""Plain-text History presentation and portable exports; no Qt or OS access."""

from dataclasses import dataclass
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
    lines = [f"Speech model: {row.asr_model or row.model or 'Unknown'}",
             f"Cleanup model: {row.llm_model or 'None'}",
             f"Cleanup decision: {row.llm_decision or 'Not recorded'}",
             f"Language: {row.language or 'Not recorded'}",
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


def export_history(rows, format):
    """Serialize the supplied rows only. Export never reads audio or clipboard."""
    if format == "md":
        pieces = ["# Saydraft history\n"]
        for row in rows:
            pieces += [f"\n## Dictation #{row.id}\n\n", _fenced(f"Recorded: {row.created_at}\nApp: {row.app_name or 'Unknown'}"),
                       "\n### Cleaned\n\n", _fenced(row.cleaned_text), "\n### Raw\n\n", _fenced(row.raw_text),
                       "\n### Details\n\n", _fenced(result_details(row))]
        return "".join(pieces)
    if format != "csv":
        raise ValueError("Choose Markdown or CSV")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    columns = ("id", "created_at", "app_name", "cleaned_text", "raw_text", "mode", "profile", "duration_seconds",
               "asr_model", "llm_model", "llm_decision", "language", "style", "intensity", "timings_json")
    writer.writerow(columns)
    for row in rows:
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
    return output.getvalue()


def save_history_export(path, rows, format):
    """Replace an explicitly selected destination only after a complete write."""
    text = export_history(rows, format)
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=destination.parent,
                prefix=f".{destination.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
