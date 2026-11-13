import json
import os
import types
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from saydraft.ui.history_page import add_word_to_dictionary_action


def qt_modules():
    from PySide6 import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return types.SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)


def settle_history(window, *, timeout=8):
    application = qt_modules().QtWidgets.QApplication.instance()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if not window.loading and not window._exporting and not window.jobs.export_busy:
            return
        time.sleep(.003)
    raise AssertionError("Owned History work did not finish")


class FakeClipboard:
    def __init__(self):
        self.texts = []

    def setText(self, text):
        self.texts.append(text)


def build_history(tmp_path):
    from saydraft.history import DictationHistoryStore, HistoryEntry

    store = DictationHistoryStore(tmp_path / "history.db")
    store.append(
        HistoryEntry(
            app_name="Notepad",
            raw_text="um older raw",
            cleaned_text="Older clean.",
            mode="balanced",
            profile="notes",
            duration_seconds=2.0,
            model="base",
        )
    )
    store.append(
        HistoryEntry(
            app_name="Code",
            raw_text="newer raw Qwen Turbo",
            cleaned_text="Newer clean Qwen Turbo.",
            mode="aggressive",
            profile="code/comments",
            duration_seconds=1.2,
            model="small",
        )
    )
    return store


def test_history_add_word_to_dictionary_action_learns_selected_word(tmp_path):
    glossary_path = tmp_path / "glossary.json"

    learned = add_word_to_dictionary_action("  Qwen Turbo  ", glossary_path=glossary_path)

    assert learned == "Qwen Turbo"
    saved = json.loads(glossary_path.read_text(encoding="utf-8"))
    assert saved["user_terms"] == ["Qwen Turbo"]


def test_history_add_word_to_dictionary_action_returns_none_for_blank_selection(tmp_path):
    glossary_path = tmp_path / "glossary.json"

    learned = add_word_to_dictionary_action("   ", glossary_path=glossary_path)

    assert learned is None
    assert not glossary_path.exists()


def test_history_window_loads_reverse_chron_and_toggles_raw_clean(tmp_path):
    from saydraft.ui.history_page import HistoryPage

    store = build_history(tmp_path)
    window = HistoryPage(qt_modules=qt_modules(), store=store, glossary_path=tmp_path / "glossary.json")
    settle_history(window)

    assert window.list_widget.count() == 2
    assert "Newer clean" in window.list_widget.item(0).text()
    assert "Older clean" in window.list_widget.item(1).text()
    assert window.detail_editor.toPlainText() == "Newer clean Qwen Turbo."
    assert "Code" in window.metadata_label.text()

    window.raw_toggle.setChecked(True)
    assert window.detail_editor.toPlainText() == "newer raw Qwen Turbo"
    window.raw_toggle.setChecked(False)
    assert window.detail_editor.toPlainText() == "Newer clean Qwen Turbo."


def test_history_window_search_filters_rows(tmp_path):
    from saydraft.ui.history_page import HistoryPage

    store = build_history(tmp_path)
    window = HistoryPage(qt_modules=qt_modules(), store=store, glossary_path=tmp_path / "glossary.json")

    window.search_edit.setText("older")
    settle_history(window)

    assert window.list_widget.count() == 1
    assert "Older clean" in window.list_widget.item(0).text()
    assert window.detail_editor.toPlainText() == "Older clean."


def test_history_retry_requires_saved_audio_and_selects_new_result_for_review(tmp_path):
    from saydraft.history import HistoryEntry
    from saydraft.ui.history_page import HistoryPage

    store = build_history(tmp_path)
    calls = []
    window = HistoryPage(qt_modules=qt_modules(), store=store,
                           retry_callback=lambda row: calls.append(row.id) or True)
    settle_history(window)
    assert not window.retry_button.isEnabled()
    source = store.append(HistoryEntry("Notepad", "", "", "raw", "notes", 1, "primary", audio_path="local.wav"))
    window.refresh()
    settle_history(window)
    window._select_id(source)
    settle_history(window)
    assert window.retry_button.isEnabled()
    assert "Recording saved" in window.list_widget.currentItem().text()
    assert window.retry_current_audio()
    assert calls == [source] and not window.retry_button.isEnabled()
    result = store.append(HistoryEntry("Notepad", "recovered", "Recovered.", "raw", "notes", 1,
                                      "whisper-large-v3-turbo", audio_path="local.wav", edits_json=json.dumps([
                                          {"type": "asr_retry", "source_history_id": source}])))
    window.finish_retry(result)
    settle_history(window)
    assert window.current_row().id == result
    assert window.detail_editor.toPlainText() == "Recovered."
    assert f"Retry of #{source}" in window.metadata_label.text()
    assert window.retry_button.isEnabled()


def test_history_window_rejected_reinsertion_does_not_claim_it_was_queued(tmp_path):
    from saydraft.ui.history_page import HistoryPage
    qt_modules()
    window = HistoryPage(store=build_history(tmp_path), reinsert_callback=lambda *args: False)
    settle_history(window)
    try:
        assert not window.reinsert_current_text()
        assert "busy" in window.status_label.text() and "Queued" not in window.status_label.text()
    finally:
        window.close()


def test_history_window_copy_reinsert_and_add_dictionary_actions(tmp_path):
    from saydraft.ui.history_page import HistoryPage

    store = build_history(tmp_path)
    clipboard = FakeClipboard()
    reinserts = []
    glossary_path = tmp_path / "glossary.json"
    window = HistoryPage(
        qt_modules=qt_modules(),
        store=store,
        clipboard=clipboard,
        reinsert_callback=lambda text, row: reinserts.append((text, row.id)),
        glossary_path=glossary_path,
    )
    settle_history(window)

    window.copy_current_text()
    window.reinsert_current_text()
    window.detail_editor.selectAll()
    learned = window.add_selection_to_dictionary()

    assert clipboard.texts == ["Newer clean Qwen Turbo."]
    assert reinserts == [("Newer clean Qwen Turbo.", 2)]
    assert learned == "Newer clean Qwen Turbo."
    saved = json.loads(glossary_path.read_text(encoding="utf-8"))
    assert saved["user_terms"] == ["Newer clean Qwen Turbo."]
