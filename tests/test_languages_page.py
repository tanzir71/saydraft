from PySide6 import QtWidgets

from saydraft.config import default_config
from saydraft.ui.languages_page import LanguagesPage


def make_page():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return app, LanguagesPage(default_config())


def set_pin(combo, code):
    combo.setCurrentIndex(combo.findData(code))


def test_auto_and_up_to_three_pins_persist_with_single_language_hint():
    app, page = make_page()
    cfg = default_config()
    page.apply_to(cfg)
    assert cfg["stt"]["pinned_languages"] == [] and cfg["stt"]["language"] == "auto"
    assert not page.combos[1].isEnabled()
    set_pin(page.combos[0], "bn")
    page.apply_to(cfg)
    assert cfg["stt"]["language"] == "bn"
    assert "optional shared" in page.note.text()
    set_pin(page.combos[1], "ar")
    set_pin(page.combos[2], "en")
    page.apply_to(cfg)
    assert cfg["stt"]["pinned_languages"] == ["bn", "ar", "en"]
    assert cfg["stt"]["language"] == "auto"
    set_pin(page.combos[0], None)
    page.apply_to(cfg)
    assert cfg["stt"]["pinned_languages"] == []


def test_manual_model_mode_and_english_max_are_explicit():
    app, page = make_page()
    set_pin(page.combos[0], "en")
    page.english_max.setChecked(True)
    assert "Parakeet v2" in page.note.text()
    page.routing.setChecked(False)
    cfg = default_config()
    page.apply_to(cfg)
    assert cfg["stt"]["routing_enabled"] is False
    assert not page.english_max.isEnabled()
