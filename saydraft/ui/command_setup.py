"""Review the experimental Command model; transfer only on an explicit click."""

from html import escape
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.models.command import command_bundle, command_choice, download_command_model
from saydraft.models.cleanup import transfer_bytes
from saydraft.models.tiers import effective_tier
from .download_task import DownloadTask, call_download
from .progress import ThemedProgressBar


class CommandSetup(QtWidgets.QGroupBox):
    finished = QtCore.Signal()

    def __init__(self, config, *, report=None, callback=None):
        super().__init__('Command Mode · experimental')
        self.config, self.report = config, report
        self.callback, self.task = callback or download_command_model, None
        self.description = QtWidgets.QLabel('Select text and hold Ctrl+Win+Alt. Wait for the Command label, '
            'then speak a short editing instruction. Release to edit; Esc cancels. '
            'Read-only selections produce an edit to copy. This Pro feature uses a separate local editing model. '
            'Dictation cleanup can stay off.')
        self.description.setWordWrap(True)
        self.enabled_check = QtWidgets.QCheckBox('Enable experimental Command Mode')
        self.enabled_check.setChecked(config.get('labs', {}).get('command_mode', False))
        self.backend = QtWidgets.QComboBox()
        self.backend.setAccessibleName('Command model processor')
        for title, value in [('Recommended processor', 'auto'), ('CPU', 'cpu'), ('GPU (Vulkan)', 'vulkan')]:
            self.backend.addItem(title, value)
        self.backend.setCurrentIndex(max(0, self.backend.findData(config.get('command', {}).get('backend', 'auto'))))
        self.eligibility, self.license, self.status = QtWidgets.QLabel(), QtWidgets.QLabel(), QtWidgets.QLabel()
        for label in (self.eligibility, self.license, self.status):
            label.setWordWrap(True)
        self.eligibility.setTextFormat(QtCore.Qt.PlainText)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.license.setOpenExternalLinks(True)
        self._palette_timer = QtCore.QTimer(self)
        self._palette_timer.setSingleShot(True)
        self._palette_timer.timeout.connect(self._details)
        self.license.installEventFilter(self)
        self.download_button = QtWidgets.QPushButton('Download / Resume Command model')
        self.pause_button = QtWidgets.QPushButton('Pause')
        self.progress = ThemedProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setAccessibleName('Command model and processor download progress')
        self.status.setText('Review the size and licenses before downloading. Existing verified files are reused. '
                            'Enabling Command never starts a download.')
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.download_button)
        buttons.addWidget(self.pause_button)
        layout = QtWidgets.QVBoxLayout(self)
        for widget in (self.description, self.eligibility, self.enabled_check, self.backend, self.license):
            layout.addWidget(widget)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        self.backend.currentIndexChanged.connect(self._details)
        self.download_button.clicked.connect(self.start_download)
        self.pause_button.clicked.connect(self.pause)
        self.update_eligibility(config, report)

    def update_eligibility(self, config, report=None):
        self.config, self.report = config, report
        self.allowed = effective_tier(config, report) == 'pro'
        self.eligibility.setText('Pro tier available. Download or verify the model, enable Command and Save Settings.'
            if self.allowed else 'Needs Pro tier: Command uses a larger local editing model. '
            'Check performance or select Pro in Models before using it.')
        self.enabled_check.setEnabled(self.allowed)
        self.backend.setEnabled(self.task is None)
        self.download_button.setEnabled(self.allowed and self.task is None)
        self.pause_button.setEnabled(self.task is not None)
        self._details()

    def _backend(self):
        staged = {**self.config, 'command': {'backend': self.backend.currentData()}}
        return command_choice(staged, self.report).backend

    def _details(self):
        package = command_bundle(self._backend())
        size = sum(transfer_bytes(model) for model in package) / 1e6
        rows = [f'{size:,.1f} MB total download · Qwen3.5 4B model and processor files']
        color = self.license.palette().color(QtGui.QPalette.WindowText).name()
        for model in package:
            license = model['license'] if 'license' in model['license'].lower() else model['license'] + ' license'
            rows.append(f'{escape(model["publisher"])} · '
                f'<a style="color:{color}" href="{escape(model["license_url"])}">{escape(license)}</a> · '
                f'<a style="color:{color}" href="{escape(model["source"])}">Source and credits</a>')
        self.license.setText('<br>'.join(rows))

    def eventFilter(self, watched, event):
        if watched is self.license and event.type() in (QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange):
            self._palette_timer.start(0)
        return super().eventFilter(watched, event)

    def apply_to(self, config):
        config.setdefault('labs', {})['command_mode'] = self.enabled_check.isChecked()
        config.setdefault('command', {})['backend'] = self.backend.currentData()

    def start_download(self):
        if not self.allowed or self.task is not None:
            return
        backend = self._backend()
        task = self.task = DownloadTask(self)
        self.update_eligibility(self.config, self.report)
        self.progress.setValue(0)
        self.status.setText('Downloading or verifying the chosen Command model and processor…')
        task.progress.connect(self.progress.setValue)
        task.succeeded.connect(self._succeeded)
        task.failed.connect(self._failed)
        task.paused.connect(self.status.setText)
        task.finished.connect(self._finished)
        task.start(lambda progress: call_download(self.callback, backend, progress, pause_event=task.pause_event))

    def _succeeded(self, path):
        if not path or Path(path).suffix.casefold() != '.gguf' or not Path(path).is_file():
            self.status.setText('Command setup did not return a usable model. Choose Download / Resume to retry.')
            return
        self.progress.setValue(100)
        self.status.setText('Command model and processor verified. Enable Command and Save Settings to use them.')

    def _failed(self, error):
        self.status.setText(f'Command setup failed: {error}. Choose Download / Resume to retry.')

    def _finished(self):
        self.task = None
        self.update_eligibility(self.config, self.report)
        self.finished.emit()

    def pause(self):
        if self.task is not None:
            self.task.pause()
            self.pause_button.setEnabled(False)
            self.status.setText('Pausing Command download…')
