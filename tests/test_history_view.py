import csv
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import io
from contextlib import contextmanager
import sqlite3

import pytest

from saydraft.data.history_view import export_history, result_details, save_history_export, timestamp_label, transcript_diff
from saydraft.history import DictationHistoryStore, HistoryRow


def row(**kwargs):
    return replace(HistoryRow(4, "2026-11-13 12:30:00", "Notepad", "um hello", "Hello.", "balanced",
        "notes", 2., "Parakeet"), **kwargs)


@pytest.mark.parametrize("value", ["2026-11-12T21:45:00Z", "2026-11-12 21:45:00", "2026-11-13T03:45:00+06:00"])
def test_timestamp_labels_convert_utc_legacy_and_iso_offsets_to_the_local_day(value):
    zone = timezone(timedelta(hours=6))
    assert timestamp_label(value, now=datetime(2026, 11, 13, 9, tzinfo=zone), tz=zone) == "Today · 03:45"


def test_timestamp_labels_keep_older_years_and_tolerate_invalid_legacy_metadata():
    now = datetime(2026, 11, 13, tzinfo=timezone.utc)
    assert timestamp_label("2025-10-01 12:00:00", now=now, tz=timezone.utc) == "01 Oct 2025 · 12:00"
    assert timestamp_label("2026-10-01 12:00:00", now=now, tz=timezone.utc) == "01 Oct · 12:00"
    assert timestamp_label("unknown", now=now) == "Time unavailable"


@pytest.mark.parametrize("raw,cleaned", [
    ("um hello", "Hello."), ("same\n\ntext", "same\n\ntext"), ("", "Hello"), ("removed", ""),
    ("a\t b\r\nc", "a b\nc"), ("আমি বাংলা লিখি", "আমি বাংলায় লিখি।"),
    ("السَّلَامُ عَلَيْكُمْ", "السَّلَامُ عليكم"), ("👨‍👩‍👧‍👦 hello", "👨‍👩‍👧‍👦 hi"),
    ("x " * 30_000, "y " * 30_000),
], ids=["backtrack", "equal", "empty_before", "empty_after", "whitespace", "bengali", "arabic", "emoji", "large"])
def test_diff_reconstructs_both_originals_without_losing_characters(raw, cleaned):
    runs = transcript_diff(raw, cleaned)
    assert "".join(run.text for run in runs if run.kind != "insert") == raw
    assert "".join(run.text for run in runs if run.kind != "delete") == cleaned


def test_combining_marks_and_emoji_are_kept_inside_whole_word_changes():
    runs = transcript_diff("আমি বাংলায় লিখি 👨‍👩‍👧‍👦", "আমি বাংলা লিখি 👨‍👩‍👧‍👦")
    assert any(run.kind == "delete" and run.text.strip() == "বাংলায়" for run in runs)
    assert any(run.kind == "equal" and "👨‍👩‍👧‍👦" in run.text for run in runs)


def test_details_are_plain_text_and_tolerate_legacy_or_invalid_timings():
    value = row(asr_model="v3", llm_model="Qwen", llm_decision="rules_budget", language="bn",
                style="casual", intensity=3, timings_json='{"stt":0.2,"rules":0.001}')
    text = result_details(value)
    assert all(part in text for part in ("v3", "Qwen", "rules_budget", "bn", "casual", "0.001"))
    assert "Timings" not in result_details(replace(value, timings_json="broken"))


def test_markdown_fences_untrusted_content_and_retains_raw_clean_unicode():
    value = row(app_name='<img src="https://invalid.test/pixel">',
        raw_text="```\n<script>alert(1)</script>\n```", cleaned_text="বাংলা\nالعربية\n![link](https://invalid.test)")
    text = export_history([value], "md")
    assert "````text\n" + value.raw_text + "\n````" in text
    assert "```text\n" + value.cleaned_text + "\n```" in text
    assert '<img src="https://invalid.test/pixel">' in text
    assert "## Dictation #4" in text


def test_csv_roundtrips_unicode_quotes_and_linebreaks_without_exposing_audio_paths():
    value = row(raw_text='raw "quote",\r\nবাংলা', cleaned_text="العربية\nclean", audio_path="private/local.wav")
    parsed = list(csv.DictReader(io.StringIO(export_history([value], "csv"))))
    assert parsed[0]["raw_text"] == value.raw_text
    assert parsed[0]["cleaned_text"] == value.cleaned_text
    assert parsed[0]["asr_model"] == value.model
    assert "audio_path" not in parsed[0]


@pytest.mark.parametrize("value", ["=HYPERLINK(\"https://invalid.test\")", "+cmd", "-1+2", "@SUM(A1)", " \t=1+1", "\r\n@SUM(A1)"])
def test_csv_treats_formula_like_transcript_strings_as_text(value):
    parsed = list(csv.DictReader(io.StringIO(export_history([row(raw_text=value)], "csv"))))
    assert parsed[0]["raw_text"] == "'" + value


def test_failed_export_does_not_replace_the_existing_destination(tmp_path, monkeypatch):
    destination = tmp_path / "history.md"
    destination.write_text("existing owner export", encoding="utf-8")

    def unavailable(*args):
        raise OSError("fixture replacement failure")

    monkeypatch.setattr("saydraft.data.history_view.os.replace", unavailable)
    with pytest.raises(OSError):
        save_history_export(destination, [row()], "md")
    assert destination.read_text("utf-8") == "existing owner export"
    assert list(tmp_path.iterdir()) == [destination]


def test_export_writes_utf8_exactly_and_rejects_unknown_formats_before_opening(tmp_path):
    destination = tmp_path / "history.md"
    save_history_export(destination, [row()], "md")
    assert destination.read_text("utf-8") == export_history([row()], "md")
    previous = destination.read_bytes()
    with pytest.raises(ValueError):
        save_history_export(destination, [row()], "html")
    assert destination.read_bytes() == previous


def test_weekly_stats_use_local_monday_sunday_boundaries_without_reading_transcripts(tmp_path, monkeypatch):
    store = DictationHistoryStore(tmp_path / "history.db")
    with store._connect() as connection:
        for day, count, words, seconds in (("2026-11-08", 10, 999, 10), ("2026-11-09", 2, 80, 30),
                ("2026-11-15", 1, 40, 10), ("2026-11-16", 10, 999, 10)):
            connection.execute("INSERT INTO stats_daily(day,dictations,words,audio_seconds) VALUES(?,?,?,?)",
                (day, count, words, seconds))
    @contextmanager
    def metadata_connection():
        connection = sqlite3.connect(store.db_path)
        connection.set_authorizer(lambda action, table, column, *_: sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_READ and column in ("raw_text", "cleaned_text") else sqlite3.SQLITE_OK)
        try:
            yield connection
        finally:
            connection.close()
    monkeypatch.setattr(store, "_connect", metadata_connection)
    stats = store.weekly_stats(today=date(2026, 11, 13))
    assert (stats.start, stats.end) == (date(2026, 11, 9), date(2026, 11, 15))
    assert (stats.dictations, stats.words, stats.audio_seconds) == (3, 120, 40.)
    assert stats.words_per_minute == 180 and stats.seconds_saved == 140


def test_empty_and_year_crossing_weeks_have_honest_unmeasured_speed(tmp_path):
    store = DictationHistoryStore(tmp_path / "history.db")
    stats = store.weekly_stats(today=date(2027, 1, 1))
    assert (stats.start, stats.end) == (date(2026, 12, 28), date(2027, 1, 3))
    assert (stats.dictations, stats.words, stats.audio_seconds) == (0, 0, 0.)
    assert stats.words_per_minute is None and stats.seconds_saved == 0


def test_missing_legacy_duration_does_not_overstate_weekly_speed_or_time_saved(tmp_path):
    from saydraft.history import HistoryEntry

    store = DictationHistoryStore(tmp_path / "history.db")
    store.append(HistoryEntry("Notes", "known words", "Known words.", "raw", "notes", 2, "primary"))
    store.append(HistoryEntry("Notes", "unknown duration", "Unknown duration.", "raw", "notes", None, "legacy"))
    with store._connect() as connection:
        connection.execute("UPDATE dictations SET created_at='2026-11-13T12:00:00Z'")
        connection.execute("UPDATE stats_daily SET day='2026-11-13'")
    stats = store.weekly_stats(today=date(2026, 11, 13))
    assert stats.words == 4 and stats.audio_seconds == 2
    assert not stats.duration_complete and stats.words_per_minute is None and stats.seconds_saved is None
