import threading
from types import SimpleNamespace as NS

import pytest
from PySide6 import QtCore, QtTest

from saydraft.config import default_config
from saydraft.core.style_preview import StylePreviewResult
from saydraft.dictation.glossary import Glossary
from saydraft.insert._clipboard_win32 import PRIVACY_FORMATS
from saydraft.ui.styles_page import GROUP_LABELS, StylesPage
from tests.test_settings_window import make_window, qt_modules


def page_fixture():
    app = qt_modules().QtWidgets.QApplication.instance()
    cfg, profiles, calls = default_config(), [], []
    page = None
    def config():
        value = {**cfg, "dictation": dict(cfg["dictation"])}
        page.apply_to(value)
        return value
    page = StylesPage(cfg, config_provider=config, profiles_provider=lambda: profiles,
        glossary_provider=lambda: Glossary(), callback=lambda value: calls.append(value) or True)
    page.refresh()
    return app, page, cfg, profiles, calls


def test_matrix_roundtrip_keeps_inheritance_and_legacy_mode_changes(tmp_path):
    window, path, _ = make_window(tmp_path)
    page = window.styles_page
    assert len(page.tones) == 7 and not page.tones["code"].isEnabled()
    window.mode_combo.setCurrentText("aggressive")
    assert window.apply_changes() and window.config["dictation"]["styles"] == {}
    page.tones["messages"].setCurrentIndex(page.tones["messages"].findData("very_casual"))
    page.levels["messages"].setCurrentIndex(page.levels["messages"].findData(2))
    assert window.apply_changes()
    assert window.config["dictation"]["styles"] == {"messages": {"tone": "very_casual", "intensity": 2}}
    page.close()
    window.close()


def test_live_rules_preview_matches_every_group_tone_and_level():
    from saydraft.eval import load_eval_corpus
    expected = {(c.app_group, c.tone, c.intensity): c.expected for c in load_eval_corpus() if c.id.startswith("style-v1-")}
    _app, page, _cfg, _profiles, _calls = page_fixture()
    try:
        for group in GROUP_LABELS:
            page.group.setCurrentIndex(page.group.findData(group))
            for tone in ("formal", "casual", "very_casual"):
                page.tones[group].setCurrentIndex(page.tones[group].findData(tone))
                for level in range(1, 5):
                    page.levels[group].setCurrentIndex(page.levels[group].findData(level))
                    page.refresh()
                    context = page._request().context
                    assert (context.tone, context.intensity) == (tone, level)
                    assert page.after.toPlainText() == expected[group, tone, level]
    finally:
        page.close()


def test_app_override_changes_context_without_reading_an_application():
    _app, page, _cfg, profiles, _calls = page_fixture()
    try:
        profiles.append({"exe": "slack.exe", "tone": "very_casual", "intensity": 2})
        page.exe.setText("slack.exe")
        page.refresh()
        assert page.after.toPlainText() == "like hello hello world"
        assert "Work chat" in page.status.text()
    finally:
        page.close()


def test_visible_row_edit_updates_its_live_preview_after_debounce():
    app, page, _cfg, _profiles, _calls = page_fixture()
    try:
        page.show()
        app.processEvents()
        page.before.setPlainText("um hello hello")
        page.tones["email"].setCurrentIndex(page.tones["email"].findData("formal"))
        assert page.timer.isActive() and page.group.currentData() == "email"
        QtTest.QTest.qWait(240)
        assert page.after.toPlainText() == "Hello."
        page.hide()
        assert not page.timer.isActive()
    finally:
        page.close()


@pytest.mark.parametrize("mode,level", [("raw", 3), ("balanced", 1)])
def test_raw_and_verbatim_preview_disable_prose_ai(mode, level):
    _app, page, cfg, _profiles, _calls = page_fixture()
    try:
        cfg["dictation"]["mode"] = mode
        page.levels["messages"].setCurrentIndex(page.levels["messages"].findData(level))
        page.refresh()
        assert "um like hello hello world" in page.after.toPlainText()
        assert not page.ai_button.isEnabled()
    finally:
        page.close()


def test_stale_ai_results_hidden_page_and_other_draft_changes_do_not_replace_current_output():
    app, page, cfg, _profiles, calls = page_fixture()
    try:
        page.preview_ai()
        first = calls[-1]
        page.before.setPlainText("new text")
        page.refresh()
        page.accept_result(StylePreviewResult(first, "OBSOLETE", "accepted"))
        assert "OBSOLETE" not in page.after.toPlainText()
        page.preview_ai()
        second = calls[-1]
        cfg["llm"]["enabled"] = True
        page.accept_result(StylePreviewResult(second, "WRONG MODEL", "accepted"))
        assert "WRONG MODEL" not in page.after.toPlainText()
        page.show()
        app.processEvents()
        page.preview_ai()
        page.hide()
        page.accept_result(StylePreviewResult(calls[-1], "HIDDEN", "accepted"))
        assert "HIDDEN" not in page.after.toPlainText()
    finally:
        page.close()


def test_candidate_display_is_plain_private_and_input_is_never_silently_truncated():
    _app, page, _cfg, _profiles, calls = page_fixture()
    try:
        page.before.setPlainText("<b>private</b>")
        page.before.selectAll()
        mime = page.before.createMimeDataFromSelection()
        assert all(mime.hasFormat(f'application/x-qt-windows-mime;value="{name}"') for name in PRIVACY_FORMATS)
        assert mime.text() == "<b>private</b>"
        assert all(bytes(mime.data(f'application/x-qt-windows-mime;value="{name}"')) == bytes(4) for name in PRIVACY_FORMATS)
        page.preview_ai()
        page.accept_result(StylePreviewResult(calls[-1], "<b>candidate</b>", "accepted"))
        assert page.after.toPlainText() == "<b>candidate</b>"
        page.before.setPlainText("x" * 4097)
        page.refresh()
        assert len(page.before.toPlainText()) == 4097 and not page.after.toPlainText()
        assert not page.ai_button.isEnabled()
    finally:
        page.close()



def test_app_wires_current_ai_callback_and_queues_worker_result_to_the_page(tmp_path):
    from saydraft.app import SaydraftApp, create_worker_signals
    app, page, _cfg, _profiles, calls = page_fixture()
    subject = SaydraftApp(qt_modules=NS(QtCore=QtCore), config_path=tmp_path / "config.json")
    def callback(value):
        calls.append(value)
        return True
    subject.controller = NS(preview_style=callback, style_glossary=lambda: Glossary())
    subject.signals = create_worker_signals(QtCore)
    def window(**kwargs):
        assert kwargs["config_path"] == subject.config_path
        assert kwargs["style_preview_callback"] is callback
        page.callback = kwargs["style_preview_callback"]
        return NS(styles_page=page, show=lambda: None, raise_=lambda: None, activateWindow=lambda: None)
    subject.settings_window_factory = window
    from tests.test_qt_app_shell import fake_hub_factory
    subject.hub_window_factory = fake_hub_factory("Settings")
    try:
        subject._show_settings()
        page.preview_ai()
        result = StylePreviewResult(calls[-1], "Queued public fixture", "accepted")
        thread = threading.Thread(target=lambda: subject.signals.style_preview_finished.emit(result))
        thread.start()
        thread.join(timeout=2)
        assert "Queued public fixture" not in page.after.toPlainText()
        app.processEvents()
        assert page.after.toPlainText() == "Queued public fixture"
    finally:
        page.close()
