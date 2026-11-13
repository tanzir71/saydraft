"""Background model inventory and concrete confirmation before manual removal."""

import threading

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.models.storage import inventory, protected_paths, removal_reason


def bytes_label(value):
    return f"{value / 1e9:.2f} GB" if value >= 1e9 else f"{value / 1e6:.1f} MB" if value >= 1e6 else f"{value:,} bytes"


class ModelRemovalDialog(QtWidgets.QDialog):
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remove model files")
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setTabChangesFocus(True)
        self.details.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.details.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.details.setAccessibleName("Model removal details")
        self.details.setPlainText(f"Remove {entry.label}?\n\nRevision: {entry.revision}\nFolder: {entry.path}\n"
                       f"Recognized files: {bytes_label(entry.size)}\n\n"
                       "Only the confirmed model files will be removed after checksum verification. "
                       "Unknown files and other versions stay. You will need to download this version again to use it.")
        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok, self)
        remove = self.buttons.button(QtWidgets.QDialogButtonBox.Ok)
        remove.setText("Remove")
        remove.setAutoDefault(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.details, 1)
        layout.addWidget(self.buttons)
        cancel = self.buttons.button(QtWidgets.QDialogButtonBox.Cancel)
        cancel.setAutoDefault(False)
        cancel.setDefault(True)
        cancel.setFocus(QtCore.Qt.OtherFocusReason)
        window = parent.window() if parent is not None else None
        self.resize(min(720, max(360, window.width() - 80)) if window else 640,
                    min(520, max(360, window.height() - 60)) if window else 480)


class StorageTask(QtCore.QObject):
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    finished = QtCore.Signal()
    _settled = QtCore.Signal()
    _active = set()

    def __init__(self):
        super().__init__()
        self._settled.connect(self._finish, QtCore.Qt.QueuedConnection)

    def start(self, action):
        def run():
            try:
                self.succeeded.emit(action())
            except Exception as error:
                self.failed.emit(str(error))
            finally:
                self._settled.emit()
        self._thread = threading.Thread(target=run, name="Saydraft-model-storage", daemon=True)
        self._active.add(self)
        try:
            self._thread.start()
        except BaseException:
            self._active.discard(self)
            self.deleteLater()
            raise

    @QtCore.Slot()
    def _finish(self):
        if self._thread.is_alive():
            QtCore.QTimer.singleShot(1, self._finish)
            return
        self.finished.emit()
        self._active.discard(self)
        self.deleteLater()


class ModelStorage(QtWidgets.QWidget):
    def __init__(self, *, config_provider, remove_callback=None, inventory_provider=inventory):
        super().__init__()
        self.config_provider, self.remove_callback = config_provider, remove_callback
        self.inventory_provider = inventory_provider
        self.task, self.snapshot = None, None
        self._refresh_pending = False
        self.combo = QtWidgets.QComboBox()
        self.combo.setAccessibleName("Installed models and retained versions")
        self.combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.combo.setMinimumContentsLength(20)
        self.summary, self.details, self.status = (QtWidgets.QLabel() for _ in range(3))
        for label in (self.summary, self.details, self.status):
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.summary.setText("Refresh to inspect installed models and disk usage. No files are changed by inspection.")
        self.refresh_button = QtWidgets.QPushButton("Refresh storage")
        self.remove_button = QtWidgets.QPushButton("Remove…")
        self.remove_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh)
        self.remove_button.clicked.connect(self.request_remove)
        self.combo.currentIndexChanged.connect(self.selection_changed)
        self.confirm = self._confirm
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self.summary, self.combo, self.details):
            layout.addWidget(widget)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.remove_button)
        layout.addLayout(buttons)
        layout.addWidget(self.status)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _start(self, action, finished, *, refresh_after=False):
        if self.task is not None:
            return
        task = self.task = StorageTask()
        self.refresh_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.combo.setEnabled(False)
        task.succeeded.connect(finished)
        task.failed.connect(self.status.setText)
        task.finished.connect(self._finished)
        self._refresh_pending = self._refresh_pending or refresh_after
        task.start(action)

    @QtCore.Slot()
    def _finished(self):
        self.task = None
        self.combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.selection_changed()
        if self._refresh_pending:
            self._refresh_pending = False
            self.refresh()

    def refresh(self):
        if self.task is not None:
            self._refresh_pending = True
            return
        self._start(self.inventory_provider, self._inventoried)

    @QtCore.Slot(object)
    def _inventoried(self, snapshot):
        previous = self.combo.currentData()
        self.snapshot = snapshot
        lines = []
        for usage in snapshot.roots:
            free = bytes_label(usage.free) if usage.free is not None else "unknown"
            lines.append(f"{usage.root.label}: {bytes_label(usage.total)} logical file size; "
                         f"{bytes_label(usage.other)} other or cached files retained. Drive free: {free}." +
                         (f" {usage.skipped} linked or unreadable entries excluded." if usage.skipped else ""))
        self.summary.setText("\n".join(lines) + "\nInventory checks receipts and sizes; removal verifies payload checksums. "
                             "Older versions are never removed automatically.")
        self.combo.clear()
        for entry in snapshot.models:
            self.combo.addItem(f"{entry.label} · {entry.status} · {bytes_label(entry.size)} · {entry.root.label}", entry)
        if previous is not None:
            index = next((i for i, entry in enumerate(snapshot.models) if entry.path == previous.path), -1)
            if index >= 0:
                self.combo.setCurrentIndex(index)
        self.selection_changed()

    def selection_changed(self, _index=None):
        entry = self.combo.currentData()
        if entry is None:
            self.details.setText("No catalogued model folders found. Download a model above to set up speech recognition.")
            self.remove_button.setEnabled(False)
            return
        reason = removal_reason(entry, protected_paths(self.config_provider()))
        if self.remove_callback is None:
            reason = "Removal is available while connected to the running app."
        self.details.setText(f"{entry.status} · {bytes_label(entry.size)} recognized files\n"
                             f"Revision: {entry.revision}\nFolder: {entry.path}" + (f"\n{reason}" if reason else ""))
        self.remove_button.setEnabled(not reason and self.task is None)

    def _confirm(self, entry):
        dialog = ModelRemovalDialog(entry, self)
        return dialog.exec() == QtWidgets.QDialog.Accepted

    def request_remove(self):
        entry = self.combo.currentData()
        if self.task is not None or entry is None or self.remove_callback is None:
            return
        reason = removal_reason(entry, protected_paths(self.config_provider()))
        if reason:
            self.status.setText(reason)
            return
        if not self.confirm(entry):
            return
        self.status.setText("Verifying the confirmed model files before removal…")
        self._start(lambda: self.remove_callback(entry), self._removed, refresh_after=True)

    @QtCore.Slot(object)
    def _removed(self, result):
        self.status.setText(f"Removed {result.removed} files ({bytes_label(result.bytes_removed)}). "
                            "Unknown files and other versions were preserved." +
                            (" Removal stopped: " + "; ".join(result.errors) if result.errors else ""))
