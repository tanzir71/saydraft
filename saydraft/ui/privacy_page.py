"""Applied audio expiry, local network facts and an explicit read-only rule check."""

from concurrent.futures import ThreadPoolExecutor

from PySide6 import QtCore, QtWidgets

from saydraft.data.retention import AudioRetentionPolicy
from saydraft.privacy.firewall import FirewallStatus,inspect_firewall
from saydraft.privacy.netguard import NetworkGuard


class PrivacyPage(QtWidgets.QWidget):
    firewall_ready = QtCore.Signal(int,object)

    def __init__(self, config, checkbox, *, saved_policy, cleanup_callback=None, firewall_provider=None, parent=None):
        super().__init__(parent)
        self.checkbox,self.saved_policy,self.cleanup_callback = checkbox,saved_policy,cleanup_callback
        self.firewall_provider = firewall_provider or inspect_firewall
        self._closed = self._working = False
        self._pool = self._future = None
        self._firewall_generation = self._retention_generation = 0
        layout = QtWidgets.QVBoxLayout(self)
        def paragraph(text,*,display=False):
            label = QtWidgets.QLabel(text)
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
            label.setSizePolicy(policy)
            if display:
                label.setProperty("role","display")
            layout.addWidget(label)
            return label
        paragraph("Your words stay on your machine.",display=True)
        self.network_status = paragraph("")
        paragraph("The Python network policy blocks connections outside loopback. Model downloads happen only when requested. OS rules and native helpers need separate verification.")
        paragraph("Telemetry: none. Dictation, cleanup, History and preferences stay local.")
        self.firewall_status = paragraph("Windows Firewall: not checked.")
        self.firewall_button = QtWidgets.QPushButton("Check firewall rules")
        self.firewall_button.clicked.connect(self.check_firewall)
        layout.addWidget(self.firewall_button)
        paragraph("Saved recordings",display=True)
        layout.addWidget(checkbox)
        self.retention_combo = QtWidgets.QComboBox()
        self.retention_combo.addItem("Keep forever",0)
        self.retention_combo.addItem("Keep for a set number of days",1)
        self.retention_combo.setAccessibleName("Saved recording retention")
        self.retention_combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored,QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(self.retention_combo)
        self.days_spin = QtWidgets.QSpinBox()
        self.days_spin.setRange(1,3650)
        self.days_spin.setSuffix(" days")
        self.days_spin.setAccessibleName("Days to keep saved recordings")
        layout.addWidget(self.days_spin)
        paragraph("Off by default. Turning this off stops saving new recordings and leaves existing ones untouched. Keep forever preserves the current recordings.")
        paragraph("Saving a time limit enables automatic cleanup of expired recordings linked in History. Raw and cleaned text stay in History. Other files are kept. A recent retry does not restart a recording’s age.")
        self.cleanup_button = QtWidgets.QPushButton("Clean up expired recordings now")
        layout.addWidget(self.cleanup_button)
        self.retention_status = paragraph("")
        layout.addStretch()
        checkbox.toggled.connect(self._actions)
        self.retention_combo.currentIndexChanged.connect(self._actions)
        self.days_spin.valueChanged.connect(self._actions)
        self.cleanup_button.clicked.connect(self.cleanup)
        self.firewall_ready.connect(self._accept_firewall,QtCore.Qt.QueuedConnection)
        self.destroyed.connect(self._shutdown)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self._shutdown)
        self.set_policy(AudioRetentionPolicy.from_config(config))
        self.refresh_network()

    def policy(self):
        return AudioRetentionPolicy(self.checkbox.isChecked(),self.days_spin.value() if self.retention_combo.currentData() else 0)

    def set_policy(self, policy):
        self.checkbox.setChecked(policy.enabled)
        self.retention_combo.setCurrentIndex(1 if policy.days else 0)
        self.days_spin.setValue(policy.days or 30)
        self._actions()

    def _actions(self):
        self.retention_combo.setEnabled(self.checkbox.isChecked())
        self.days_spin.setEnabled(self.checkbox.isChecked() and bool(self.retention_combo.currentData()))
        self.cleanup_button.setEnabled(not self._closed and not self._working and self.cleanup_callback is not None
            and self.policy().expires and self.policy()==self.saved_policy())

    def policy_saved(self):
        self._working = False
        self.retention_status.setText("")
        self._actions()

    def refresh_network(self):
        self.network_status.setText("Offline mode active" if NetworkGuard.is_installed() else "Offline policy unavailable")

    def cleanup(self):
        if self._closed or self._working or not self.policy().expires or self.policy()!=self.saved_policy() or self.cleanup_callback is None:
            return False
        try:
            accepted = bool(self.cleanup_callback(self.policy()))
        except Exception:
            accepted = False
        if accepted:
            self._working = True
            self.retention_status.setText("Cleaning up expired saved recordings…")
        else:
            self.retention_status.setText("Cleanup is not ready. Wait for current work to finish, then try again.")
        self._actions()
        return accepted

    @QtCore.Slot(object)
    def accept_retention(self, update):
        if self._closed or update.policy!=self.saved_policy() or update.generation<self._retention_generation:
            return
        self._retention_generation = update.generation
        self._working = update.state=="working"
        if self._working:
            message = "Cleaning up expired saved recordings…"
        elif update.state=="failed" or update.result is None:
            message = "Audio cleanup could not finish. Some expired recordings may remain; try again."
        else:
            result = update.result
            message = f"Removed {result.removed} expired recording(s). Cleared {result.unavailable} unavailable audio link(s)."
            if result.skipped or result.failed:
                message += f" Left {result.skipped} unchanged; {result.failed} could not be processed."
        self.retention_status.setText(message)
        self._actions()

    def check_firewall(self):
        if self._closed or self._future is not None and not self._future.done():
            return False
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=1,thread_name_prefix="Saydraft-firewall-check")
        self._firewall_generation += 1
        generation = self._firewall_generation
        self.firewall_button.setEnabled(False)
        self.firewall_status.setText("Checking this process’s firewall rules…")
        def run():
            try:
                result = self.firewall_provider()
            except Exception:
                result = FirewallStatus()
            if not self._closed:
                try:
                    self.firewall_ready.emit(generation,result)
                except RuntimeError:
                    pass
        self._future = self._pool.submit(run)
        return True

    @QtCore.Slot(int,object)
    def _accept_firewall(self, generation, result):
        if self._closed or generation!=self._firewall_generation:
            return
        self._future = None
        self.firewall_button.setEnabled(True)
        if result.state=="found":
            message = f"Windows Firewall: {result.matching_rules} matching enabled outbound block rule(s) for this process."
        elif result.state=="absent":
            message = "Windows Firewall: no matching process block rule found."
        elif result.state=="unsupported":
            message = "Windows Firewall inspection is available on Windows."
        else:
            message = "Windows Firewall: could not read the current process rules."
        self.firewall_status.setText(message+" Native-helper and destination coverage is not verified by this check.")

    @QtCore.Slot()
    def _shutdown(self):
        self._closed = True
        if self._pool is not None:
            self._pool.shutdown(wait=False,cancel_futures=True)

    def closeEvent(self,event):
        self._shutdown()
        super().closeEvent(event)
