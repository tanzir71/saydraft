"""Qt-only keyboard/accessibility regressions with public, disposable data."""

import json
import sys
from types import SimpleNamespace

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from saydraft.config import default_config, save_config
from saydraft.history import DictationHistoryStore, HistoryEntry
from saydraft.models.storage import Inventory
from saydraft.ui.hub import HubWindow
from saydraft.ui.theme import install_theme


APP = None
PAGES = ("Home", "History", "Dictionary", "Snippets", "Style", "Notes")
SECTIONS = ("General", "Shortcuts", "Languages", "Cleanup", "Models", "Performance",
            "Labs", "Microphone", "Privacy", "About")


class Hints(QtCore.QObject):
    colorSchemeChanged = QtCore.Signal(object)
    contrastPreferenceChanged = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.contrast = QtCore.Qt.ContrastPreference.NoPreference

    def accessibility(self):
        return self

    def colorScheme(self):
        return QtCore.Qt.ColorScheme.Light

    def contrastPreference(self):
        return self.contrast


def forbidden(*args, **kwargs):
    raise AssertionError("Owner, device, download and external ports are barred")


@pytest.fixture
def owned_hub(tmp_path, monkeypatch):
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app = APP
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    original_font, original_sheet = QtGui.QFont(app.font()), app.styleSheet()
    qt_errors = []
    monkeypatch.setattr(sys, "excepthook", lambda kind, error, trace: qt_errors.append((kind.__name__, str(error))))
    monkeypatch.setattr(QtWidgets.QApplication, "clipboard", forbidden)
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", forbidden)
    monkeypatch.setattr("saydraft.ui.settings_page.wispr_running", lambda: False)
    monkeypatch.setattr("saydraft.models.storage.storage_roots", lambda: ())
    monkeypatch.setattr("saydraft.ui.onboarding_models.inspect_speech_package",
                        lambda _: {"state": "missing", "missing": []})
    config = default_config()
    config["dictation"].update(glossary_path=str(tmp_path / "glossary.json"),
                               app_profiles_path=str(tmp_path / "profiles.json"))
    save_config(config, tmp_path / "config.json")
    (tmp_path / "glossary.json").write_text(json.dumps({"user_terms": ["Saydraft"]}), encoding="utf-8")
    (tmp_path / "profiles.json").write_text("[]", encoding="utf-8")
    (tmp_path / "snippets.txt").write_text("office address=123 Example Road\n", encoding="utf-8")
    store = DictationHistoryStore(tmp_path / "history.db")
    store.append(HistoryEntry(app_name="Public fixture", raw_text="um hello world",
                              cleaned_text="Hello world.", mode="balanced", profile="notes",
                              duration_seconds=2.0, model="public-fixture"))
    hub = HubWindow(settings_options=dict(config_path=tmp_path / "config.json",
        snippets_path=tmp_path / "snippets.txt", autostart_manager=SimpleNamespace(
            is_enabled=lambda: False, set_enabled=forbidden), microphone_devices_provider=forbidden,
        microphone_start_callback=forbidden, microphone_stop_callback=lambda: None,
        model_download_callback=forbidden, vad_download_callback=forbidden,
        hardware_benchmark_callback=forbidden, preview_download_callback=forbidden,
        cleanup_download_callback=forbidden, cleanup_runtime_download_callback=forbidden,
        style_preview_callback=forbidden, audio_cleanup_callback=forbidden,
        firewall_status_provider=forbidden, model_remove_callback=forbidden,
        model_inventory_provider=lambda: Inventory(models=(), roots=())),
        history_options=dict(store=store, clipboard=SimpleNamespace(setText=forbidden)))
    hints = Hints()
    controllers = []

    def theme(mode, px):
        font = QtGui.QFont(app.font())
        font.setPixelSize(px)
        app.setFont(font)
        hints.contrast = (QtCore.Qt.ContrastPreference.HighContrast if mode == "high-contrast"
                          else QtCore.Qt.ContrastPreference.NoPreference)
        controller = install_theme(app, mode="light" if mode == "high-contrast" else mode, style_hints=hints)
        if controller not in controllers:
            controllers.append(controller)
        controller.set_mode("light" if mode == "high-contrast" else mode)
        controller.refresh()
        app.processEvents()
        return controller

    def settle():
        # Only owned SQLite readers and queued Qt events; no desktop event source.
        for _ in range(100):
            app.processEvents()
            if not hub.history_page.loading:
                break
            QtTest.QTest.qWait(5)
        assert not hub.history_page.loading

    hub.resize(880, 600)
    for page in (hub.settings_page.dictionary_page, hub.settings_page.snippets_page):
        page.table.selectRow(0)
    hub.show()
    settle()
    yield SimpleNamespace(app=app, hub=hub, theme=theme, settle=settle, hints=hints)
    hub.close()
    hub.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()
    for controller in controllers:
        controller.close()
    app.setStyleSheet(original_sheet)
    app.setFont(original_font)
    assert not qt_errors, qt_errors


def accessible_name(widget):
    interface = QtGui.QAccessible.queryAccessibleInterface(widget)
    return interface.text(QtGui.QAccessible.Name) if interface else ""


def walk_tabs(subject, *, backwards=False):
    hub, app = subject.hub, subject.app
    hub.navigation.setFocus()
    app.processEvents()
    visited = []
    for _ in range(160):
        focus = app.focusWidget()
        assert focus is not None and focus.window() is hub
        assert focus.isVisibleTo(hub) and focus.isEnabled()
        assert accessible_name(focus).strip(), type(focus).__name__
        visited.append(focus)
        QtTest.QTest.keyClick(focus, QtCore.Qt.Key_Tab,
            QtCore.Qt.ShiftModifier if backwards else QtCore.Qt.NoModifier)
        app.processEvents()
        if app.focusWidget() is hub.navigation:
            return visited
    pytest.fail("Tab did not return to Hub navigation: " + str([accessible_name(w) for w in visited[-8:]]))


@pytest.mark.parametrize("mode", ["light", "dark", "high-contrast"])
@pytest.mark.parametrize("px", [16, 32])
def test_all_hub_pages_have_named_forward_and_reverse_tab_cycles(owned_hub, mode, px):
    subject, hub = owned_hub, owned_hub.hub
    subject.theme(mode, px)
    for name, section in [(name, None) for name in PAGES] + [("Settings", name) for name in SECTIONS]:
        hub.show_page(name, tab=section)
        subject.settle()
        editors = [w for w in hub.findChildren(QtWidgets.QPlainTextEdit) if not w.isReadOnly()]
        texts = [editor.toPlainText() for editor in editors]
        for backwards in [False, True]:
            visited = walk_tabs(subject, backwards=backwards)
            if name in ("Dictionary", "Snippets", "Style", "Settings"):
                assert hub.save_button in visited
            for label in hub.findChildren(QtWidgets.QLabel):
                if label.isVisibleTo(hub) and label.isEnabled() and label.openExternalLinks() and '<a ' in label.text():
                    assert label in visited, label.text()
        assert [editor.toPlainText() for editor in editors] == texts


@pytest.mark.parametrize("mode", ["light", "dark", "high-contrast"])
def test_navigation_refits_live_font_changes_and_native_scrollbars(owned_hub, mode):
    subject, hub = owned_hub, owned_hub.hub
    for px in [16, 32, 16]:
        subject.theme(mode, px)
        for width, height in [(880, 600), (1080, 720)]:
            hub.resize(width, height)
            subject.app.processEvents()
            nav = hub.navigation
            assert nav.horizontalScrollBar().maximum() == 0
            assert nav.viewport().width() >= nav.sizeHintForColumn(0)
            assert not any(nav.item(index).icon().isNull() for index in range(nav.count()))
            for index in range(nav.count()):
                nav.setCurrentRow(index)
                nav.setFocus()
                QtTest.QTest.keyClick(nav, QtCore.Qt.Key_Down if index == 0 else QtCore.Qt.Key_Up)
                assert nav.currentRow() == (1 if index == 0 else index - 1)
                assert subject.app.focusWidget() is nav
                assert hub.pages.currentIndex() == nav.currentRow()


@pytest.mark.parametrize("page", ["Dictionary", "Snippets", "Style", "Cleanup"])
def test_multiline_form_editors_leave_with_tab_without_changing_drafts(owned_hub, page):
    subject, hub = owned_hub, owned_hub.hub
    subject.theme("dark", 32)
    hub.show_page("Settings" if page == "Cleanup" else page, tab=page if page == "Cleanup" else None)
    if page in ("Dictionary", "Snippets"):
        child = getattr(hub.settings_page, page.lower() + "_page")
        child.advanced.setChecked(True)
        if page == "Snippets":
            child.test_toggle.setChecked(True)
    subject.app.processEvents()
    editors = [w for w in hub.findChildren(QtWidgets.QPlainTextEdit)
               if w.isVisibleTo(hub) and not w.isReadOnly()]
    assert editors
    for editor in editors:
        before = editor.toPlainText()
        editor.setFocus()
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Tab)
        assert subject.app.focusWidget() is not editor
        assert editor.toPlainText() == before
        editor.setFocus()
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Tab, QtCore.Qt.ShiftModifier)
        assert subject.app.focusWidget() is not editor
        assert editor.toPlainText() == before
    assert hub.save_button in walk_tabs(subject)


def test_home_and_general_settings_reflow_without_horizontal_scrolling(owned_hub):
    subject, hub = owned_hub, owned_hub.hub
    subject.theme("light", 32)
    for page, section in [("Home", None), ("Settings", "General"), ("Settings", "Shortcuts")]:
        hub.show_page(page, tab=section)
        subject.app.processEvents()
        scroll = hub.home_page if page == "Home" else hub.settings_page.tabs.currentWidget()
        assert scroll.horizontalScrollBar().maximum() == 0
        assert hub.width() == 880
    hub.show_page("Home")
    for index in range(hub.home_page.keycaps.count()):
        keycap = hub.home_page.keycaps.itemAt(index).widget()
        assert keycap.height() <= keycap.sizeHint().height()


def test_high_contrast_retires_brand_sheet_and_preserves_large_font(owned_hub):
    subject, hub = owned_hub, owned_hub.hub
    controller = subject.theme("dark", 32)
    assert subject.app.styleSheet()
    subject.hints.contrast = QtCore.Qt.ContrastPreference.HighContrast
    subject.hints.contrastPreferenceChanged.emit(subject.hints.contrast)
    subject.app.processEvents()
    assert controller.current == "high-contrast"
    assert subject.app.styleSheet() == controller.original_sheet
    assert subject.app.font().pixelSize() == 32
    hub.setFocus()
    assert subject.app.focusWidget() is hub.navigation
    assert hub.home_page.offline_button in walk_tabs(subject)
