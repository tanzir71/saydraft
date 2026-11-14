"""Independent recovery Scratchpads; never replace or activate the current note."""

from PySide6 import QtCore

from saydraft.cleanup.llm.edit import MAX_REPLACEMENT_UNITS
from saydraft.core.command_edit import CommandEditResult
from .scratchpad import ScratchpadWindow


class _RecoveryStore:
    def __init__(self, store):
        self.store = store

    def save(self, identifier, body, **options):
        if self.store is None:
            raise OSError('Notes unavailable')
        return self.store.save(identifier, body, **{**options, 'activate': False})

    def get(self, identifier):
        return self.store.get(identifier) if self.store is not None else None

    def active(self):
        return None  # A recovery window must never load the owner's active draft.


def _description(result):
    if result.reason == 'copy_only':
        return ('Your edit is ready. The original selection could not be verified for replacement, so no paste was sent. '
                'Copy the edit into the original field. This edit saves as a separate note on this PC.')
    if result.reason == 'instruction_history_unavailable':
        return ('Editing did not finish and your instruction could not be saved to History. '
                'These are your recognized instruction words, available to copy and save as a separate note.')
    if result.reason == 'insertion_unconfirmed':
        return ('Paste was sent, but the change could not be confirmed. '
                'Check the original field before copying and pasting again. This edit saves as a separate note.')
    if result.reason == 'history_unavailable':
        return ('Your edit could not be saved to History. It is here to copy, '
                'and will try saving as a separate note on this PC.')
    return ('Your edit is ready to copy. Check the original field before pasting again. '
            'This edit saves as a separate note on this PC.')


class CommandRecoveryWindow(ScratchpadWindow):
    def __init__(self, store, result, *, clipboard=None):
        if not isinstance(result, CommandEditResult) or type(result.text) is not str or not result.text.strip():
            raise ValueError('Recovery requires a complete edit')
        try:
            if result.reason == 'instruction_history_unavailable':
                from saydraft.data.notes import MAX_NOTE_BYTES
                valid = len(result.text.encode('utf-8')) <= MAX_NOTE_BYTES
            else:
                valid = len(result.text) <= MAX_REPLACEMENT_UNITS and len(result.text.encode('utf-16-le')) // 2 <= MAX_REPLACEMENT_UNITS
        except UnicodeError:
            valid = False
        if not valid:
            raise ValueError('Recovery edit exceeds its text limit')
        heading = 'Command instruction' if result.reason == 'instruction_history_unavailable' else 'Command edit'
        super().__init__(_RecoveryStore(store), clipboard=clipboard, heading=heading, description=_description(result))
        self.result = result
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.new_button.hide()
        self.editor.setAccessibleName(heading + ' text')
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


class CommandRecoveryWindows:
    def __init__(self, store, *, clipboard=None, saved=lambda: None, notes=lambda: None,
                 window_factory=CommandRecoveryWindow):
        self.store, self.clipboard = store, clipboard
        self.saved, self.notes, self.window_factory = saved, notes, window_factory
        self._windows = {}

    @property
    def windows(self):
        return tuple(self._windows.values())

    def present(self, result, *, valid=lambda: True):
        if not valid():
            return None
        window = self.window_factory(self.store, result, clipboard=self.clipboard)
        key = id(window)
        self._windows[key] = window
        window.destroyed.connect(lambda _object=None, key=key: self._windows.pop(key, None))
        window.saved.connect(self.saved)
        window.notes_requested.connect(self.notes)
        if not window.present(valid=valid):
            self._windows.pop(key, None)
            window.draft.discard()
            window.shutdown()
            window.deleteLater()
            return None
        return window

    def flush_then(self, action):
        keys = tuple(self._windows)
        def advance(index):
            while index < len(keys) and keys[index] not in self._windows:
                index += 1
            if index == len(keys):
                return action() is not False
            outcome = [None]
            def proceed():
                outcome[0] = advance(index + 1)
            accepted = self._windows[keys[index]].flush_then(proceed)
            return accepted and outcome[0] is not False
        return advance(0)

    def shutdown(self):
        for window in self.windows:
            window.shutdown()
