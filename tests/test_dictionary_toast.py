import threading
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from PySide6 import QtCore, QtGui, QtWidgets, QtTest

from saydraft.core.corrections import DictionaryChange
from saydraft.ui.dictionary_toast import DictionaryPresenter


@pytest.fixture
def presenter():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    QtGui.QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\segoeui.ttf")
    if Path(r"C:\Windows\Fonts\Nirmala.ttc").is_file():
        QtGui.QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\Nirmala.ttc")
    app.setFont(QtGui.QFont("Segoe UI", 9))
    candidate = NS(candidate=NS(term="Kubernetes"))
    calls = []
    controller = NS(is_current_correction=lambda obj: obj is candidate,
        add_correction=lambda obj, **kw: calls.append(("add", obj, kw)) or True,
        undo_correction=lambda receipt: calls.append(("undo", receipt)) or True)
    config = {"dictation": {"auto_add_dictionary": False}}
    p = DictionaryPresenter(controller, config=lambda: config)
    yield NS(p=p, app=app, candidate=candidate, calls=calls, controller=controller, config=config)
    p.close()


def test_suggestion_add_saved_undo_and_dismiss_clear_private_words(presenter):
    r = presenter
    r.p.suggest(r.candidate)
    assert r.p.toast.isVisible() and r.p.toast.action.text() == "Add"
    assert r.p.toast.testAttribute(QtCore.Qt.WA_ShowWithoutActivating)
    assert r.p.toast.message.textFormat() == QtCore.Qt.PlainText
    r.p.toast.action.click()
    assert r.calls == [("add", r.candidate, {})]
    receipt = NS(term="Kubernetes")
    r.p.changed(DictionaryChange("added", receipt))
    assert r.p.toast.action.text() == "Undo"
    r.p.toast.action.click()
    assert r.calls[-1] == ("undo", receipt)
    r.p.changed(DictionaryChange("undone"))
    assert "undone" in r.p.toast.message.text() and not r.p.toast.action.isVisible()
    r.p.toast.dismiss_button.click()
    assert not r.p.toast.isVisible() and not r.p.toast.message.text() and r.p.receipt is None


def test_auto_add_waits_for_saved_result_then_shows_undo(presenter):
    r = presenter
    r.config["dictation"]["auto_add_dictionary"] = True
    r.p.suggest(r.candidate)
    assert r.calls == [("add", r.candidate, {"automatic": True})]
    assert r.p.suggestion is None and not r.p.toast.action.isVisible()
    r.p.changed(DictionaryChange("added", NS(term="Kubernetes")))
    assert r.p.toast.action.text() == "Undo"


def test_obsolete_suggestions_and_closed_presenter_never_show(presenter):
    r = presenter
    r.p.suggest(NS(candidate=NS(term="Obsolete")))
    assert not r.p.toast.isVisible() and not r.calls
    r.p.close()
    r.p.suggest(r.candidate)
    r.p.changed(DictionaryChange("added", NS(term="Kubernetes")))
    assert not r.p.toast.isVisible() and not r.calls


def test_new_recording_retires_suggestion_but_preserves_actual_undo(presenter):
    r = presenter
    r.p.suggest(r.candidate)
    r.p.retire_suggestion()
    assert not r.p.toast.isVisible() and r.p.suggestion is None
    r.p.changed(DictionaryChange("added", NS(term="Kubernetes")))
    r.p.retire_suggestion()
    assert r.p.toast.isVisible() and r.p.receipt is not None


def test_busy_undo_and_write_error_keep_retry_action(presenter):
    r = presenter
    receipt = NS(term="Kubernetes")
    r.p.changed(DictionaryChange("added", receipt))
    r.controller.undo_correction = lambda obj: False
    r.p.toast.action.click()
    assert r.p.receipt is receipt and r.p.toast.action.text() == "Undo"
    r.p.changed(DictionaryChange("error", receipt))
    assert r.p.receipt is receipt and r.p.toast.action.isVisible()
    r.p.changed(DictionaryChange("stale"))
    assert r.p.receipt is None and not r.p.toast.action.isVisible()


def test_timer_and_escape_dismiss_and_plaintext_does_not_interpret_markup(presenter):
    r = presenter
    r.candidate.candidate.term = "<b>Word</b>"
    r.p.suggest(r.candidate)
    assert "<b>Word</b>" in r.p.toast.message.text()
    QtTest.QTest.keyClick(r.p.toast, QtCore.Qt.Key_Escape)
    assert not r.p.toast.isVisible() and not r.p.toast.message.text()
    r.p.suggest(r.candidate)
    r.p.toast.timer.timeout.emit()
    assert not r.p.toast.isVisible() and r.p.suggestion is None


def test_queued_worker_result_is_presented_on_gui_thread(presenter):
    from saydraft.app import create_worker_signals
    r = presenter
    signals = create_worker_signals(QtCore)
    class Receiver(QtCore.QObject):
        @QtCore.Slot(object)
        def receive(self, change):
            assert QtCore.QThread.currentThread() == r.app.thread()
            r.p.changed(change)
    receiver = Receiver()
    signals.dictionary_changed.connect(receiver.receive, QtCore.Qt.QueuedConnection)
    thread = threading.Thread(target=lambda: signals.dictionary_changed.emit(
        DictionaryChange("added", NS(term="Kubernetes"))))
    thread.start()
    thread.join(timeout=2)
    assert not r.p.toast.isVisible()
    r.app.processEvents()
    assert r.p.toast.isVisible() and r.p.toast.action.text() == "Undo"


@pytest.mark.parametrize("term", ["বাংলা", "العربية"], ids=["bengali", "arabic"])
def test_local_script_fonts_render_candidate_without_missing_glyphs(presenter, term):
    if not Path(r"C:\Windows\Fonts\Nirmala.ttc").is_file():
        pytest.skip("Windows script font is not installed on this test host")
    r = presenter
    r.candidate.candidate.term = term
    r.p.suggest(r.candidate)
    layout = QtGui.QTextLayout(r.p.toast.message.text(), r.p.toast.message.font())
    layout.beginLayout()
    layout.createLine().setLineWidth(320)
    layout.endLayout()
    runs = layout.glyphRuns()
    assert runs and all(glyph > 0 for run in runs for glyph in run.glyphIndexes())
