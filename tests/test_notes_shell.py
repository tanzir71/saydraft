"""Native-action -> queued app signal -> real owned Hub/Scratchpad/SQLite."""

from types import SimpleNamespace

from saydraft.config import load_config
from saydraft.core.hotkey_service import HotkeyService
from saydraft.hotkeys.chords import Transition
from tests.test_history_window import build_history, FakeClipboard, settle_history
from tests.test_native_recording import factory
from tests.test_settings_window import write_config, FakeAutoStartManager, qt_modules
from tests.test_scratchpad import settle


def test_queued_actions_persist_to_hub_notes_and_diff_then_quit_after_latest_save(tmp_path):
    from PySide6 import QtTest
    from saydraft.app import SaydraftApp, create_worker_signals
    from saydraft.ui.settings_page import SettingsPage
    qt = qt_modules()
    qt.QtTest = QtTest
    path = write_config(tmp_path)
    history, clipboard = build_history(tmp_path), FakeClipboard()
    create, owners = factory()
    app = SaydraftApp(config_path=path,
        settings_window_factory=lambda **options: SettingsPage(**options,
            autostart_manager=FakeAutoStartManager(), snippets_path=tmp_path / 'snippets.txt'))
    app.qt_app = qt.QtWidgets.QApplication.instance()
    app.config = load_config(config_path=path)
    app.signals = create_worker_signals(qt.QtCore)
    service = HotkeyService(app.config, start=lambda: None, stop=lambda: None,
        cancel=lambda: None, save=lambda: None, notify=lambda message: None,
        native_factory=create, ui_request=app.signals.utility_requested.emit)
    app.controller = SimpleNamespace(history_store=lambda: history, clipboard=lambda: clipboard,
        is_current_ui_request=service.is_current_ui_request)
    app.signals.utility_requested.connect(app._utility_requested, qt.QtCore.Qt.QueuedConnection)
    service.start()
    try:
        before = history.search_page().total
        owners[-1].action(Transition('scratchpad', 'release'), 1)
        settle(qt, lambda: app.scratchpad_window is not None and app.scratchpad_window.editor.isEnabled())
        pad = app.scratchpad_window
        pad.editor.setPlainText('Saved from the native action route. বাংলা العربية')
        app._show_hub('Notes')
        settle(qt, lambda: not pad.draft.snapshot().dirty and bool(app.hub_window.notes_page.rows))
        assert app.hub_window.notes_page.rows[0].preview == pad.editor.toPlainText()
        assert history.search_page().total == before
        owners[-1].action(Transition('view_diff', 'release'), 2)
        settle(qt, lambda: app.hub_window.navigation.currentItem().text() == 'History')
        settle_history(app.history_window)
        assert app.history_window.current_row() is not None and app.history_window.diff_toggle.isChecked()
        service.revoke_requests()
        app.hub_window.show_page('Home')
        app.signals.utility_requested.emit(SimpleNamespace(action='view_diff', ticket=object()))
        qt.QtWidgets.QApplication.processEvents()
        assert app.hub_window.navigation.currentItem().text() == 'Home'
        calls = []
        app.qt_app = SimpleNamespace(quit=lambda: calls.append(pad.draft.store.active().body))
        pad.editor.setPlainText('Last edit at Quit')
        assert app._request_quit()
        settle(qt, lambda: bool(calls))
        assert calls == ['Last edit at Quit']
    finally:
        service.stop()
        if app.scratchpad_window is not None:
            app.scratchpad_window.shutdown()
            app.scratchpad_window.draft.executor.shutdown(wait=True)
            app.scratchpad_window.hide()
            app.scratchpad_window.deleteLater()
        if app.hub_window is not None:
            app.hub_window.notes_page.jobs.close()
            app.hub_window.notes_page.jobs.executor.shutdown(wait=True)
            app.hub_window.history_page.close()
            app.hub_window.close()
            app.hub_window.deleteLater()
        app.signals.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)
