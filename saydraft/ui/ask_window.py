"""Review a frozen selection and ask locally; this window never reads a target."""

import logging

from PySide6 import QtCore, QtWidgets

from saydraft.cleanup.llm.ask import build_ask_messages
from saydraft.core.ask import AskResult, AskSource
from .private_text import PrivatePlainTextEdit

logger = logging.getLogger(__name__)
_PRESETS = (
    ('Summarize', 'summarize', 'Summarize the selected text.'),
    ('Explain', 'explain', 'Explain the selected text.'),
    ('Rewrite', 'rewrite', 'Rewrite the selected text clearly, preserving its facts and meaning.'),
)
_ERRORS = {
    'context_limit': 'This selection is too long for the local model. Select a shorter passage and try again.',
    'invalid_request': 'Enter a short question and try again.',
    'cancelled': 'Ask was cancelled. You can try again.',
    'history_unavailable': 'Your answer is ready in a separate window. It could not be saved to History.',
    'display_unavailable': 'The answer window could not open. Check History for a saved answer.',
}


class AskQuestionWindow(QtWidgets.QWidget):
    def __init__(self, source, *, submit, cancel, valid=lambda: True):
        if type(source) is not AskSource:
            raise ValueError('Ask requires a reviewed source')
        build_ask_messages(source.text, 'Review the selected text.')
        super().__init__(None, QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.source, self._submit, self._cancel, self._valid = source, submit, cancel, valid
        self._busy = self._retired = self._closing = False
        self.setWindowTitle('Ask about selected text — Saydraft')
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.resize(640, 620)
        self.setMinimumSize(480, 520)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)
        scroll = QtWidgets.QScrollArea()
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setFocusPolicy(QtCore.Qt.NoFocus)
        scroll.setAccessibleName('Ask review')
        self.review_scroll = scroll
        self._scroll_timer = QtCore.QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._ensure_question_visible)
        body = QtWidgets.QWidget()
        scroll.setWidget(body)
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        outer.addWidget(scroll, 1)
        title = QtWidgets.QLabel('Ask about selected text')
        title.setTextFormat(QtCore.Qt.PlainText)
        title.setProperty('role', 'display')
        layout.addWidget(title)
        description = QtWidgets.QLabel('Review the selection, then ask a question or choose an action. '
            'Answers run on this PC and open in a separate Scratchpad.')
        description.setWordWrap(True)
        description.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(description)
        self.source_editor = PrivatePlainTextEdit()
        self.source_editor.setAccessibleName('Reviewed selection for Ask')
        self.source_editor.setReadOnly(True)
        self.source_editor.setPlainText(source.text)
        self.source_editor.setMinimumHeight(100)
        self.source_editor.setMaximumHeight(140)
        layout.addWidget(self.source_editor, 1)
        presets = QtWidgets.QHBoxLayout()
        self.preset_buttons = []
        for label, action, question in _PRESETS:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, action=action, question=question: self.send(question, action))
            presets.addWidget(button)
            self.preset_buttons.append(button)
        layout.addLayout(presets)
        self.question = PrivatePlainTextEdit()
        self.question.setAccessibleName('Question about selected text')
        self.question.setPlaceholderText('What would you like to know about this selection?')
        self.question.setTabChangesFocus(True)
        self.question.setMinimumHeight(80)
        self.question.setMaximumHeight(100)
        layout.addWidget(self.question, 1)
        self.status = QtWidgets.QLabel('Local answers use the reviewed text. Ask has no web tools.')
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName('Ask status')
        outer.addWidget(self.status)
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        self.ask_button = QtWidgets.QPushButton('Ask')
        self.ask_button.clicked.connect(lambda: self.send(self.question.toPlainText(), 'question'))
        self.close_button = QtWidgets.QPushButton('Close')
        self.close_button.clicked.connect(self.close)
        actions.addWidget(self.ask_button)
        actions.addWidget(self.close_button)
        outer.addLayout(actions)
        self.question.textChanged.connect(self._update)
        self._update()

    def _update(self):
        enabled = not self._busy and not self._retired
        self.question.setReadOnly(not enabled)
        for button in self.preset_buttons:
            button.setEnabled(enabled)
        try:
            build_ask_messages(self.source.text, self.question.toPlainText())
            question_ok = True
        except ValueError:
            question_ok = False
        self.ask_button.setEnabled(enabled and question_ok)
        self.close_button.setText('Cancel' if self._busy else 'Close')

    def present(self):
        if not self._valid():
            self.retire()
            return False
        self.show()
        if not self._valid():
            self.retire()
            return False
        self.raise_()
        self.activateWindow()
        self.question.setFocus()
        if not self._valid():
            self.retire()
            return False
        self._scroll_timer.start(0)
        return True

    def _ensure_question_visible(self):
        if not self._retired and self.isVisible():
            self.review_scroll.ensureWidgetVisible(self.question, 0, 8)

    def send(self, question, action='question'):
        if self._busy or self._retired or not self._valid():
            return False
        try:
            build_ask_messages(self.source.text, question, action)
        except ValueError:
            self.status.setText(_ERRORS['invalid_request'])
            return False
        if action != 'question':
            self.question.setPlainText(question)
        self._busy = True
        self.status.setText('Preparing the local answer…')
        self._update()
        try:
            accepted = bool(self._submit(question, action))
        except Exception:
            accepted = False
        if not accepted and self._busy:
            self._busy = False
            self.status.setText('Ask is unavailable now. Review the model and Labs settings, then try again.')
            self._update()
        return accepted

    def progress(self, text):
        if not self._retired and self._valid() and self._busy:
            self.status.setText(text)

    def finished(self, result):
        if type(result) is not AskResult or self._retired or not self._valid():
            return False
        self._busy = False
        self.status.setText('Your answer is ready in a separate Scratchpad.' if result.reason == 'ok' else
            _ERRORS.get(result.reason, 'The answer could not be completed. Your question is still here. Try again.'))
        self._update()
        self._scroll_timer.start(0)
        return True

    def retire(self):
        self._retired = True
        self._update()
        self.close()

    def closeEvent(self, event):
        self._retired = True
        if not self._closing:
            self._closing = True
            try:
                self._cancel()  # The caller fences this request; closure never waits for a model.
            except Exception:
                logger.warning('Ask window cancellation receiver unavailable')
        super().closeEvent(event)
