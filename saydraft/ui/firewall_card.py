"""User-initiated, immediate firewall actions, separate from saved preferences."""

import threading

from PySide6 import QtCore, QtWidgets

from saydraft.privacy.firewall_control import FirewallChange, change_firewall, packaged_executable


class FirewallCard(QtWidgets.QWidget):
    finished = QtCore.Signal(int, str, object)

    def __init__(self, *, target_provider=packaged_executable, changer=change_firewall, confirm=None, parent=None):
        super().__init__(parent)
        self.target_provider, self.changer = target_provider, changer
        self.confirm = confirm or self._confirm
        self._closed, self._busy, self._generation = False, False, 0
        self._thread = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.explanation = QtWidgets.QLabel(
            "Block Saydraft from the internet with a Windows Firewall outbound rule. "
            "Windows asks for administrator approval. Remove this rule before downloading models "
            "or checking for updates. Installed models keep working locally. "
            "The rule covers this Saydraft.exe path; separate helper executables need their own verification.")
        self.explanation.setTextFormat(QtCore.Qt.PlainText)
        self.explanation.setWordWrap(True)
        self.explanation.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(self.explanation)
        self.block_button = QtWidgets.QPushButton("Block Saydraft from the internet")
        self.remove_button = QtWidgets.QPushButton("Remove Saydraft’s block rule")
        layout.addWidget(self.block_button)
        layout.addWidget(self.remove_button)
        self.status = QtWidgets.QLabel()
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(self.status)
        self.block_button.clicked.connect(lambda: self.request("block"))
        self.remove_button.clicked.connect(lambda: self.request("remove"))
        self.finished.connect(self._accept, QtCore.Qt.QueuedConnection)
        # A plain closure survives QObject destruction; no QWidget calls here.
        self.destroyed.connect(lambda: self.retire())
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.retire)
        self._actions()

    def _actions(self):
        eligible = self.target_provider() is not None
        self.block_button.setEnabled(eligible and not self._closed and not self._busy)
        self.remove_button.setEnabled(eligible and not self._closed and not self._busy)
        if not eligible and not self._busy and not self._closed:
            self.status.setText("Available in a local, unlinked packaged Windows installation. Source Python is never blocked.")

    def _confirm(self, action, target):
        message = ("Block outbound connections for this Saydraft installation?\n\n"
                   "Model downloads and update checks will fail until you remove the rule. "
                   "Installed models can be used offline. Windows will request administrator approval."
                   if action == "block" else
                   "Remove the block rule created for this Saydraft installation?\n\n"
                   "Other firewall rules are preserved. Windows will request administrator approval.")
        dialog = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Question, "Saydraft firewall rule", message,
                                      QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, self)
        dialog.setTextFormat(QtCore.Qt.PlainText)
        dialog.setInformativeText(str(target))
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        return dialog.exec() == QtWidgets.QMessageBox.Ok

    def request(self, action):
        if action not in ("block", "remove") or self._closed or self._busy:
            return False
        target = self.target_provider()
        if target is None or not self.confirm(action, target) or self._closed:
            return False
        self._generation += 1
        generation = self._generation
        self._busy = True
        self.status.setText("Waiting for Windows approval and the firewall result… Closing Settings does not cancel an approved change.")
        self._actions()

        def run():
            try:
                result = self.changer(action)
            except Exception:
                result = FirewallChange()
            if not self._closed:
                try:
                    self.finished.emit(generation, action, result)
                except RuntimeError:
                    pass

        self._thread = threading.Thread(target=run, name="Saydraft-firewall-change", daemon=True)
        try:
            self._thread.start()
        except RuntimeError:
            self._accept(generation, action, FirewallChange())
        return True

    @QtCore.Slot(int, str, object)
    def _accept(self, generation, action, result):
        if self._closed or generation != self._generation:
            return
        self._busy = False
        messages = {
            "cancelled": "Windows approval was cancelled. No change was requested from the helper.",
            "conflict": "A conflicting or edited rule was found. It was left unchanged; review it in Windows Firewall.",
            "failed": "The firewall change could not be confirmed. Check firewall rules before trying again.",
            "unknown": "The helper’s result is unknown. Check Windows Firewall before trying again.",
            "unsupported": "Firewall controls require the local packaged Windows app.",
            "busy": "Another firewall request is still running. Wait for Windows to finish, then try again.",
        }
        if result.state == "applied":
            text = ("The outbound block rule is configured. Remove it before downloading models or checking for updates."
                    if action == "block" else "Saydraft’s managed rule is removed. Other firewall policies may still block connections.")
            text += " Use Check firewall rules and the offline verification guide to confirm the effective policy."
        else:
            text = messages.get(result.state, messages["failed"])
        self.status.setText(text)
        self._actions()

    @QtCore.Slot()
    def retire(self):
        self._closed = True
        self._generation += 1

    def closeEvent(self, event):
        self.retire()
        super().closeEvent(event)
