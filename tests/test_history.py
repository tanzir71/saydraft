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
