import sqlite3


def test_history_store_appends_and_reads_dictations(tmp_path):
    from saydraft.history import DictationHistoryStore, HistoryEntry

    db_path = tmp_path / "history.db"
    store = DictationHistoryStore(db_path)

    entry_id = store.append(
        HistoryEntry(
            app_name="Notepad",
            raw_text="um hello",
            cleaned_text="Hello.",
            mode="balanced",
            profile="notes",
            duration_seconds=2.5,
            model="base",
        )
    )

    assert entry_id == 1
    rows = store.list_recent(limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == 1
    assert row.app_name == "Notepad"
    assert row.raw_text == "um hello"
    assert row.cleaned_text == "Hello."
    assert row.mode == "balanced"
    assert row.profile == "notes"
    assert row.duration_seconds == 2.5
    assert row.model == "base"
    assert row.created_at

    with sqlite3.connect(db_path) as conn:
        columns = [info[1] for info in conn.execute("PRAGMA table_info(dictations)")]

    assert columns[:9] == [
        "id",
        "created_at",
        "app_name",
        "raw_text",
        "cleaned_text",
        "mode",
        "profile",
        "duration_seconds",
        "model",
    ]
    assert {"app_exe", "app_group", "style", "intensity", "language", "asr_model",
            "llm_model", "llm_decision", "timings_json", "edits_json", "audio_path"} <= set(columns)


def test_default_history_path_uses_local_appdata(tmp_path, monkeypatch):
    from saydraft.history import default_history_path

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_history_path() == tmp_path / "Saydraft" / "history.db"


def test_audio_retry_preserves_original_and_does_not_inflate_dictation_totals(tmp_path):
    import json

    from saydraft.history import DictationHistoryStore, HistoryEntry

    store = DictationHistoryStore(tmp_path / "history.db")
    source_id = store.append(HistoryEntry("Notepad", "original words", "Original words.", "raw", "notes",
                                          8, "primary", audio_path="local.wav"))
    original = store.list_recent()[0]
    store.append(HistoryEntry("Notepad", "more recovered words", "More recovered words.", "raw", "notes",
                              8, "whisper-large-v3-turbo", audio_path="local.wav",
                              timings_json='{"stt": 1.5}', edits_json=json.dumps([
                                  {"type": "asr_retry", "source_history_id": source_id}])))
    assert store.list_recent()[1] == original
    with sqlite3.connect(store.db_path) as connection:
        totals = connection.execute("SELECT sum(dictations),sum(words),sum(audio_seconds),sum(processing_seconds) FROM stats_daily").fetchone()
    assert totals == (1, 2, 8.0, 1.5)
