"""Offscreen Ask review uses only authored strings and injected callbacks."""

import pytest

from saydraft.core.ask import AskResult, AskSource
from tests.test_history_window import qt_modules


@pytest.fixture
def subject():
    from saydraft.ui.ask_window import AskQuestionWindow
    qt = qt_modules()
    calls, closed, current = [], [], [True]
    window = AskQuestionWindow(AskSource('Public العربية বাংলা <b>literal</b>'),
        submit=lambda question, action: calls.append((question, action)) or True,
        cancel=lambda: closed.append(True), valid=lambda: current[0])
    try:
        yield window, calls, closed, current
    finally:
        window.close()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def test_source_is_plain_read_only_and_question_requires_valid_input(subject):
    window, calls, _, _ = subject
    assert window.source_editor.isReadOnly()
    assert window.source_editor.toPlainText() == 'Public العربية বাংলা <b>literal</b>'
    assert not window.ask_button.isEnabled()
    window.question.setPlainText('What does it say?')
    assert window.ask_button.isEnabled()
    window.ask_button.click()
    assert calls == [('What does it say?', 'question')]
    assert window.question.isReadOnly() and not window.ask_button.isEnabled()
    assert not any(button.isEnabled() for button in window.preset_buttons)
    assert window.close_button.isEnabled() and window.close_button.text() == 'Cancel'
    assert not window.send('Duplicate question') and len(calls) == 1


@pytest.mark.parametrize('index,action', [(0, 'summarize'), (1, 'explain'), (2, 'rewrite')])
def test_quick_actions_use_explicit_questions_without_changing_the_reviewed_source(subject, index, action):
    window, calls, _, _ = subject
    source = window.source_editor.toPlainText()
    window.preset_buttons[index].click()
    assert calls[0][1] == action and calls[0][0]
    assert window.question.toPlainText() == calls[0][0]
    assert window.source_editor.toPlainText() == source


def test_failure_preserves_question_for_retry_and_completion_keeps_source_window_independent(subject):
    window, calls, _, _ = subject
    window.question.setPlainText('Question retained.')
    window.ask_button.click()
    assert window.finished(AskResult(None, 'incomplete'))
    assert window.question.toPlainText() == 'Question retained.' and window.ask_button.isEnabled()
    assert 'still here' in window.status.text()
    window.ask_button.click()
    assert len(calls) == 2
    assert window.finished(AskResult('Complete answer', 'ok', 1))
    assert 'separate Scratchpad' in window.status.text()
    assert window.source_editor.toPlainText() == window.source.text


def test_oversized_unicode_question_is_not_truncated_or_submitted(subject):
    window, calls, _, _ = subject
    value = '😀' * 513
    window.question.setPlainText(value)
    assert window.question.toPlainText() == value and not window.ask_button.isEnabled()
    assert not window.send(value) and not calls


def test_retired_request_never_submits_or_accepts_late_progress(subject):
    window, calls, _, current = subject
    current[0] = False
    assert not window.send('Late question')
    assert not window.finished(AskResult('Late answer', 'ok', 1))
    window.progress('Late private text')
    assert not calls and 'Late private text' not in window.status.text()


def test_close_cancels_once_and_does_not_wait_for_worker(subject):
    window, _, closed, _ = subject
    window.question.setPlainText('Question')
    window.ask_button.click()
    window.close()
    window.close()
    assert closed == [True]


@pytest.mark.parametrize('reason', ['context_limit', 'incomplete', 'model_missing'])
def test_small_window_keeps_the_question_and_feedback_reachable(subject, reason):
    from PySide6 import QtTest
    from tests.test_scratchpad import settle
    window, _, _, _ = subject
    qt = qt_modules()
    qt.QtTest = QtTest
    window.resize(480, 520)
    assert window.present()
    qt.QtWidgets.QApplication.processEvents()
    window.finished(AskResult(None, reason))
    qt.QtWidgets.QApplication.processEvents()
    viewport = window.review_scroll.viewport()
    settle(qt, lambda: (window.question.mapTo(viewport, qt.QtCore.QPoint()).y()
                       + window.question.height() <= viewport.height()))
    position = window.question.mapTo(viewport, qt.QtCore.QPoint(0, 0))
    assert position.y() >= 0
    assert position.y() + window.question.height() <= viewport.height()
    assert window.status.isVisible() and window.close_button.isVisible()
    assert window.status.y() + window.status.height() <= window.close_button.y()


def test_presentation_gate_is_checked_again_before_focus_changes(subject, monkeypatch):
    window, _, closed, current = subject
    permitted = [True]
    monkeypatch.setattr(window, 'raise_', lambda: permitted.__setitem__(0, False))
    monkeypatch.setattr(window, 'activateWindow', lambda: pytest.fail('Retired presentation cannot activate'))
    assert not window.present(valid=lambda: permitted[0])
    assert closed == [True] and current[0]  # This gate is separate from ongoing review validity.
