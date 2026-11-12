"""Keep selection copies and drags private through Qt's native MIME converter."""

from PySide6 import QtCore, QtWidgets

from saydraft.insert._clipboard_win32 import PRIVACY_FORMATS


class PrivatePlainTextEdit(QtWidgets.QPlainTextEdit):
    def createMimeDataFromSelection(self):
        selection = super().createMimeDataFromSelection()
        # Qt's selection MIME subclass overrides formats()/retrieveData(); new
        # formats set on that object are invisible. Copy into a regular object.
        data = QtCore.QMimeData()
        for name in selection.formats():
            data.setData(name, selection.data(name))
        for name in PRIVACY_FORMATS:
            data.setData(f'application/x-qt-windows-mime;value="{name}"', QtCore.QByteArray(bytes(4)))
        return data
