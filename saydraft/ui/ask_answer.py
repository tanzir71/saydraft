"""Independent answer Scratchpad; never loads or activates the current note."""

from PySide6 import QtCore

from saydraft.cleanup.llm.ask import MAX_ANSWER_UNITS, _valid_text
from saydraft.core.ask import AskResult
from .command_recovery import _RecoveryStore
from .scratchpad import ScratchpadWindow


class AskAnswerWindow(ScratchpadWindow):
    def __init__(self, store, result, *, clipboard=None):
        if type(result) is not AskResult or not _valid_text(result.text, MAX_ANSWER_UNITS):
            raise ValueError('Ask recovery requires a complete bounded answer')
        description = ('Review your local answer before using it. It saves as a separate note on this PC.'
            if result.history_id is not None else
            'Review your local answer before using it. History could not save it. This window keeps a separate note.')
        super().__init__(_RecoveryStore(store), clipboard=clipboard, heading='Ask answer', description=description)
        self.result = result
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.new_button.hide()
        self.editor.setAccessibleName('Ask answer text')
        self.draft.new()
        self._render(self.draft.snapshot())
        self.editor.setPlainText(result.text)
        self.timer.stop()

    def present(self, *, valid=lambda: True):
        if not valid():
            return False
        self.show()
        if not valid():
            self.hide()
            return False
        self.raise_()
        if not valid():
            self.hide()
            return False
        self.activateWindow()
        self.editor.setFocus()
        if not valid():
            self.hide()
            return False
        self.draft.save()
        return True

    def closeEvent(self, event):
        if self.draft.snapshot().dirty or self.draft.snapshot().saving:
            event.ignore()
            self.flush_then(self.close)
            return
        super().closeEvent(event)
