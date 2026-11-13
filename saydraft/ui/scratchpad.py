"""Private plain-text Scratchpad with asynchronous, revision-aware autosave."""

from PySide6 import QtCore, QtWidgets

from saydraft.core.note_draft import NoteDraft
from .private_text import PrivatePlainTextEdit


_ERRORS = {
    'load': 'Could not load this note. Try again.',
    'missing': 'This note was deleted. Choose New note to start again.',
    'queue': 'Notes are unavailable. Your unsaved text is still here. Try again.',
    'storage': 'Could not save. Your unsaved text is still here. Try again.',
    'conflict': 'This note changed or was deleted elsewhere. Save as new to keep this draft, or discard changes and reload.',
    'invalid': 'This note could not be saved. Keep it under 1 MiB of text and try again.',
}


def _retire_draft(draft):
    state = draft.snapshot()
    if state.dirty and not state.error:
        draft.save()
    draft.close(force=True)


class ScratchpadWindow(QtWidgets.QWidget):
    state_changed = QtCore.Signal(object)
    saved = QtCore.Signal()
    notes_requested = QtCore.Signal()

    def __init__(self, store, *, clipboard=None, draft_factory=NoteDraft):
        super().__init__(None, QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowTitle('Scratchpad — Saydraft')
        self.resize(640, 520)
        self.setMinimumSize(480, 420)
        self.clipboard = clipboard
        self._presented_generation = None
        self._requested_id = None
        self._pending = None
        self._last_saved = None
        self.draft = draft_factory(store, emit=self.state_changed.emit)
        self.state_changed.connect(self._accept, QtCore.Qt.QueuedConnection)
        self.destroyed.connect(lambda _object=None, draft=self.draft: _retire_draft(draft))
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.draft.save)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        heading = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('Scratchpad')
        title.setProperty('role', 'display')
        heading.addWidget(title, 1)
        self.new_button = QtWidgets.QPushButton('New note')
        self.new_button.clicked.connect(lambda: self.present(new=True))
        heading.addWidget(self.new_button)
        layout.addLayout(heading)
        description = QtWidgets.QLabel('A quiet place for your words. Notes save on this PC as you type.')
        description.setWordWrap(True)
        layout.addWidget(description)
        self.editor = PrivatePlainTextEdit()
        self.editor.setAccessibleName('Scratchpad text')
        self.editor.setPlaceholderText('Write or dictate here…')
        self.editor.textChanged.connect(self._edited)
        layout.addWidget(self.editor, 1)
        self.status = QtWidgets.QLabel('Loading…')
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName('Note save status')
        layout.addWidget(self.status)
        actions = QtWidgets.QHBoxLayout()
        self.retry_button = QtWidgets.QPushButton('Save now')
        self.retry_button.clicked.connect(self._retry)
        self.copy_button = QtWidgets.QPushButton('Copy')
        self.copy_button.clicked.connect(self.copy_text)
        self.notes_button = QtWidgets.QPushButton('View Notes')
        self.notes_button.clicked.connect(lambda: self.flush_then(self.notes_requested.emit))
        for button in (self.retry_button, self.copy_button, self.notes_button):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        recovery = QtWidgets.QHBoxLayout()
        self.save_copy_button = QtWidgets.QPushButton('Save as new')
        self.save_copy_button.clicked.connect(self._save_copy)
        self.discard_button = QtWidgets.QPushButton('Discard changes')
        self.discard_button.clicked.connect(self.discard_changes)
        recovery.addWidget(self.save_copy_button)
        recovery.addWidget(self.discard_button)
        recovery.addStretch()
        layout.addLayout(recovery)
        self._render(self.draft.snapshot())

    def present(self, identifier=None, *, new=False):
        self.show()
        self.raise_()
        self.activateWindow()
        def open_note():
            if new:
                self._requested_id = None
                self.draft.new()
            elif identifier is not None or not self.draft.snapshot().loaded:
                self._requested_id = identifier
                self.draft.load(identifier)
            self._render(self.draft.snapshot())
        self.flush_then(open_note)
        self.editor.setFocus()

    def _edited(self):
        if self.draft.edit(self.editor.toPlainText()):
            self.timer.start()
            self._render(self.draft.snapshot())

    @QtCore.Slot(object)
    def _accept(self, emitted):
        state = self.draft.snapshot()
        if emitted.generation != state.generation:
            return
        self._render(state)
        receipt = (state.identifier, state.revision)
        if state.loaded and state.revision and receipt != self._last_saved:
            self._last_saved = receipt
            self.saved.emit()
        if state.error:
            self._pending = None
            if state.dirty:
                self.show()
        elif state.loaded and not state.dirty and not state.saving and self._pending is not None:
            action, self._pending = self._pending, None
            action()

    def _render(self, state):
        if not state.loaded:
            self.editor.blockSignals(True)
            self.editor.clear()
            self.editor.blockSignals(False)
        elif self._presented_generation != state.generation:
            if self.editor.toPlainText() != state.body:
                self.editor.blockSignals(True)
                self.editor.setPlainText(state.body)
                self.editor.blockSignals(False)
            self._presented_generation = state.generation
        self.editor.setEnabled(state.loaded)
        self.status.setText(_ERRORS.get(state.error, 'Could not save. Try again.') if state.error else
            'Loading…' if not state.loaded else 'Saving…' if state.saving else
            'Unsaved changes' if state.dirty else 'Saved on this PC' if state.revision else 'New note')
        self.retry_button.setText('Retry load' if not state.loaded else 'Retry save' if state.error else 'Save now')
        self.retry_button.setEnabled(not state.saving)
        self.copy_button.setEnabled(state.loaded and bool(state.body))
        self.new_button.setEnabled(not state.saving)
        self.save_copy_button.setVisible(bool(state.error and state.loaded))
        self.discard_button.setVisible(bool(state.error and state.loaded))
        self.save_copy_button.setEnabled(not state.saving)
        self.discard_button.setEnabled(not state.saving)

    def _retry(self):
        state = self.draft.snapshot()
        if not state.loaded:
            self.draft.load(self._requested_id)
            self._render(self.draft.snapshot())
        elif state.error == 'conflict':
            self.status.setText(_ERRORS['conflict'])
        else:
            self.draft.save(retry=True)

    def _save_copy(self):
        self.timer.stop()
        self._pending = None
        self.draft.save_copy()
        self._render(self.draft.snapshot())

    def discard_changes(self):
        if self.draft.snapshot().saving:
            return False
        choice = QtWidgets.QMessageBox.question(self, 'Discard unsaved changes?',
            'This discards only the unsaved draft. The stored note will be reloaded.',
            QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
        if choice != QtWidgets.QMessageBox.Discard:
            return False
        state = self.draft.snapshot()
        self.timer.stop()
        self._pending = None
        if self.draft.discard():
            self._requested_id = state.identifier if state.revision else None
            if state.revision:
                self.draft.load(state.identifier)
            else:
                self.draft.new()
            self._render(self.draft.snapshot())
            return True
        return False

    def flush_then(self, action):
        """Retain the window and text when a close/new/quit cannot save safely."""
        state = self.draft.snapshot()
        if state.dirty or state.saving:
            if state.error:
                self.show()
                self._render(state)
                return False
            self._pending = action
            self.timer.stop()
            if not self.draft.save():
                self._pending = None
                return False
        else:
            action()
        return True

    def copy_text(self):
        text = self.editor.toPlainText()
        if not text or not self.draft.snapshot().loaded:
            return False
        try:
            if self.clipboard is None:
                from saydraft.insert.clipboard_win import WindowsClipboard
                self.clipboard = WindowsClipboard()
            self.clipboard.setText(text)
        except (OSError, ValueError):
            self.status.setText('Could not copy. Your note is still here.')
            return False
        self.status.setText('Copied. This draft still needs to be saved.' if self.draft.snapshot().dirty else 'Copied')
        return True

    def closeEvent(self, event):
        if self.draft.snapshot().dirty or self.draft.snapshot().saving:
            event.ignore()
            self.flush_then(self.hide)
            return
        self.timer.stop()
        super().closeEvent(event)

    def shutdown(self):
        self.timer.stop()
        _retire_draft(self.draft)
