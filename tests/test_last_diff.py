"""Last-diff opens the latest global completed entry despite a prior filter."""

from saydraft.history import HistoryEntry
from saydraft.ui.history_page import HistoryPage
from tests.test_history_window import FakeClipboard, build_history, qt_modules, settle_history


def test_last_diff_clears_search_and_pagination_and_uses_plain_text_diff(tmp_path):
    qt_modules()
    store = build_history(tmp_path)
    window = HistoryPage(store=store, clipboard=FakeClipboard(), glossary_path=tmp_path / 'words.json', limit=1)
    try:
        settle_history(window)
        window.search_edit.setText('meeting')
        settle_history(window)
        row_id = store.append(HistoryEntry('Fixture', 'um <tag> words', '<tag> words.', 'balanced', 'general', 2, 'fixture'))
        window.show_last_diff()
        settle_history(window)
        assert window.search_edit.text() == ''
        assert window.current_row().id == row_id and window.diff_toggle.isChecked()
        assert window._page.offset == 0
        assert '<tag>' in window.detail_editor.toPlainText()
    finally:
        window.close()


def test_last_diff_on_empty_history_shows_empty_state(tmp_path):
    from saydraft.history import DictationHistoryStore
    qt_modules()
    window = HistoryPage(store=DictationHistoryStore(tmp_path / 'history.db'), clipboard=FakeClipboard(),
        glossary_path=tmp_path / 'words.json')
    try:
        window.show_last_diff()
        settle_history(window)
        assert window.current_row() is None and not window.detail_editor.toPlainText()
        assert window.diff_toggle.isChecked()
    finally:
        window.close()
