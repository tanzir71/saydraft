import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from saydraft.dictionary.store import add_term, entry_source, read_dictionary, undo_learning
from tests.test_settings_window import make_window, qt_modules


@pytest.fixture
def subject(tmp_path):
    qt = qt_modules()
    window, config, _ = make_window(tmp_path)
    try:
        yield SimpleNamespace(window=window, page=window.dictionary_page,
            path=tmp_path / "glossary.json", config=config, directory=tmp_path, qt=qt)
    finally:
        window.close()
        window.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def rows(page):
    return [tuple(page.model.data(page.model.index(i, j)) for j in range(page.model.columnCount()))
        for i in range(page.model.rowCount())]


def select(page, term):
    index = next(i for i, values in enumerate(rows(page)) if values[0] == term)
    page.table.setCurrentIndex(page.model.index(index, 0))


def choose(page, category):
    page.kind.setCurrentIndex(page.kind.findData(category))


def incoming(subject, data):
    path = subject.directory / "import.json"
    path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    return path


@pytest.mark.parametrize('category,term,value', [
    ('user_terms', 'Krezel', None), ('protected_terms', 'Krezle', None),
    ('replacements', 'sea sharp', 'C#'),
])
def test_pending_form_preview_matches_save_without_mutating_staged_or_saved_state(subject, category, term, value):
    page = subject.page
    choose(page, category)
    page.term_edit.setText(term)
    if value is not None:
        page.value_edit.setText(value)
    before, revision = subject.path.read_bytes(), page.snapshot.revision
    editor, claims, imports = page.json_editor.toPlainText(), page.manual_claims, page.imports
    preview = page.preview_data()
    assert page.json_editor.toPlainText() == editor
    assert page.manual_claims == claims and page.imports == imports
    assert page.snapshot.revision == revision and subject.path.read_bytes() == before
    assert subject.window.apply_changes()
    assert read_dictionary(subject.path).editable == preview


def test_previewing_pending_rename_of_imported_entry_does_not_claim_or_drop_source(subject):
    page = subject.page
    assert page.import_file(incoming(subject, {'user_terms': ['Krezel']}))
    select(page, 'Krezel')
    page.term_edit.setText('Krezle')
    imports, claims = page.imports, page.manual_claims
    preview = page.preview_data()
    assert preview['user_terms'] == ['Saydraft', 'Krezle']
    assert page.imports == imports and page.manual_claims == claims
    assert subject.window.apply_changes()
    assert read_dictionary(subject.path).editable == preview
    assert entry_source(read_dictionary(subject.path), 'user_terms', 'Krezle') == 'Manual'


def test_structured_edits_are_staged_across_categories_and_shared_save_commits_the_last_form(subject):
    p, w = subject.page, subject.window
    original = subject.path.read_bytes()
    assert rows(p) == [("Saydraft", "Manual")]
    assert not p.dirty and not p.advanced.isChecked()
    p.term_edit.setText("  Café   Society  ")
    assert p.add_entry()
    select(p, "Café Society")
    p.term_edit.setText("Café Club")
    assert p.update_entry()
    choose(p, "protected_terms")
    p.term_edit.setText("C#")
    assert p.add_entry()
    choose(p, "replacements")
    p.term_edit.setText("sea sharp")
    p.value_edit.setText("C#")
    # Save includes the pending form, even if Add was not pressed.
    assert subject.path.read_bytes() == original and p.dirty
    assert w.apply_changes()
    saved = read_dictionary(subject.path)
    assert saved.editable == {"user_terms": ["Saydraft", "Café Club"],
        "protected_terms": ["C#"], "replacements": {"sea sharp": "C#"}}
    assert not p.dirty
    select(p, "sea sharp")
    p.term_edit.setText("see sharp")
    p.value_edit.setText(r"C:\new\bin\1")
    assert p.update_entry()
    assert rows(p) == [("see sharp", r"C:\new\bin\1", "Manual")]
    select(p, "see sharp")
    assert p.remove_entry() and not rows(p)
    assert read_dictionary(subject.path).editable["replacements"] == {"sea sharp": "C#"}
    assert w.apply_changes() and not read_dictionary(subject.path).editable["replacements"]


def test_duplicate_unicode_terms_and_empty_forms_do_not_replace_existing_entries(subject):
    p = subject.page
    p.term_edit.setText("Café")
    assert p.add_entry()
    p.term_edit.setText("CAFE\u0301")
    assert not p.add_entry() and "already" in p.status_label.text()
    assert rows(p) == [("Saydraft", "Manual"), ("Café", "Manual")]
    p.term_edit.clear()
    assert not p.add_entry() and "Enter a term" in p.status_label.text()
    assert subject.window.apply_changes()
    assert read_dictionary(subject.path).editable["user_terms"] == ["Saydraft", "Café"]


def test_source_chips_and_make_manual_preserve_or_revoke_real_learning_undo(subject):
    p, w = subject.page, subject.window
    receipt = add_term(subject.path, "Kubernetes", learned=True)
    assert w.refresh_dictionary()
    assert rows(p) == [("Saydraft", "Manual"), ("Kubernetes", "Learned")]
    select(p, "Kubernetes")
    assert p.manual_button.isEnabled()
    # Re-saving an untouched selection must not claim a learned word manually.
    assert w.apply_changes()
    assert undo_learning(subject.path, receipt)
    receipt = add_term(subject.path, "Kubernetes", learned=True)
    assert w.refresh_dictionary()
    select(p, "Kubernetes")
    p.manual_button.click()
    assert rows(p)[1] == ("Kubernetes", "Manual") and p.dirty
    assert w.apply_changes()
    assert entry_source(read_dictionary(subject.path), "user_terms", "Kubernetes") == "Manual"
    assert not undo_learning(subject.path, receipt)


def test_import_merge_search_sources_and_portable_export_do_not_apply_before_save(subject):
    p, w = subject.page, subject.window
    path = incoming(subject, {"user_terms": ["SAYDRAFT", "বাংলা", "العربية"],
        "protected_terms": ["C#"], "replacements": {"sea sharp": "C#"}, "owner": {"extra": 1}})
    original = subject.path.read_bytes()
    assert p.import_file(path) and subject.path.read_bytes() == original
    assert "4 new entries; 1 already present" in p.status_label.text()
    p.search.setText("imported")
    assert rows(p) == [("বাংলা", "Imported"), ("العربية", "Imported")]
    p.search.clear()
    choose(p, "replacements")
    p.search.setText("C#")
    assert rows(p) == [("sea sharp", "C#", "Imported")]
    exported = subject.directory / "dictionary.copy"
    assert p.export_file(exported)
    assert json.loads(exported.read_text("utf-8")) == p.data()
    assert subject.path.read_bytes() == original
    assert not p.export_file(subject.path)
    assert "another file" in p.status_label.text()
    assert w.apply_changes()
    saved = read_dictionary(subject.path)
    assert entry_source(saved, "user_terms", "বাংলা") == "Imported"
    assert entry_source(saved, "replacements", "sea sharp", "C#") == "Imported"
    assert saved.editable["owner"] == {"extra": 1} and not p.dirty
    # A target conflict is reported and keeps the existing replacement.
    assert p.import_file(incoming(subject, {"replacements": {"SEA SHARP": "Wrong"}}))
    assert "1 existing replacements kept" in p.status_label.text()
    assert p.data()["replacements"] == {"sea sharp": "C#"}


def test_background_learning_refreshes_clean_rows_but_keeps_typed_forms_and_refuses_stale_save(subject):
    p, w = subject.page, subject.window
    add_term(subject.path, "GitHub", learned=True)
    w.autostart_checkbox.setChecked(True)
    assert w.refresh_dictionary()
    assert rows(p)[-1] == ("GitHub", "Learned") and w.autostart_checkbox.isChecked()
    p.term_edit.setText("A pending form")
    receipt = add_term(subject.path, "Kubernetes", learned=True)
    original_config = subject.config.read_bytes()
    assert not w.refresh_dictionary()
    assert p.term_edit.text() == "A pending form" and "staged edits are kept" in p.status_label.text()
    assert not w.apply_changes()
    assert subject.config.read_bytes() == original_config
    assert "A pending form" in p.data()["user_terms"]
    assert read_dictionary(subject.path).editable["user_terms"] == ["Saydraft", "GitHub", "Kubernetes"]
    p.reload_button.click()
    assert not p.dirty and "A pending form" not in p.data()["user_terms"]
    assert undo_learning(subject.path, receipt)
    assert w.refresh_dictionary() and "Kubernetes" not in p.data()["user_terms"]


def test_stale_import_remains_staged_and_cannot_overwrite_new_learning(subject):
    p, w = subject.page, subject.window
    assert p.import_file(incoming(subject, {"user_terms": ["Django"]}))
    receipt = add_term(subject.path, "Kubernetes", learned=True)
    assert not w.refresh_dictionary() and not w.apply_changes()
    assert rows(p)[-1] == ("Django", "Imported")
    assert undo_learning(subject.path, receipt)
    assert read_dictionary(subject.path).editable["user_terms"] == ["Saydraft"]


@pytest.mark.parametrize("raw", ['{broken', '{"user_terms":[1]}', '[' * 1200])
def test_invalid_advanced_json_is_visible_and_refuses_save_without_losing_saved_data(subject, raw):
    old_dictionary, old_config = subject.path.read_bytes(), subject.config.read_bytes()
    p = subject.page
    p.json_editor.setPlainText(raw)
    assert p.advanced.isChecked() and not p.add_button.isEnabled()
    assert not subject.window.apply_changes()
    assert subject.path.read_bytes() == old_dictionary and subject.config.read_bytes() == old_config
    assert p.json_editor.toPlainText() == raw
    p.reload_button.click()
    assert rows(p) == [("Saydraft", "Manual")] and not p.dirty


def test_invalid_missing_and_over_budget_imports_keep_the_current_draft(subject):
    p = subject.page
    p.term_edit.setText("Draft")
    assert p.add_entry()
    before = p.json_editor.toPlainText()
    assert not p.import_file(subject.directory / "missing.json")
    assert not p.import_file(incoming(subject, {"user_terms": [42]}))
    assert not p.import_file(incoming(subject, {"user_terms": ["x" * (2 * 1024 * 1024)]}))
    assert p.json_editor.toPlainText() == before and rows(p)[-1] == ("Draft", "Manual")


@pytest.mark.parametrize("raw", [b'\xff', b' ' * (4 * 1024 * 1024 + 1)], ids=["encoding", "oversized"])
def test_unreadable_saved_dictionary_opens_safely_and_requires_repair_before_saving(subject, raw):
    from saydraft.ui.settings_page import SettingsPage
    from tests.test_settings_window import FakeAutoStartManager

    original = subject.path.read_bytes()
    subject.path.write_bytes(raw)
    window = SettingsPage(config_path=subject.config, snippets_path=subject.directory / "snippets.txt",
        autostart_manager=FakeAutoStartManager())
    try:
        p = window.dictionary_page
        assert p.snapshot is None and not p.add_button.isEnabled() and not p.export_button.isEnabled()
        assert not window.apply_changes() and subject.path.read_bytes() == raw
        assert len(p.json_editor.toPlainText()) < 500
        subject.path.write_bytes(original)
        p.reload_button.click()
        assert rows(p) == [("Saydraft", "Manual")] and window.apply_changes()
    finally:
        window.close()
        window.deleteLater()


def test_export_failure_is_plain_text_and_preserves_existing_destination(subject, monkeypatch):
    destination = subject.directory / "copy.json"
    destination.write_bytes(b"owner bytes")
    def fail(*args):
        raise OSError("<b>fixture write denied</b>")
    monkeypatch.setattr("saydraft.dictionary.store.os.replace", fail)
    assert not subject.page.export_file(destination)
    assert destination.read_bytes() == b"owner bytes"
    assert "<b>fixture write denied</b>" in subject.window.status_label.text()
    assert subject.window.status_label.textFormat() == subject.qt.QtCore.Qt.PlainText


def test_file_dialog_cancel_is_noop_and_export_uses_exact_confirmed_path(subject, monkeypatch):
    p, qt = subject.page, subject.qt
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "getOpenFileName", lambda *args: ("", ""))
    before = p.json_editor.toPlainText()
    assert not p.choose_import() and p.json_editor.toPlainText() == before
    target = subject.directory / "chosen.without-json"
    calls = []
    def choose(dialog):
        assert dialog.acceptMode() == qt.QtWidgets.QFileDialog.AcceptSave
        assert dialog.fileMode() == qt.QtWidgets.QFileDialog.AnyFile
        assert dialog.defaultSuffix() == "json"
        assert not dialog.testOption(qt.QtWidgets.QFileDialog.DontConfirmOverwrite)
        dialog.selectFile(str(target))
        return qt.QtWidgets.QDialog.Accepted
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "exec", choose)
    monkeypatch.setattr(p, "export_file", lambda path: calls.append(path) or True)
    assert p.choose_export() and len(calls) == 1 and Path(calls[0]) == target
    monkeypatch.setattr(qt.QtWidgets.QFileDialog, "exec", lambda self: qt.QtWidgets.QDialog.Rejected)
    assert not p.choose_export() and len(calls) == 1


def test_real_app_queues_learning_updates_on_gui_thread_without_opening_a_hub(subject, monkeypatch):
    from saydraft.app import SaydraftApp
    from saydraft.config import default_config

    qt = subject.qt
    application = qt.QtWidgets.QApplication.instance()
    monkeypatch.setattr(qt.QtWidgets.QApplication, "exec", lambda self: 0)
    monkeypatch.setattr("saydraft.ui.fonts.install_bundled_fonts", lambda *args, **kwargs: None)
    monkeypatch.setattr("saydraft.ui.theme.install_theme", lambda *args, **kwargs: None)
    config = default_config()
    config["app"]["onboarded"] = True
    def noop(*args, **kwargs):
        pass
    controller = SimpleNamespace(start=noop, stop=noop, model_label=lambda: "Public fixture")
    tray = SimpleNamespace(set_listening=noop, set_state=noop, show_notification=noop, set_model_label=noop)
    pill = SimpleNamespace(show_processing=noop, update_level=noop, finish_success=noop, show_error=noop)
    app = SaydraftApp(qt_modules=qt, controller_factory=lambda signals: controller,
        tray_factory=lambda **kwargs: tray, pill_factory=lambda **kwargs: pill,
        config_loader=lambda **kwargs: config, crash_guard_installer=lambda **kwargs: None)
    delivered = []
    original = subject.window.refresh_dictionary
    def observe(change):
        delivered.append(threading.get_ident())
        return original(change)
    monkeypatch.setattr(subject.window, "refresh_dictionary", observe)
    assert app.run() == 0
    try:
        # A change before first open must not create/show a Hub.
        app.signals.dictionary_changed.emit(object())
        application.processEvents()
        assert app.hub_window is None and not delivered
        app.settings_window = subject.window
        add_term(subject.path, "Kubernetes", learned=True)
        worker = threading.Thread(target=lambda: app.signals.dictionary_changed.emit(object()))
        worker.start()
        worker.join(2)
        assert not worker.is_alive() and not delivered
        application.processEvents()
        assert delivered == [threading.get_ident()]
        assert rows(subject.page)[-1] == ("Kubernetes", "Learned")
        subject.page.term_edit.setText("Pending input")
        app.signals.dictionary_changed.emit(object())
        application.processEvents()
        assert subject.page.term_edit.text() == "Pending input"
    finally:
        app.signals.blockSignals(True)
        application.aboutToQuit.disconnect(controller.stop)
        app.signals.deleteLater()
