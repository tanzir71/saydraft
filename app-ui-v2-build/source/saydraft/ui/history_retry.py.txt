"""Explicit installed-model and per-request cleanup choices for saved audio."""

from PySide6 import QtCore, QtWidgets

from saydraft.asr.retry import RetryOptions
from saydraft.asr.router import ALL_LANGUAGES


class HistoryRetryDialog(QtWidgets.QDialog):
    def __init__(self, models, *, source_model=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Retry saved audio")
        self.setAccessibleName("Retry saved audio")
        self.resize(560, 480)
        outer = QtWidgets.QVBoxLayout(self)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll, 1)
        def paragraph(text):
            label = QtWidgets.QLabel(text)
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
            label.setSizePolicy(policy)
            layout.addWidget(label)
            return label
        paragraph("Recognize the saved recording again. The original stays unchanged; the new result is saved in History for review.")
        self.model = QtWidgets.QComboBox()
        self.model.setAccessibleName("Speech model for this retry")
        self.model.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        for identifier, label in models:
            self.model.addItem(label, identifier)
        selected = self.model.findData(ALL_LANGUAGES)
        if selected < 0:
            selected = self.model.findData(source_model)
        if self.model.count():
            self.model.setCurrentIndex(max(0, selected))
        paragraph("Speech model")
        layout.addWidget(self.model)
        self.cleanup = QtWidgets.QComboBox()
        self.cleanup.setAccessibleName("Cleanup for this retry")
        self.cleanup.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        for label, choice in (("Use current setting", "current"), ("AI off · rules only", "off"), ("AI on · local model", "on")):
            self.cleanup.addItem(label, choice)
        paragraph("Cleanup")
        layout.addWidget(self.cleanup)
        paragraph("Only installed speech models are listed. Add models in Settings → Models. These choices apply to this retry only.")
        paragraph("AI uses the cleanup model selected in Settings and may take time to prepare. If it cannot help, rules are kept. Raw, Code and Verbatim keep their usual behavior.")
        if not self.model.count():
            paragraph("No installed speech model is available. Set one up in Settings before retrying.")
        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Start retry")
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(bool(self.model.count()))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

    def options(self):
        return RetryOptions(self.model.currentData(), self.cleanup.currentData())
