import pytest

from saydraft.config import default_config, load_config, sanitize_config, save_config
from saydraft.core.preview import preview_eligibility
from saydraft.models.tiers import effective_tier, tier_defaults


@pytest.mark.parametrize("selected,measured,wanted", [
    ("auto", None, "pending"), ("auto", "standard", "standard"),
    ("lite", "pro", "lite"), ("standard", None, "standard"), ("pro", "lite", "pro"),
])
def test_saved_override_is_separate_from_measurement(tmp_path, selected, measured, wanted):
    cfg = default_config()
    cfg["app"]["tier"] = selected
    path = tmp_path / "config.json"
    save_config(cfg, path)
    report = {"assessment": {"tier": measured}}
    assert effective_tier(load_config(config_path=path), report) == wanted
    assert report == {"assessment": {"tier": measured}}


@pytest.mark.parametrize("value", ["unknown", "Pro", "", 1, None, [], {}], ids=["unknown", "case", "empty", "int", "null", "list", "object"])
def test_invalid_tier_preferences_fall_back_to_auto(value):
    cfg = default_config()
    cfg["app"]["tier"] = value
    assert sanitize_config(cfg)["app"]["tier"] == "auto"
    assert sanitize_config({})["app"]["tier"] == "auto"


def test_feature_gate_uses_saved_tier_and_keeps_language_policy():
    cfg = default_config()
    cfg["app"]["tier"] = "pro"
    assert preview_eligibility(cfg, None) is None
    cfg["stt"]["pinned_languages"] = ["bn"]
    assert preview_eligibility(cfg, None) == "english_only"
    cfg["app"]["tier"] = "lite"
    assert preview_eligibility(cfg, {"assessment": {"tier": "pro"}}) == "needs_pro"


def test_pending_tier_cannot_apply_defaults():
    with pytest.raises(ValueError, match="performance check"):
        tier_defaults("pending")


@pytest.mark.parametrize("tier,model,cleanup", [
    ("lite", "whisper-base", None),
    ("standard", "parakeet-tdt-0-6b-v3-int8", "qwen35-08b-q4-k-m"),
    ("pro", "parakeet-tdt-0-6b-v3-int8", "qwen35-2b-q4-k-m"),
])
def test_defaults_stage_without_saving_or_downloading(tmp_path, monkeypatch, tier, model, cleanup):
    from tests.test_settings_window import make_window
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    window, path, _ = make_window(tmp_path)
    before = path.read_bytes()
    window.model_picker.callback = lambda *args: pytest.fail("Unexpected speech download")
    window.cleanup_picker.callback = lambda *args: pytest.fail("Unexpected cleanup download")
    window.tier_combo.setCurrentIndex(window.tier_combo.findData(tier))
    # Selecting a tier alone preserves individual model choices.
    assert window.model_combo.currentData() == default_config()["stt"]["model_id"]
    assert not window.llm_enabled_checkbox.isChecked()
    window._stage_tier_defaults()
    assert window.model_combo.currentData() == model
    assert window.llm_enabled_checkbox.isChecked() == (cleanup is not None)
    assert window.cleanup_picker.combo.currentData() == cleanup
    assert window.languages_page.routing.isChecked() == (tier != "lite")
    assert path.read_bytes() == before
    assert window.apply_changes()
    assert load_config(config_path=path)["app"]["tier"] == tier
    assert window.labs_page.allowed == (tier == "pro")
    if cleanup:
        assert cleanup in load_config(config_path=path)["llm"]["model_path"]
    window.close()


def test_tier_defaults_preserve_pins_and_route_shared_multilingual_model(tmp_path):
    from tests.test_settings_window import make_window
    window, _, _ = make_window(tmp_path, overrides={"stt": {"pinned_languages": ["bn", "ar"]}})
    window.tier_combo.setCurrentIndex(window.tier_combo.findData("pro"))
    window._stage_tier_defaults()
    cfg = window._collect_config()
    assert cfg["stt"]["pinned_languages"] == ["bn", "ar"]
    assert window.model_combo.currentData() == "whisper-large-v3-turbo"
    assert not cfg["labs"]["live_preview"] and not window.labs_page.allowed
    window.close()


def test_refreshing_measurement_preserves_override_and_custom_choices(tmp_path):
    from tests.test_settings_window import make_window
    window, _, _ = make_window(tmp_path, overrides={"app": {"tier": "standard"}, "llm": {"model_path": "custom.gguf"}})
    window.refresh_labs({"assessment": {"tier": "pro"}, "vulkan": True})
    assert window.tier_picker.selected_tier() == "standard"
    assert window.llm_path_edit.text() == "custom.gguf"
    assert "Performance check: Pro" in window.tier_picker.note.text()
    assert "Tier defaults: Standard" in window.cleanup_picker.recommendation.text()
    window.close()


def test_reopening_manual_tier_keeps_processor_choices_until_defaults_are_requested():
    from saydraft.ui.cleanup_picker import CleanupPicker
    from tests.test_settings_window import qt_modules
    qt_modules()
    cfg = default_config()
    cfg["app"]["tier"] = "pro"
    picker = CleanupPicker(cfg, report={"assessment": {"tier": "pro"}, "vulkan": True})
    assert picker.combo.currentData() is None and picker.backend.currentData() == "cpu"
    assert "Tier defaults: Pro" in picker.recommendation.text()
    assert not cfg["llm"]["enabled"]
    picker.close()


def test_model_notices_keep_their_height_when_storage_status_wraps(tmp_path):
    from PySide6 import QtWidgets
    from saydraft.ui.hub import HubWindow
    from saydraft.ui.fonts import install_bundled_fonts
    from saydraft.ui.theme import install_theme
    from tests.test_history_window import build_history, FakeClipboard, settle_history
    from tests.test_settings_window import qt_modules, write_config, FakeAutoStartManager
    from tests.test_model_storage import make_subject, snapshot
    from tests.test_model_storage_ui import settle

    qt = qt_modules()
    application = qt.QtWidgets.QApplication.instance()
    original_font, original_stylesheet = application.font(), application.styleSheet()
    install_bundled_fonts(application)
    theme = install_theme(application, mode="light")
    config, fixture = write_config(tmp_path), make_subject(tmp_path)
    hub = HubWindow(settings_options=dict(config_path=config, snippets_path=tmp_path / "snippets.txt",
        autostart_manager=FakeAutoStartManager(), model_inventory_provider=lambda: snapshot(fixture)),
        history_options=dict(store=build_history(tmp_path), clipboard=FakeClipboard()))
    try:
        hub.show_page("Settings", tab="Models")
        hub.resize(880, 600)
        hub.show()
        settle_history(hub.history_page)
        page = hub.settings_page
        settle(page.model_storage)
        for pixels in (16, 22):
            font = qt.QtWidgets.QApplication.font()
            font.setPixelSize(pixels)
            qt.QtWidgets.QApplication.setFont(font)
            page.tier_combo.setCurrentIndex(page.tier_combo.findData("pro"))
            for blocked in (False, True):
                page.config["llm"]["model_path"] = str(fixture[2] / "weights.gguf") if blocked else "elsewhere.gguf"
                page.model_storage.selection_changed()
                for _ in range(4):
                    qt.QtWidgets.QApplication.processEvents()
                scroll = page.tabs.currentWidget()
                assert scroll.horizontalScrollBar().maximum() == 0, [
                    (type(widget).__name__, getattr(widget, "text", lambda: "")(), widget.minimumSizeHint().width())
                    for widget in scroll.widget().findChildren(QtWidgets.QWidget)
                    if widget.minimumSizeHint().width() > scroll.viewport().width()]
                assert all(label.height() >= label.heightForWidth(label.width())
                           for label in scroll.findChildren(QtWidgets.QLabel) if label.wordWrap())
    finally:
        theme.close()
        application.setStyleSheet(original_stylesheet)
        qt.QtWidgets.QApplication.setFont(original_font)
        hub.close()
        hub.history_page.close()
        hub.settings_page.microphone_page.close()
