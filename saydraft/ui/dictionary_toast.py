"""Nonactivating dictionary suggestions; all private words stay off the log channel."""

from PySide6 import QtCore, QtGui, QtWidgets
from .kit import Label, ActionButton, IconButton, Card
from .icons import svg_icon
from .reflow import AdaptiveRow


class DictionaryToast(QtWidgets.QWidget):
    action_requested = QtCore.Signal()
    dismissed = QtCore.Signal()

    def __init__(self):
        super().__init__(None, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self.setWindowTitle("Saydraft Dictionary")
        self.setObjectName("dictionaryToast")
        self.setProperty("bare", True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setMinimumWidth(412)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16,16,16,26)
        self.card = Card(padding=0)
        self.card.setMinimumWidth(380)
        root.addWidget(self.card)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(26)
        shadow.setOffset(0,10)
        from .theme.style import color, high_contrast
        shade = color(self,"ink")
        shade.setAlphaF(.12)
        shadow.setColor(shade)
        shadow.setEnabled(not high_contrast(self))
        self.card.setGraphicsEffect(shadow)
        layout = self.card.body
        layout.setContentsMargins(14, 12, 12, 10)
        layout.setSpacing(10)
        heading = QtWidgets.QHBoxLayout()
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setFixedSize(28,28)
        heading.addWidget(self.icon_label)
        self.title = Label("Dictionary", "sub")
        heading.addWidget(self.title,1)
        self.close_button = IconButton("x", "Close notification")
        self.close_button.clicked.connect(self.dismiss)
        heading.addWidget(self.close_button)
        layout.addLayout(heading)
        self.message = Label("", "small")
        self.message.setMaximumWidth(352)
        layout.addWidget(self.message)
        buttons = AdaptiveRow()
        self.action = ActionButton("Add", primary=True, small=True)
        self.action.clicked.connect(self.action_requested)
        self.dismiss_button = ActionButton("Not now", small=True)
        self.dismiss_button.clicked.connect(self.dismiss)
        buttons.addWidget(self.action)
        buttons.addWidget(self.dismiss_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.dismiss)

    def present(self, message, action="", *, timeout=12000):
        self.message.setText(message)
        failed = str(message).startswith("Could not")
        added = str(message).startswith("Added")
        saving = str(message).startswith(("Saving", "Undoing"))
        self.title.setText("Couldn’t save" if failed else "Added to Dictionary" if added else "Saving" if saving else "Dictionary suggestion" if action == "Add" else "Dictionary")
        self.icon_label.setPixmap(svg_icon("alert" if failed else "check" if added else "info" if saving else "dictionary", self.palette(), size=24, tone="danger" if failed else "ok" if added else "ink").pixmap(24,24))
        self.dismiss_button.setText("Not now" if action == "Add" else "Dismiss")
        self.message.setAccessibleName(message)
        self.action.setText(action)
        self.action.setVisible(bool(action))
        self.action.setEnabled(True)
        self.adjustSize()
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 16, area.bottom() - self.height() - 80)
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
