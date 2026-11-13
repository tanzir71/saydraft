from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from saydraft.config import load_config
from saydraft.history import HistoryEntry
from tests.test_history_window import FakeClipboard, build_history, settle_history
from tests.test_settings_window import FakeAutoStartManager, qt_modules, write_config


@pytest.fixture
def subject(tmp_path):
    from saydraft.ui.hub import HubWindow

    qt = qt_modules()
    config = write_config(tmp_path)
    store, clipboard = build_history(tmp_path), FakeClipboard()
    applied = []
    hub = HubWindow(settings_options=dict(config_path=config, snippets_path=tmp_path / "snippets.txt",
        autostart_manager=FakeAutoStartManager(), on_config_applied=applied.append),
        history_options=dict(store=store, clipboard=clipboard, glossary_path=tmp_path / "glossary.json"),
        shortcut=lambda: "Ctrl+Win", model=lambda: "Parakeet v3", tier=lambda: "standard")
    try:
        yield SimpleNamespace(hub=hub, qt=qt, config=config, store=store, clipboard=clipboard,
            applied=applied, directory=tmp_path)
    finally:
        hub.close()
        hub.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def test_hub_has_one_window_and_seven_pages_with_real_existing_controls(subject):
    hub, qt = subject.hub, subject.qt
    assert [hub.navigation.item(i).text() for i in range(7)] == [
        "Home", "History", "Dictionary", "Snippets", "Style", "Notes", "Settings"]
    assert hub.size() == qt.QtCore.QSize(1080, 720)
    assert hub.minimumSize() == qt.QtCore.QSize(880, 600)
    assert hub.isWindow() and not hub.settings_page.isWindow() and not hub.history_page.isWindow()
    assert hub.settings_page.dictionary_editor.window() is hub
    assert hub.settings_page.snippets_editor.window() is hub
    assert hub.settings_page.speech_hotkey_edit.window() is hub
    for name in ("Dictionary", "Snippets", "Style"):
        assert hub.page_widgets[name].parentWidget() is hub.pages
        assert name not in [hub.settings_page.tabs.tabText(i) for i in range(hub.settings_page.tabs.count())]
    for name in ("Home", "History", "Dictionary", "Snippets", "Style", "Notes", "Settings", "Home"):
        hub.show_page(name)
        assert hub.pages.currentWidget() is hub.page_widgets[name]
        assert hub.footer.isHidden() == (name not in ("Dictionary", "Snippets", "Style", "Settings"))
    assert all(not hub.navigation.item(i).icon().isNull() for i in range(7))
    sections = hub.settings_page.section_combo
    assert [sections.itemText(i) for i in range(sections.count())] == [
        "General", "Shortcuts", "Languages", "Cleanup", "Models", "Performance", "Labs", "Microphone", "Privacy", "About"]
    sections.setCurrentIndex(sections.findText("Models"))
    tabs = hub.settings_page.tabs
    assert tabs.tabText(tabs.currentIndex()) == "Models"
    hub.settings_page.show_tab("Privacy")
    assert sections.currentText() == "Privacy"


def test_shared_save_preserves_all_fields_and_applies_edits_from_separate_pages(subject):
    from saydraft.ui.settings_page import SettingsPage

    hub = subject.hub
    reference = SettingsPage(config_path=subject.config, snippets_path=subject.directory / "snippets.txt",
        autostart_manager=FakeAutoStartManager())
    try:
        assert hub.settings_page._collect_config() == reference._collect_config()
    finally:
        reference.close()
        reference.deleteLater()
    hub.show_page("Dictionary")
    hub.settings_page.learn_corrections_checkbox.setChecked(True)
    hub.settings_page.auto_add_dictionary_checkbox.setChecked(True)
    hub.show_page("Snippets")
    hub.settings_page.snippets_editor.setPlainText("sig=With thanks\n")
    hub.show_page("Settings", tab="Privacy")
    hub.settings_page.retain_audio_checkbox.setChecked(True)
    hub.settings_page.speech_hotkey_edit.setText("f8")
    expected = hub.settings_page._collect_config()
    hub.save_button.click()
    assert subject.applied == [expected]
    assert load_config(config_path=subject.config) == expected
    assert hub.settings_page.snippet_store.read().editable == {"sig": "With thanks"}
    assert (subject.directory / "snippets.txt").read_text("utf-8") == "addr=123 Main\n"


def test_save_failure_is_visible_and_keeps_staged_data_and_config(subject):
    hub = subject.hub
    previous = subject.config.read_bytes()
    hub.settings_page.speech_hotkey_edit.setText("f10")  # Conflicts with History-only capture.
    hub.show_page("Style")
    hub.save_button.click()
    assert not subject.applied and subject.config.read_bytes() == previous
    assert "conflict" in hub.settings_page.status_label.text().lower()
    hub.show_page("Settings")
    assert hub.settings_page.speech_hotkey_edit.text() == "f10"


def test_home_uses_current_shortcut_models_and_exactly_last_five_entries(subject):
    hub = subject.hub
    for i in range(6):
        subject.store.append(HistoryEntry("Notes", f"public {i}", f"Public fixture {i}.", "raw", "notes", 2, "v3"))
    hub.home_page.shortcut = lambda: "f8"
    hub.home_page.refresh()
    assert hub.home_page.recent.count() == 5
    assert "fixture 5" in hub.home_page.recent.item(0).text()
    assert "fixture 1" in hub.home_page.recent.item(4).text()
    assert hub.home_page.keycaps.itemAt(0).widget().text() == "F8"
    assert hub.home_page.model_label.text() == "Parakeet v3 · Standard tier"
    target = hub.home_page.recent.item(2)
    hub.history_page.search_edit.setText("older")
    hub.home_page.recent.itemActivated.emit(target)
    settle_history(hub.history_page)
    assert hub.pages.currentWidget() is hub.history_view
    assert hub.history_page.current_row().id == target.data(subject.qt.QtCore.Qt.UserRole)
    assert not hub.history_page.search_edit.text()


def test_home_offline_chip_opens_privacy_and_does_not_claim_an_uninstalled_guard(subject, monkeypatch):
    from saydraft.privacy.netguard import NetworkGuard

    hub = subject.hub
    monkeypatch.setattr(NetworkGuard, "is_installed", lambda: True)
    hub.home_page.refresh()
    assert hub.home_page.offline_button.text() == "Offline"
    assert not hub.home_page.offline_button.icon().isNull()
    hub.home_page.offline_button.click()
    tabs = hub.settings_page.tabs
    assert hub.pages.currentWidget() is hub.settings_page and tabs.tabText(tabs.currentIndex()) == "Privacy"
    assert hub.settings_page.privacy_status.text() == "Offline mode active"
    monkeypatch.setattr(NetworkGuard, "is_installed", lambda: False)
    hub.refresh()
    assert hub.home_page.offline_button.text() == "Offline policy unavailable"


def test_home_empty_and_incomplete_measurements_are_honest(subject):
    from saydraft.history import WeeklyStats

    home = subject.hub.home_page
    home.now = lambda: datetime(2026, 11, 13, 9)
    stats = WeeklyStats(datetime(2026, 11, 9).date(), datetime(2026, 11, 15).date(), 0, 0, 0)
    subject.store.weekly_stats = lambda **kwargs: stats
    subject.store.list_recent = lambda **kwargs: []
    home.refresh()
    assert home.greeting.text() == "Good morning."
    assert home.values["words"].text() == "0" and home.values["wpm"].text() == "—"
    assert home.values["saved"].text() == "0 sec" and not home.empty.isHidden()
    stats = replace(stats, words=120, audio_seconds=30, duration_complete=False)
    home.refresh()
    assert home.values["words"].text() == "120"
    assert home.values["wpm"].text() == "—" and home.values["saved"].text() == "—"
    assert "incomplete" in home.measurement_note.text()


def test_home_refresh_keeps_unchanged_keycaps_and_hides_retired_labels_before_deferred_deletion(subject):
    home = subject.hub.home_page
    previous = [home.keycaps.itemAt(i).widget() for i in range(home.keycaps.count())]
    home.refresh()
    assert [home.keycaps.itemAt(i).widget() for i in range(home.keycaps.count())] == previous
    home.shortcut = lambda: "F8"
    home.refresh()
    assert all(widget.isHidden() for widget in previous)
    # No event-loop/deferred-delete processing is needed to avoid an overlay.
    visible = [label for label in home.findChildren(subject.qt.QtWidgets.QLabel)
        if label.property("keycap") and not label.isHidden()]
    assert [label.text() for label in visible] == ["F8"]


def test_hub_close_pauses_all_download_owners_without_discarding_pages(subject, monkeypatch):
    hub = subject.hub
    paused = []
    for name in ("model_picker", "labs_page", "cleanup_picker"):
        monkeypatch.setattr(getattr(hub.settings_page, name), "pause", lambda name=name: paused.append(name))
    hub.settings_page._vad_download_task = SimpleNamespace(pause=lambda: paused.append("vad"))
    page = hub.page_widgets["Dictionary"]
    hub.close()
    assert paused == ["model_picker", "labs_page", "cleanup_picker", "vad"]
    assert hub.page_widgets["Dictionary"] is page
    hub.show_page("History")
    settle_history(hub.history_page)
    assert not hub.history_page.jobs.closed and hub.history_page.current_row() is not None


def test_real_app_routes_history_settings_and_home_to_the_same_owned_hub(subject):
    from saydraft.app import SaydraftApp, create_worker_signals
    from saydraft.ui.hub import HubWindow

    qt = subject.qt
    application = qt.QtWidgets.QApplication.instance()
    created = []

    def create(**options):
        options["settings_options"].update(autostart_manager=FakeAutoStartManager(),
            snippets_path=subject.directory / "snippets.txt")
        hub = HubWindow(**options)
        created.append(hub)
        return hub

    app = SaydraftApp(qt_modules=qt, config_path=subject.config, hub_window_factory=create)
    app.qt_app = application
    app.signals = create_worker_signals(qt.QtCore)
    app.controller = SimpleNamespace(history_store=lambda: subject.store, clipboard=lambda: subject.clipboard,
        model_label=lambda: "Public model", hotkey_hint=lambda: "Ctrl+Win")
    try:
        app._show_history()
        hub = app.hub_window
        assert hub.pages.currentWidget() is hub.history_view
        app._show_settings()
        assert app.hub_window is hub and hub.pages.currentWidget() is hub.settings_page
        assert hub.history_page.glossary_path == hub.settings_page.glossary_path
        app._fix_bar_error("models")
        assert hub.settings_page.tabs.tabText(hub.settings_page.tabs.currentIndex()) == "Models"
        hub.close()
        app._show_hub()
        assert app.hub_window is hub and hub.pages.currentWidget() is hub.home_page
        assert len(created) == 1 and not hub.history_page.isWindow() and not hub.settings_page.isWindow()
    finally:
        app.signals.blockSignals(True)
        if created:
            application.aboutToQuit.disconnect(created[0].close)
            created[0].close()
            created[0].deleteLater()
        app.signals.deleteLater()
        application.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_hub_keeps_its_minimum_size_with_larger_text_and_all_controls_reachable(subject, mode):
    from saydraft.ui.fonts import install_bundled_fonts
    from saydraft.ui.theme.controller import ThemeController

    hub, qt = subject.hub, subject.qt
    application = qt.QtWidgets.QApplication.instance()
    original_font, original_sheet = application.font(), application.styleSheet()
    install_bundled_fonts(application)
    font = application.font()
    font.setPixelSize(22)
    application.setFont(font)
    theme = ThemeController(application, mode=mode)
    try:
        theme.start()
        hub.resize(880, 600)
        hub.show()
        for name in ("Home", "History", "Dictionary", "Snippets", "Style", "Notes", "Settings"):
            hub.show_page(name)
            application.processEvents()
            assert hub.size() == qt.QtCore.QSize(880, 600)
        hub.show_page("History")
        settle_history(hub.history_page)
        application.processEvents()
        assert hub.history_view.horizontalScrollBar().maximum() == 0
        hub.show_page("Dictionary")
        application.processEvents()
        dictionary_scroll = hub.page_widgets["Dictionary"]
        assert dictionary_scroll.horizontalScrollBar().maximum() == 0
        dictionary_scroll.ensureWidgetVisible(hub.settings_page.dictionary_page.reload_button)
        application.processEvents()
        control = hub.settings_page.dictionary_page.reload_button
        point = control.mapTo(dictionary_scroll.viewport(), qt.QtCore.QPoint())
        assert 0 <= point.y() and point.y() + control.height() <= dictionary_scroll.viewport().height()
        hub.show_page("Snippets")
        page = hub.settings_page.snippets_page
        page.test_toggle.setChecked(True)
        page.test_input.setPlainText("addr")
        assert page.test_expansion()
        application.processEvents()
        assert hub.size() == qt.QtCore.QSize(880, 600)
        snippet_scroll = hub.page_widgets["Snippets"]
        assert snippet_scroll.horizontalScrollBar().maximum() == 0
        for control in (page.test_button, page.reload_button):
            snippet_scroll.ensureWidgetVisible(control)
            application.processEvents()
            point = control.mapTo(snippet_scroll.viewport(), qt.QtCore.QPoint())
            assert 0 <= point.y() and point.y() + control.height() <= snippet_scroll.viewport().height()
        hub.show_page("Settings", tab="Shortcuts")
        application.processEvents()
        scroll = hub.settings_page.tabs.currentWidget()
        scroll.ensureWidgetVisible(hub.settings_page.tap_lock_spin)
        application.processEvents()
        point = hub.settings_page.tap_lock_spin.mapTo(scroll.viewport(), qt.QtCore.QPoint())
        assert 0 <= point.y() and point.y() + hub.settings_page.tap_lock_spin.height() <= scroll.viewport().height()
        save_bottom = hub.save_button.mapTo(hub, qt.QtCore.QPoint(0, hub.save_button.height()))
        assert save_bottom.y() <= hub.height()
    finally:
        theme.close()
        application.setFont(original_font)
        application.setStyleSheet(original_sheet)
