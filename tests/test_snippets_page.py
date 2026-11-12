import json
from types import SimpleNamespace

import pytest

from saydraft.data.snippets import SnippetStore
from tests.test_settings_window import FakeAutoStartManager, make_window, qt_modules


@pytest.fixture
def subject(tmp_path):
    qt = qt_modules()
    window, config, _ = make_window(tmp_path)
    try:
        yield SimpleNamespace(window=window, p=window.snippets_page, config=config, directory=tmp_path, qt=qt)
    finally:
        window.close()
        window.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def select(page, trigger):
    index = next(i for i, row in enumerate(page.model.rows) if row[0] == trigger)
    page.table.setCurrentIndex(page.model.index(index, 0))


def test_structured_crud_multiline_save_restart_and_source_preservation(subject):
    from saydraft.ui.settings_page import SettingsPage
    p, w = subject.p, subject.window
    old = (subject.directory / "snippets.txt").read_bytes()
    assert p.model.rows == [("addr", "123 Main")] and not p.dirty
    p.trigger_edit.setText("  my   signature  ")
    p.expansion_edit.setPlainText("  বাংলা\nالعربية\n{date}\n{clipboard}\nC:\\new\\1=a  ")
    assert w.snippet_store.read().editable == {"addr": "123 Main"}
    # Shared Save stages a pending multiline form, without requiring Add first.
    assert w.apply_changes()
    expected = {"addr": "123 Main", "my signature": "  বাংলা\nالعربية\n{date}\n{clipboard}\nC:\\new\\1=a  "}
    assert w.snippet_store.read().editable == expected and not p.dirty
    assert (subject.directory / "snippets.txt").read_bytes() == old
    reopened = SettingsPage(config_path=subject.config, snippets_path=subject.directory / "snippets.txt",
        autostart_manager=FakeAutoStartManager())
    try:
        assert reopened.snippets_page.entries() == expected
    finally:
        reopened.close()
        reopened.deleteLater()
    select(p, "my signature")
    p.trigger_edit.setText("my sign off")
    p.expansion_edit.setPlainText("New\nlines")
    assert p._edit("update")
    select(p, "addr")
    assert p._edit("remove")
    assert w.apply_changes()
    assert w.snippet_store.read().editable == {"my sign off": "New\nlines"}


def test_search_duplicate_validation_and_variable_buttons_keep_drafts_off_disk(subject):
    p, w = subject.p, subject.window
    p.trigger_edit.setText("Café")
    p.expansion_edit.setPlainText("Public")
    p.date_button.click()
    p.clipboard_button.click()
    assert "{date}" in p.expansion_edit.toPlainText() and "{clipboard}" in p.expansion_edit.toPlainText()
    assert p._edit("add")
    p.trigger_edit.setText("CAFE\u0301")
    p.expansion_edit.setPlainText("Different")
    assert not p._edit("add") and "already" in p.status_label.text()
    p.clear_form()
    assert not p._edit("add") and "Enter" in p.status_label.text()
    p.search.setText("public")
    assert len(p.model.rows) == 1 and p.model.rows[0][0] == "Café"
    assert w.snippet_store.read().editable == {"addr": "123 Main"}


def test_test_panel_includes_pending_form_and_never_reads_clipboard_or_records_history(subject, monkeypatch):
    p, qt = subject.p, subject.qt
    monkeypatch.setattr(qt.QtWidgets.QApplication, "clipboard", staticmethod(lambda: pytest.fail("Owner clipboard")))
    monkeypatch.setattr("saydraft.insert.clipboard_win.WindowsClipboard.read_text", lambda self: pytest.fail("Owner clipboard"))
    p.trigger_edit.setText("sign off")
    p.expansion_edit.setPlainText("Thanks\n{clipboard}\n{{date}} {unknown}")
    p.test_input.setPlainText("sign off sign off")
    p.clipboard_sample.setPlainText("sign off {date} \\1 <b>literal</b>")
    before = subject.window.snippet_store.read()
    assert p.test_expansion()
    value = "Thanks\nsign off {date} \\1 <b>literal</b>\n{date} {unknown}"
    assert p.test_output.toPlainText() == value + " " + value
    assert subject.window.snippet_store.read() == before and p.dirty
    with subject.window.snippet_store.connect() as connection:
        assert connection.execute("SELECT count(*) FROM dictations").fetchone() == (0,)
    assert p.trigger_edit.text() == "sign off"


def test_advanced_json_roundtrip_and_invalid_draft_refuse_all_shared_config_writes(subject):
    p, w = subject.p, subject.window
    p.json_editor.setPlainText(json.dumps({"sig": "One\nTwo"}))
    assert w.apply_changes() and w.snippet_store.read().editable == {"sig": "One\nTwo"}
    original = subject.config.read_bytes()
    dictionary = (subject.directory / "glossary.json").read_bytes()
    for raw in ("{broken", "broken legacy draft", '["not a document"]'):
        p.json_editor.setPlainText(raw)
        w.speech_hotkey_edit.setText("f8")
        w.dictionary_editor.setPlainText('{"user_terms":["Should stay staged"]}')
        assert not w.apply_changes()
        assert subject.config.read_bytes() == original
        assert (subject.directory / "glossary.json").read_bytes() == dictionary
        assert w.snippet_store.read().editable == {"sig": "One\nTwo"}
    p.reload_button.click()
    assert p.entries() == {"sig": "One\nTwo"} and not p.dirty


def test_stale_snippet_draft_does_not_overwrite_newer_rows_or_apply_other_pages(subject):
    p, w = subject.p, subject.window
    p.trigger_edit.setText("Draft")
    p.expansion_edit.setPlainText("Unsaved")
    latest = SnippetStore(w.snippets_db_path, legacy_path=w.snippets_path)
    latest.save({"newer": "Keep"}, expected_revision=latest.read().revision)
    original = subject.config.read_bytes()
    dictionary = (subject.directory / "glossary.json").read_bytes()
    w.dictionary_editor.setPlainText('{"user_terms":["Also staged"]}')
    assert not w.apply_changes()
    assert "Snippets changed" in w.status_label.text()
    assert subject.config.read_bytes() == original and (subject.directory / "glossary.json").read_bytes() == dictionary
    assert p.entries()["Draft"] == "Unsaved" and latest.read().editable == {"newer": "Keep"}
    p.reload_button.click()
    assert p.entries() == {"newer": "Keep"}


def test_unchanged_editor_keeps_newer_saved_rows_and_both_styles_and_runtime_see_the_same_values(subject):
    p, w = subject.p, subject.window
    other = SnippetStore(w.snippets_db_path, legacy_path=w.snippets_path)
    other.save({"sig": "Hello\nsecond line"}, expected_revision=other.read().revision)
    assert w.apply_changes() and p.entries() == {"sig": "Hello\nsecond line"}
    style = w.styles_page
    style.before.setPlainText("sig")
    style.refresh()
    assert "Hello\nsecond line" in style.after.toPlainText()


def test_preview_limit_is_visible_and_does_not_change_saved_entries(subject):
    p = subject.p
    p.test_input.setPlainText("x" * 4097)
    assert not p.test_expansion() and "4096" in p.status_label.text()
    assert p.entries() == {"addr": "123 Main"}
