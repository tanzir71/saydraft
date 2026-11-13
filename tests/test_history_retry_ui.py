import json

import pytest

from saydraft.asr.retry import RetryOptions
from saydraft.asr.router import ALL_LANGUAGES
from saydraft.asr.model_ids import DEFAULT_MODEL
from saydraft.history import HistoryEntry
from saydraft.ui.history_page import HistoryPage
from saydraft.ui.history_retry import HistoryRetryDialog
from tests.test_history_window import build_history, qt_modules, settle_history, FakeClipboard


@pytest.fixture
def subject(tmp_path):
    qt = qt_modules()
    store = build_history(tmp_path)
    source = store.append(HistoryEntry("Public editor", "Original", "Original.", "balanced", "notes", 1,
        DEFAULT_MODEL, audio_path="public-fixture.wav"))
    calls, cancels = [], []
    page = HistoryPage(store=store, clipboard=FakeClipboard(),
        retry_callback=lambda row, options: calls.append((row.id, options)) or True,
        cancel_retry_callback=lambda: cancels.append(True) or True,
        retry_models_provider=lambda: [(DEFAULT_MODEL,"Default speech"),(ALL_LANGUAGES,"All languages")])
    settle_history(page)
    try:
        yield page, qt, store, source, calls, cancels
    finally:
        page.close()


def test_dialog_defaults_to_all_languages_and_explains_review_only_scope(subject):
    page, qt, _, _, _, _ = subject
    dialog = HistoryRetryDialog(page.retry_models_provider(), source_model=DEFAULT_MODEL, parent=page)
    try:
        assert dialog.options() == RetryOptions(ALL_LANGUAGES,"current")
        dialog.cleanup.setCurrentIndex(dialog.cleanup.findData("off"))
        dialog.model.setCurrentIndex(dialog.model.findData(DEFAULT_MODEL))
        assert dialog.options() == RetryOptions(DEFAULT_MODEL,"off")
        text = " ".join(label.text() for label in dialog.findChildren(qt.QtWidgets.QLabel))
        assert "original stays unchanged" in text and "this retry only" in text
        assert dialog.buttons.button(qt.QtWidgets.QDialogButtonBox.Ok).isEnabled()
    finally:
        dialog.close()


def test_no_models_disables_retry_and_cancel_does_not_queue(subject, monkeypatch):
    page, qt, _, _, calls, _ = subject
    page.retry_models_provider = lambda: []
    def cancel(dialog):
        assert not dialog.buttons.button(qt.QtWidgets.QDialogButtonBox.Ok).isEnabled()
        return qt.QtWidgets.QDialog.Rejected
    monkeypatch.setattr(HistoryRetryDialog,"exec",cancel)
    assert not page.choose_retry() and not calls
    assert page._retry_source_id is None


def test_dialog_freezes_source_and_passes_explicit_options_even_when_selection_changes(subject, monkeypatch):
    page, qt, _, source, calls, _ = subject
    def choose(dialog):
        dialog.model.setCurrentIndex(dialog.model.findData(DEFAULT_MODEL))
        dialog.cleanup.setCurrentIndex(dialog.cleanup.findData("off"))
        page.list_widget.setCurrentRow(1)
        settle_history(page)
        return qt.QtWidgets.QDialog.Accepted
    monkeypatch.setattr(HistoryRetryDialog,"exec",choose)
    assert page.choose_retry()
    assert calls == [(source,RetryOptions(DEFAULT_MODEL,"off"))]
    assert page.retry_button.text() == "Cancel retry" and page.retry_button.isEnabled()


def test_cancel_remains_available_while_a_different_query_is_loading(subject):
    page, _, _, _, _, cancels = subject
    assert page.retry_current_audio(RetryOptions())
    page.search_edit.setText("no matching saved entry")
    assert page.retry_button.isEnabled()
    assert page.choose_retry() and cancels == [True]
    assert not page.retry_button.isEnabled() and not page.cancel_retry()
    page.finish_retry(0)
    settle_history(page)
    assert "cancelled" in page.status_label.text() and page.current_row() is None


def test_real_history_updated_then_finished_signal_order_selects_the_new_review(subject):
    page, _, store, source, _, _ = subject
    assert page.retry_current_audio(RetryOptions())
    result = store.append(HistoryEntry("Public editor", "Recovered", "Recovered.", "balanced", "notes", 1,
        ALL_LANGUAGES, audio_path="public-fixture.wav", edits_json=json.dumps([{"type":"asr_retry","source_history_id":source}])))
    # The application's history_updated receiver refreshes before retry_finished.
    page.refresh()
    assert page.current_row() is None
    page.finish_retry(result)
    settle_history(page)
    assert page.current_row().id == result and "Retry of" in page.metadata_label.text()


def test_success_does_not_move_the_selection_after_user_browses_away(subject):
    page, _, store, source, _, _ = subject
    assert page.retry_current_audio(RetryOptions())
    page.list_widget.setCurrentRow(1)
    settle_history(page)
    selected = page.current_row().id
    result = store.append(HistoryEntry("Public editor", "Recovered", "Recovered.", "balanced", "notes", 1,
        ALL_LANGUAGES, audio_path="public-fixture.wav", edits_json=json.dumps([{"type":"asr_retry","source_history_id":source}])))
    page.refresh()
    page.finish_retry(result)
    settle_history(page)
    assert page.current_row().id == selected


@pytest.mark.parametrize("raises", [False,True])
def test_rejected_or_failed_callback_retires_retry_without_exposing_error(subject, raises):
    page, _, _, _, _, _ = subject
    def callback(*args):
        if raises:
            raise RuntimeError("private provider details")
        return False
    page.retry_callback = callback
    assert not page.retry_current_audio(RetryOptions())
    assert page._retry_source_id is None and page.retry_button.isEnabled()
    assert "private" not in page.status_label.text()


def test_real_controller_forwards_options_and_cancel_to_the_core():
    from types import SimpleNamespace
    from saydraft.app import WorkerController
    calls = []
    controller = WorkerController.__new__(WorkerController)
    controller.core = SimpleNamespace(retry_history=lambda row, options: calls.append((row, options)) or True,
        cancel_history_retry=lambda: calls.append("cancel") or True)
    options = RetryOptions(DEFAULT_MODEL,"on")
    assert controller.retry_history_audio("public-row", options) and controller.cancel_history_retry()
    assert calls == [("public-row", options), "cancel"]


def test_large_text_dialog_keeps_actions_visible_and_content_scrolls(subject):
    page, qt, _, _, _, _ = subject
    app = qt.QtWidgets.QApplication.instance()
    previous = app.font()
    from saydraft.ui.fonts import install_bundled_fonts
    install_bundled_fonts(app)
    font = qt.QtGui.QFont(app.font())
    font.setPixelSize(22)
    dialog = None
    try:
        app.setFont(font)
        dialog = HistoryRetryDialog(page.retry_models_provider(), parent=page)
        dialog.setFont(font)
        dialog.resize(480,360)
        dialog.show()
        app.processEvents()
        app.processEvents()
        assert dialog.size() == qt.QtCore.QSize(480,360)
        assert dialog.scroll.horizontalScrollBar().maximum() == 0
        assert dialog.scroll.verticalScrollBar().maximum() > 0
        assert all(label.height() >= label.heightForWidth(label.width())
            for label in dialog.scroll.findChildren(qt.QtWidgets.QLabel))
        assert dialog.buttons.isVisible() and dialog.buttons.geometry().bottom() < dialog.height()
        dialog.scroll.ensureWidgetVisible(dialog.cleanup)
        app.processEvents()
        assert dialog.cleanup.isVisible()
    finally:
        if dialog is not None:
            dialog.close()
        app.setFont(previous)
