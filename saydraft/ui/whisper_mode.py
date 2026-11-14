"""Staged quiet-speech controls and explicit, licensed enhancement setup."""

from html import escape

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.audio.gtcrn import MODEL_ID
from saydraft.audio.quiet import QuietSpeechSettings
from saydraft.model_download import download_speech_enhancement, find_installed_model
from saydraft.models.manifest import get_model
from .download_task import DownloadTask, call_download
from .progress import ThemedProgressBar


class WhisperModeControls(QtWidgets.QGroupBox):
    finished = QtCore.Signal()

    def __init__(self, config, *, callback=None, ready_provider=None, parent=None):
        super().__init__('Whisper mode · quiet speech', parent)
        self.callback = callback or download_speech_enhancement
        self.ready_provider = ready_provider or (lambda: find_installed_model(MODEL_ID, check_hashes=True))
        self.task = None
        self._download_completed = False
        settings = QuietSpeechSettings.from_config(config)
        self.enabled = QtWidgets.QCheckBox('Enable Whisper mode (experimental)')
        self.enabled.setChecked(settings.enabled)
        self.gain = QtWidgets.QDoubleSpinBox()
        self.gain.setRange(0, 24)
        self.gain.setDecimals(1)
        self.gain.setSuffix(' dB')
        self.gain.setValue(settings.gain_db)
        self.gain.setAccessibleName('Whisper-mode input gain')
        self.agc = QtWidgets.QCheckBox('Automatic gain control')
        self.agc.setChecked(settings.agc)
        self.enhancement = QtWidgets.QCheckBox('Use local speech enhancement')
        self.enhancement.setChecked(settings.enhancement)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.enabled)
        gain_row = QtWidgets.QFormLayout()
        gain_row.addRow('Input gain', self.gain)
        layout.addLayout(gain_row)
        layout.addWidget(self.agc)
        layout.addWidget(self.enhancement)
        note = QtWidgets.QLabel('Boosts quiet speech before final recognition and uses more sensitive speech detection. '
            'It works with your selected speech language; it does not select the Whisper speech model. '
            'The input test and live partial preview show the original signal; final text uses the enhanced primary model. '
            'Accuracy for whispered speech still needs evaluation.')
        note.setWordWrap(True)
        note.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(note)
        license_label = self.license_label = QtWidgets.QLabel()
        license_label.setWordWrap(True)
        license_label.setOpenExternalLinks(True)
        license_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self._palette_timer = QtCore.QTimer(self)
        self._palette_timer.setSingleShot(True)
        self._palette_timer.timeout.connect(self._render_license)
        license_label.installEventFilter(self)
        self._render_license()
        layout.addWidget(license_label)
        actions = QtWidgets.QHBoxLayout()
        self.download = QtWidgets.QPushButton('Download / Resume enhancement')
        self.pause_button = QtWidgets.QPushButton('Pause')
        actions.addWidget(self.download)
        actions.addWidget(self.pause_button)
        layout.addLayout(actions)
        self.progress = ThemedProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(self.status)
        self.enabled.toggled.connect(self._controls)
        self.download.clicked.connect(self.start_download)
        self.pause_button.clicked.connect(self.pause)
        self._controls()
        self.refresh_status()

    def _render_license(self):
        model = get_model(MODEL_ID)
        size = sum(file['size'] for file in model['files']) / 1_000_000
        color = self.license_label.palette().color(QtGui.QPalette.WindowText).name()
        self.license_label.setText(f'{escape(model["publisher"])} · {size:.2f} MB · '
            f'<a style="color:{color}" href="{escape(model["license_url"])}">{escape(model["license"])} license</a> · '
            f'<a style="color:{color}" href="{escape(model["source"])}">Model source</a>')

    def eventFilter(self, watched, event):
        if watched is self.license_label and event.type() in (QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange):
            self._palette_timer.start(0)
        return super().eventFilter(watched, event)

    def _controls(self):
        for widget in (self.gain, self.agc, self.enhancement):
            widget.setEnabled(self.enabled.isChecked())
        self.download.setEnabled(self.task is None)
        self.pause_button.setEnabled(self.task is not None)

    def ready(self):
        try:
            return bool(self.ready_provider())
        except (OSError, ValueError):
            return False

    def refresh_status(self):
        self._controls()
        self.status.setText('Enhancement files verified. Save changes to apply your choices.' if self.ready() else
            'Download enhancement once, or turn enhancement off to use gain and AGC alone. '
            'Enabling this mode never downloads or records. Installed files are reused.')

    def apply_to(self, config):
        config['recording'].update(whisper_mode=self.enabled.isChecked(), whisper_gain_db=self.gain.value(),
            whisper_agc=self.agc.isChecked(), whisper_enhancement=self.enhancement.isChecked())

    def validate(self):
        if self.enabled.isChecked() and self.enhancement.isChecked() and not self.ready():
            raise ValueError('Set up enhancement in Microphone or turn it off.')

    def start_download(self):
        if self.task is not None:
            return
        task = self.task = DownloadTask(self)
        self._download_completed = False
        self._controls()
        self.progress.setValue(0)
        self.status.setText('Downloading and verifying speech enhancement…')
        task.progress.connect(self.progress.setValue)
        task.succeeded.connect(self._succeeded)
        task.failed.connect(self._failed)
        task.paused.connect(self.status.setText)
        task.finished.connect(self._finished)
        task.start(lambda progress: call_download(self.callback, progress, pause_event=task.pause_event))

    @QtCore.Slot(str)
    def _succeeded(self, _path):
        self._download_completed = True
        self.status.setText('Verifying installed enhancement files…')

    @QtCore.Slot(str)
    def _failed(self, message):
        self.status.setText('Enhancement setup failed: ' + message)

    @QtCore.Slot()
    def _finished(self):
        self.task = None
        self._controls()
        if self.ready():
            self.status.setText('Enhancement files verified. Save changes to apply your choices.')
        elif self._download_completed:
            self.status.setText('Enhancement files are incomplete or changed. Download / Resume to recheck them.')
        self.finished.emit()

    def pause(self):
        if self.task is not None:
            self.task.pause()
            self.pause_button.setEnabled(False)
            self.status.setText('Pausing enhancement download…')
