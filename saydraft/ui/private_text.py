"""Keep selection copies and drags private through Qt's native MIME converter."""

from PySide6 import QtCore, QtWidgets

from saydraft.insert._clipboard_win32 import PRIVACY_FORMATS


class PrivatePlainTextEdit(QtWidgets.QPlainTextEdit):
    def createMimeDataFromSelection(self):
        data = super().createMimeDataFromSelection()
        for name in PRIVACY_FORMATS:
            data.setData(f'application/x-qt-windows-mime;value="{name}"', QtCore.QByteArray(bytes(4)))
        return data
