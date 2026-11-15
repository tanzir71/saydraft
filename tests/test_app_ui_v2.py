"""Behavioral acceptance for the v2 presentation's staged state and native roles."""
from pathlib import Path
from PySide6 import QtCore, QtGui
from tests.test_hub import subject as _hub_subject

subject = _hub_subject


def settle(subject):
    subject.qt.QtWidgets.QApplication.processEvents()
    subject.hub.settings_page.draft_state.refresh()


def test_clean_pages_hide_savebar_and_discard_restores_without_writing(subject):
    hub = subject.hub
    s = hub.settings_page
    before = Path(subject.config).read_bytes()
    for page in hub.page_widgets:
        hub.show_page(page)
        assert s.draft_state.refresh() == 0
        assert hub.footer.isHidden()
    hub.show_page("Settings", tab="General")
    s.show_bar_checkbox.setChecked(not s.show_bar_checkbox.isChecked())
    settle(subject)
    assert s.draft_state.count == 1 and not hub.footer.isHidden()
    assert s.draft_state.discard()
    settle(subject)
    assert s.draft_state.count == 0 and hub.footer.isHidden()
    assert Path(subject.config).read_bytes() == before
    assert subject.applied == []


def test_search_and_row_selection_do_not_stage_preferences(subject):
    hub = subject.hub
    s = hub.settings_page
    s.dictionary_page.search.setText("Saydraft")
    s.snippets_page.search.setText("addr")
    s.languages_page.tiles.search.setText("Arabic")
    s.dictionary_page.table.setCurrentIndex(s.dictionary_page.model.index(0,0))
    s.snippets_page.table.setCurrentIndex(s.snippets_page.model.index(0,0))
    settle(subject)
    assert s.draft_state.count == 0


def test_discard_restores_dirty_documents_and_synchronized_segments(subject):
    s = subject.hub.settings_page
    before = s.dictionary_editor.toPlainText()
    mode = s.mode_combo.currentIndex()
    s.dictionary_editor.setPlainText('{"user_terms":["Changed"],"replacements":{},"protected_terms":[]}')
    s.snippets_page.trigger_edit.setText("unfinished trigger")
    s.mode_combo.setCurrentIndex((mode+1)%s.mode_combo.count())
    settle(subject)
    assert s.draft_state.count >= 3
    assert s.draft_state.discard()
    settle(subject)
    assert s.dictionary_editor.toPlainText() == before
    assert s.snippets_page.trigger_edit.text() == ""
    assert s.mode_combo.currentIndex() == mode
    assert s.draft_state.count == 0
    from saydraft.ui.kit import Segmented
    assert all(segment.currentIndex() == segment.source_combo.currentIndex()
               for segment in s.findChildren(Segmented) if segment.source_combo is not None)


def test_discard_waits_for_download_owner_instead_of_switching_model(subject):
    s = subject.hub.settings_page
    s.model_combo.setCurrentIndex((s.model_combo.currentIndex()+1)%s.model_combo.count())
    selected = s.model_combo.currentData()
    s.model_picker.task = object()
    try:
        assert not s.draft_state.discard()
        assert s.model_combo.currentData() == selected
        assert "downloads" in s.status_label.text()
    finally:
        s.model_picker.task = None


def test_language_tiles_keep_three_pin_limit_and_do_not_download(subject):
    page = subject.hub.settings_page.languages_page
    page.tiles._set_pins([])
    items = {page.tiles.list.item(i).data(QtCore.Qt.UserRole):page.tiles.list.item(i)
             for i in range(page.tiles.list.count())}
    for code in ("ar","bn","ja","th"):
        items[code].setCheckState(QtCore.Qt.Checked)
    assert page.pins() == ("ar","bn","ja")
    assert items["th"].checkState() == QtCore.Qt.Unchecked
    assert "Three" in page.tiles.status.text()
    assert subject.hub.settings_page.model_picker.task is None
    settle(subject)
    assert subject.hub.settings_page.draft_state.count > 0
    page.tiles._set_pins([])
    assert page.pins() == () and page.combos[0].currentData() is None


def test_native_toggle_radio_roles_and_level_gain_do_not_claim_clipping(subject):
    from saydraft.ui.kit import Toggle, Segmented, LevelMeter
    toggle = Toggle("Test toggle")
    segment = Segmented(["One","Two"],name="Test segment")
    meter = LevelMeter()
    assert QtGui.QAccessible.queryAccessibleInterface(toggle).role() == QtGui.QAccessible.CheckBox
    assert all(QtGui.QAccessible.queryAccessibleInterface(button).role() == QtGui.QAccessible.RadioButton for button in segment.buttons)
    meter.set_rms(.05)
    assert meter.value() == 100 and not meter.clipping
    meter.set_rms(.99)
    assert meter.clipping
    meter.set_rms(float("nan"))
    assert meter.value() == 0 and not meter.clipping
    for widget in (toggle,segment,meter):
        widget.deleteLater()


def test_discard_resynchronizes_radio_model_choice_and_translation_display(subject):
    s = subject.hub.settings_page
    original = s.model_combo.currentIndex()
    s.model_combo.setCurrentIndex((original+1)%s.model_combo.count())
    s.styles_page.translation_language.setCurrentIndex(s.styles_page.translation_language.findData("es"))
    assert s.styles_page.translation_targets
    assert s.draft_state.discard()
    assert s.model_combo.currentIndex() == original
    assert all(button.isChecked() == (index == original) for button,index,_card in s.model_picker.choices.buttons)
    group = s.styles_page.translation_group.currentData()
    assert s.styles_page.translation_language.currentData() == s.styles_page.translation_targets.get(group, "")
    assert s.draft_state.refresh() == 0


def test_shortcut_change_stages_canonical_binding_and_discard_closes_stale_editor(subject):
    hub = subject.hub
    s = hub.settings_page
    hub.show_page("Settings",tab="Shortcuts")
    hub.show()
    s.shortcut_buttons["Hold to dictate"].click()
    original = s.speech_hotkey_edit.text()
    assert not s.shortcut_learner.isHidden()
    assert not s.shortcut_learner.learn_button.isEnabled()  # No native capture callback in this fixture.
    s.shortcut_learner.primary.setText("f8")
    assert s.speech_hotkey_edit.text() == "f8"
    assert s.draft_state.refresh() > 0
    assert s.draft_state.discard()
    assert s.speech_hotkey_edit.text() == original
    assert s.shortcut_learner.isHidden() and s.shortcut_target is None
    assert subject.applied == []
