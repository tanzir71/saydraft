"""Queued update notices and saved opt-in controls for Settings → Privacy."""

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft import __version__
from saydraft.updates import UpdateController, check_updates, updates_enabled


class UpdatePresenter(QtCore.QObject):
    received = QtCore.Signal(object)
    changed = QtCore.Signal(object)

    def __init__(self, *, parent=None, on_available=None, checker=check_updates, thread_factory=None, opener=None):
        super().__init__(parent)
        self._closed = False
        self._notified_version = None
        self._on_available = on_available
        self._opener = opener or QtGui.QDesktopServices.openUrl
        options = {'checker': checker}
        if thread_factory is not None:
            options['thread_factory'] = thread_factory
        self.controller = UpdateController(self.received.emit, **options)
        self.received.connect(self._accept, QtCore.Qt.QueuedConnection)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(24 * 60 * 60 * 1000)
        self.timer.timeout.connect(self.check)

    @property
    def result(self):
        return self.controller.result

    def configure(self, enabled):
        if self._closed:
            return
        self.controller.configure(enabled)
        if self.controller.enabled:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def check(self):
        return not self._closed and self.controller.check()

    @QtCore.Slot(object)
    def _accept(self, event):
        if self._closed or not self.controller.is_current(event):
            return
        self.changed.emit(event.result)
        if event.result.state == 'available' and event.result.version != self._notified_version:
            self._notified_version = event.result.version
            if self._on_available is not None:
                self._on_available(event.result)

    def open_release(self):
        result = self.result
        return bool(not self._closed and self.controller.enabled and result.url
                    and self._opener(QtCore.QUrl(result.url)))

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.controller.close()
        try:
            self.timer.stop()
        except RuntimeError:  # Parent destruction may already have deleted Qt's timer.
            pass


class UpdatesCard(QtWidgets.QWidget):
    def __init__(self, config, *, presenter=None, parent=None):
        super().__init__(parent)
        self.setAccessibleName('App updates')
        self._owns_presenter = presenter is None
        self.presenter = presenter or UpdatePresenter(parent=self)
        self._saved = updates_enabled(config)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QtWidgets.QLabel('App updates')
        heading.setProperty('role', 'display')
        layout.addWidget(heading)
        layout.addWidget(QtWidgets.QLabel(f'Installed version: {__version__}'))
        self.enabled_checkbox = QtWidgets.QCheckBox('Check for app updates')
        self.enabled_checkbox.setAccessibleName('Check for app updates')
        self.enabled_checkbox.setChecked(self._saved)
        layout.addWidget(self.enabled_checkbox)
        description = QtWidgets.QLabel('Off by default. When enabled, check GitHub releases at startup and once a day. '
                                      'Download and install updates from the release page.')
        description.setWordWrap(True)
        layout.addWidget(description)
        self.status = QtWidgets.QLabel()
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName('App update status')
        layout.addWidget(self.status)
        actions = QtWidgets.QHBoxLayout()
        self.check_button = QtWidgets.QPushButton('Check now')
        self.check_button.setAccessibleName('Check app updates now')
        self.release_button = QtWidgets.QPushButton('View release')
        self.release_button.setAccessibleName('View app release on GitHub')
        actions.addWidget(self.check_button)
        actions.addWidget(self.release_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.enabled_checkbox.toggled.connect(self.refresh)
        self.presenter.changed.connect(self.refresh)
        self.check_button.clicked.connect(self.check)
        self.release_button.clicked.connect(self.open_release)
        if self._owns_presenter:
            self.presenter.configure(self._saved)
        self.refresh()

    def set_choice(self, enabled):
        self.enabled_checkbox.setChecked(enabled is True)
        self.refresh()

    def apply_policy(self, enabled):
        self._saved = enabled is True
        self.presenter.configure(self._saved)
        self.refresh()

    def refresh(self, *_args):
        staged = self.enabled_checkbox.isChecked() != self._saved
        result = self.presenter.result
        if staged:
            message = 'Save preferences to apply your update-check choice.'
        elif not self._saved:
            message = 'App update checks are off.'
        else:
            message = {'checking': 'Checking GitHub releases…', 'current': 'No newer app release is available.',
                       'no_release': 'No published app release is available yet.',
                       'unavailable': 'Could not check for updates. Try again later.',
                       'disabled': 'App update checks are off.',
                       'available': f'Saydraft {result.version} is available.'}[result.state]
        self.status.setText(message)
        permitted = self._saved and not staged
        self.check_button.setEnabled(permitted and result.state != 'checking')
        self.release_button.setEnabled(permitted and result.state == 'available')

    def check(self):
        return self.check_button.isEnabled() and self.presenter.check()

    def open_release(self):
        return self.release_button.isEnabled() and self.presenter.open_release()

    def closeEvent(self, event):
        if self._owns_presenter:
            self.presenter.close()
        super().closeEvent(event)
