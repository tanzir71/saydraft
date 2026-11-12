"""Nonactivating dictionary suggestions; all private words stay off the log channel."""

from PySide6 import QtCore, QtGui, QtWidgets


class DictionaryToast(QtWidgets.QWidget):
    action_requested = QtCore.Signal()
    dismissed = QtCore.Signal()

    def __init__(self):
        super().__init__(None, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self.setWindowTitle("Saydraft Dictionary")
        self.setObjectName("dictionaryToast")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        self.message = QtWidgets.QLabel()
        self.message.setTextFormat(QtCore.Qt.PlainText)
        self.message.setWordWrap(True)
        self.message.setFixedWidth(320)
        layout.addWidget(self.message)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        self.action = QtWidgets.QPushButton("Add")
        self.action.clicked.connect(self.action_requested)
        self.dismiss_button = QtWidgets.QPushButton("Dismiss")
        self.dismiss_button.clicked.connect(self.dismiss)
        buttons.addWidget(self.action)
        buttons.addWidget(self.dismiss_button)
        layout.addLayout(buttons)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.dismiss)

    def present(self, message, action="", *, timeout=12000):
        self.message.setText(message)
        self.message.setAccessibleName(message)
        self.action.setText(action)
        self.action.setVisible(bool(action))
        self.action.setEnabled(True)
        self.adjustSize()
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 20, area.bottom() - self.height() - 20)
        self.show()  # WA_ShowWithoutActivating preserves the user's current field.
        self.timer.start(timeout)

    def dismiss(self):
        self.timer.stop()
        self.hide()
        self.message.clear()
        self.message.setAccessibleName("")
        self.dismissed.emit()

    def closeEvent(self, event):
        self.dismiss()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.dismiss()
            event.accept()
        else:
            super().keyPressEvent(event)


class DictionaryPresenter(QtCore.QObject):
    def __init__(self, controller, *, config, parent=None):
        super().__init__(parent)
        self.controller, self.config = controller, config
        self.toast = DictionaryToast()
        self.suggestion, self.receipt = None, None
        self.closed = False
        self.toast.action_requested.connect(self.apply_action)
        self.toast.dismissed.connect(self._clear)

    def _clear(self):
        self.suggestion, self.receipt = None, None

    @QtCore.Slot(object)
    def suggest(self, suggestion):
        if self.closed or not self.controller.is_current_correction(suggestion):
            return
        self.toast.dismiss()
        if (self.config() or {}).get("dictation", {}).get("auto_add_dictionary", False):
            if self.controller.add_correction(suggestion, automatic=True):
                self.toast.present("Saving dictionary word…")
            return
        self.suggestion = suggestion
        self.toast.present(f'Add “\u2068{suggestion.candidate.term}\u2069” to your dictionary?', "Add")

    @QtCore.Slot()
    def apply_action(self):
        if self.closed:
            return
        if self.suggestion is not None:
            suggestion, self.suggestion = self.suggestion, None
            if self.controller.add_correction(suggestion):
                self.toast.present("Saving dictionary word…")
            else:
                self.toast.dismiss()
        elif self.receipt is not None:
            if self.controller.undo_correction(self.receipt):
                self.toast.present("Undoing dictionary change…")
            else:
                self.toast.present("Finish the current work, then try Undo.", "Undo")

    @QtCore.Slot(object)
    def changed(self, change):
        if self.closed:
            return
        self._clear()
        if change.status == "added":
            self.receipt = change.receipt
            self.toast.present(f'Added “\u2068{change.receipt.term}\u2069” to your dictionary.', "Undo")
        elif change.status == "undone":
            self.toast.present("Dictionary change undone.")
        elif change.status == "unchanged":
            self.toast.present("No dictionary change was needed.")
        elif change.status == "stale":
            self.toast.present("That dictionary entry changed; nothing was removed.")
        elif change.status == "error":
            self.receipt = change.receipt
            self.toast.present("Could not save the dictionary change. Try again or check Settings.",
                "Undo" if self.receipt is not None else "")
        else:
            self.toast.dismiss()

    @QtCore.Slot()
    def retire_suggestion(self):
        if self.suggestion is not None:
            self.toast.dismiss()

    @QtCore.Slot()
    def close(self):
        self.closed = True
        self.toast.close()
