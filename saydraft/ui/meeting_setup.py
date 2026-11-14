"""Reviewed meeting model setup, explicit discovery and one consented Start."""

import copy
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from html import escape

from PySide6 import QtCore, QtWidgets

from saydraft.audio.devices import InputSelection
from saydraft.meetings.devices import MeetingDevices, discover_meeting_devices
from saydraft.meetings.request import CaptureRequest
from saydraft.meetings.setup import MeetingSetupInspection, download_meeting_setup, inspect_meeting_setup
from saydraft.models.hardware import latest_report
from .download_task import DownloadTask, call_download
from .progress import ThemedProgressBar


class MeetingSetupDialog(QtWidgets.QDialog):
    settings_requested = QtCore.Signal(str)
    _result = QtCore.Signal(str, int, object)

    def __init__(self, config, *, start_callback, inspector=None, devices_provider=None,
                 download_callback=None, report_loader=latest_report):
        super().__init__()
        self.setWindowTitle('Meeting notes · Saydraft Labs')
        self.resize(780, 760)
        self.setMinimumSize(460, 420)
        self.start_callback = start_callback
        self.inspector = inspector or (lambda snapshot: inspect_meeting_setup(snapshot, report=report_loader()))
        self.devices_provider = devices_provider or discover_meeting_devices
        self.download_callback = download_callback or download_meeting_setup
        self.config = copy.deepcopy(config)
        self.inspection = self.devices = self.task = None
        self._active_ui = False
        self._generation = {'models': 0, 'devices': 0}
        self._futures = {}
        self._inflight = {}
        self._check_again = False
        self._transfer_message = ''
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='Saydraft-meeting-setup')
        self._result.connect(self._accept, QtCore.Qt.QueuedConnection)
        pool = self._pool
        self.destroyed.connect(lambda *_: pool.shutdown(wait=False, cancel_futures=True))
        root = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea()
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        def paragraph(text, *, display=False):
            widget = QtWidgets.QLabel(text)
            widget.setTextFormat(QtCore.Qt.PlainText)
            widget.setWordWrap(True)
            widget.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            if display:
                widget.setProperty('role', 'display')
            layout.addWidget(widget)
            return widget
        paragraph('Meeting notes', display=True)
        paragraph('Record your microphone and selected computer audio. After you stop, Saydraft makes a local '
                  'speaker transcript and a separate Note with a reviewable summary. Speaker labels and summaries '
                  'can be wrong; review names, dates and decisions. No meeting bot joins the call.')
        self.eligibility = paragraph('Checking the saved Labs and Pro settings does not start recording or a download.')
        self.settings = QtWidgets.QPushButton('Open Notetaker settings')
        self.settings.clicked.connect(lambda: self.settings_requested.emit('Labs'))
        layout.addWidget(self.settings, alignment=QtCore.Qt.AlignLeft)
        self.models_label = paragraph('Local models')
        self.models_label.setProperty('role', 'eyebrow')
        self.model_table = QtWidgets.QTableWidget(0, 3)
        self.model_table.setHorizontalHeaderLabels(['Model', 'Download size', 'Installed'])
        self.model_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.model_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.model_table.setAccessibleName('Meeting models, sizes and verification')
        self.model_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.model_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.model_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.model_table.setMinimumHeight(180)
        layout.addWidget(self.model_table)
        self.licenses = QtWidgets.QLabel()
        self.licenses.setWordWrap(True)
        self.licenses.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.licenses.setOpenExternalLinks(True)
        self.licenses.setAccessibleName('Meeting model licenses and sources')
        layout.addWidget(self.licenses)
        self.size_note = paragraph('Check models to review the complete size and licenses before downloading.')
        paragraph('Auto uses the shared All languages model when the default model cannot confidently handle a '
                  'chunk. Language pins and manual speech choices follow Settings → Languages/Models. '
                  'There are no separate language packs. Existing verified models are reused.')
        actions = QtWidgets.QVBoxLayout()
        self.check_button = QtWidgets.QPushButton('Check models')
        self.download_button = QtWidgets.QPushButton('Download / Resume setup')
        self.pause_button = QtWidgets.QPushButton('Pause')
        for button in (self.check_button, self.download_button, self.pause_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.progress = ThemedProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setAccessibleName('Meeting model setup progress')
        layout.addWidget(self.progress)
        self.model_status = paragraph('Models are checked locally. Setup downloads happen only when you choose Download.')
        paragraph('Microphone and computer audio').setProperty('role', 'eyebrow')
        self.microphone = QtWidgets.QComboBox()
        self.output = QtWidgets.QComboBox()
        self.microphone.setAccessibleName('Meeting microphone')
        self.output.setAccessibleName('Meeting computer audio output')
        for combo in (self.microphone, self.output):
            combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(self.microphone)
        layout.addWidget(self.output)
        self.refresh = QtWidgets.QPushButton('Refresh devices')
        layout.addWidget(self.refresh, alignment=QtCore.Qt.AlignLeft)
        self.device_status = paragraph('Choose Refresh devices to list available endpoints. This opens no recording stream.')
        paragraph('Use headphones to reduce sound from the computer being recorded again by the microphone. '
                  'If you switch audio outputs, refresh and select the output used by your call.')
        self.duration = QtWidgets.QSpinBox()
        self.duration.setRange(1, 120)
        self.duration.setValue(30)
        self.duration.setSuffix(' minutes maximum')
        self.duration.setAccessibleName('Maximum meeting recording duration')
        layout.addWidget(self.duration)
        paragraph('Meeting audio stays in memory for processing/retry and is not archived to disk. '
                  'The resulting transcript and summary are saved in Notes. Close this window to cancel setup; '
                  'recording starts only with the button below and a visible recording indicator.')
        self.consent = QtWidgets.QCheckBox('I have informed the participants\nand have permission to record.')
        layout.addWidget(self.consent)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        root.addWidget(self.status)
        footer = QtWidgets.QHBoxLayout()
        self.close_button = QtWidgets.QPushButton('Close')
        self.start_button = QtWidgets.QPushButton('Start meeting')
        self.start_button.setAutoDefault(False)
        self.start_button.setProperty('primary', True)
        footer.addStretch()
        footer.addWidget(self.close_button)
        footer.addWidget(self.start_button)
        root.addLayout(footer)
        self.close_button.clicked.connect(self.close)
        self.check_button.clicked.connect(self.check_models)
        self.refresh.clicked.connect(self.refresh_devices)
        self.download_button.clicked.connect(self.download)
        self.pause_button.clicked.connect(self.pause)
        self.start_button.clicked.connect(self.start)
        for combo in (self.microphone, self.output):
            combo.currentIndexChanged.connect(self._selection_changed)
        self.consent.toggled.connect(self._buttons)
        self._clear_devices()
        self._buttons()

    def _clear_devices(self):
        for combo, text in ((self.microphone, 'Refresh devices and choose a microphone'),
                            (self.output, 'Refresh devices and choose computer audio')):
            combo.clear()
            combo.addItem(text, None)

    def _selection_changed(self, *_):
        self.consent.setChecked(False)
        self._buttons()

    def set_config(self, config):
        if config == self.config:
            return
        self.config = copy.deepcopy(config)
        self.inspection = None
        self.consent.setChecked(False)
        self._generation['models'] += 1
        self.pause()
        self._transfer_message = ''
        self.model_status.setText('Settings changed. Check the current model setup again.')
        if self._active_ui:
            self.check_models()
        self._buttons()

    def _submit(self, kind, action):
        if kind in self._inflight:
            if kind == 'models':
                self._check_again = True
            return False
        self._generation[kind] += 1
        generation = self._generation[kind]
        self._inflight[kind] = generation
        def run():
            try:
                result = action()
            except Exception:
                result = None
            try:
                self._result.emit(kind, generation, result)
            except RuntimeError:
                pass
        try:
            self._futures[kind] = self._pool.submit(run)
        except RuntimeError:
            self._inflight.pop(kind, None)
            return False
        self._buttons()
        return True

    def check_models(self):
        if not self._active_ui or self.task is not None:
            return False
        self.inspection = None
        snapshot = copy.deepcopy(self.config)
        self.model_status.setText('Checking the model files and licenses…')
        return self._submit('models', lambda: self.inspector(snapshot))

    def refresh_devices(self):
        if not self._active_ui or self.task is not None:
            return False
        self.devices = None
        self.consent.setChecked(False)
        self.device_status.setText('Checking available microphones and computer audio outputs…')
        return self._submit('devices', self.devices_provider)

    @QtCore.Slot(str, int, object)
    def _accept(self, kind, generation, result):
        if self._inflight.get(kind) == generation:
            self._inflight.pop(kind, None)
            self._futures.pop(kind, None)
        if generation != self._generation[kind] or not self._active_ui:
            if kind == 'models' and self._active_ui and self._check_again:
                self._check_again = False
                QtCore.QTimer.singleShot(0, self.check_models)
            self._buttons()
            return
        if kind == 'models':
            self._check_again = False
            if type(result) is MeetingSetupInspection:
                self.inspection = result
                try:
                    self._render_models()
                except (KeyError, TypeError, ValueError):
                    self.inspection = None
                    self.model_status.setText('The model plan changed. Check models to review it again.')
            else:
                self.model_status.setText('Could not verify the meeting models. Check models to retry.')
        elif kind == 'devices':
            if type(result) is MeetingDevices:
                self.devices = result
                self._clear_devices()
                saved = InputSelection.from_config(self.config)
                for microphone in result.microphones:
                    self.microphone.addItem(f'{microphone.name} · {microphone.hostapi}', microphone)
                    if microphone.key == saved.key:
                        self.microphone.setCurrentIndex(self.microphone.count() - 1)
                names = Counter(item.name for item in result.outputs)
                for index, output in enumerate(result.outputs, 1):
                    label = output.name + (f' (output {index})' if names[output.name] > 1 else '')
                    if not output.supported:
                        label += ' · unsupported loopback'
                    self.output.addItem(label, output)
                self.device_status.setText('Choose both endpoints. The exact selected output is used; recording has not started.')
            else:
                self.device_status.setText('Could not list devices. Check Windows audio settings and choose Refresh devices to retry.')
        self._buttons()

    def _render_models(self):
        result = self.inspection
        models = result.plan.models()
        self.model_table.setRowCount(len(models))
        links = []
        for index, (model, installed) in enumerate(zip(models, result.installed)):
            size = model['archive']['size'] if 'archive' in model else sum(item['size'] for item in model['files'] if 'url' in item)
            for column, value in enumerate((model.get('label', model['id']), f'{size / 1e6:.1f} MB',
                                             'Verified' if installed else 'Needs setup')):
                item = QtWidgets.QTableWidgetItem(value)
                item.setToolTip(value)
                self.model_table.setItem(index, column, item)
            links.append(f'{escape(model.get("label", model["id"]))}: {escape(model["publisher"])} · '
                         f'<a href="{escape(model["license_url"])}">{escape(model["license"])}</a> · '
                         f'<a href="{escape(model["source"])}">Source</a>')
        self.licenses.setText('<br>'.join(links))
        self.model_table.resizeRowsToContents()
        self.size_note.setText(f'Up to {result.plan.download_bytes / 1e9:.2f} GB to download; '
                              f'allow {result.plan.space_bytes / 1e9:.2f} GB free for setup. Verified files are reused.')
        enabled = self.config.get('labs', {}).get('notetaker') is True
        self.eligibility.setText('Meeting summaries require Pro. Select Pro or check performance in Settings.'
            if result.plan.reason != 'ready' else 'Enable Notetaker in Settings → Labs, then Save Settings.'
            if not enabled else 'Notetaker is enabled. Review the devices and participant permission before Start.')
        self.model_status.setText(self._transfer_message or (
            'All meeting models are verified and ready to use offline.' if result.ready else
            'Review the complete size and licenses, then choose Download / Resume setup.'))

    def _buttons(self, *_):
        checking = bool(self._inflight)
        idle = self._active_ui and self.task is None and not checking
        ready = self.inspection is not None and self.inspection.ready
        output, microphone = self.output.currentData(), self.microphone.currentData()
        self.start_button.setEnabled(bool(idle and ready and self.config.get('labs', {}).get('notetaker') is True
            and self.devices is not None and type(microphone) is InputSelection and output is not None
            and output.supported and self.consent.isChecked()))
        self.check_button.setEnabled(self._active_ui and self.task is None and not checking)
        self.refresh.setEnabled(self._active_ui and self.task is None and not checking)
        self.download_button.setEnabled(bool(idle and self.inspection is not None and self.inspection.plan.reason == 'ready'))
        self.pause_button.setEnabled(self.task is not None and not self.task.pause_event.is_set())

    def download(self):
        if not self.download_button.isEnabled() or self.inspection is None:
            return False
        plan = self.inspection.plan
        self._transfer_message = ''
        self.inspection = None
        self.consent.setChecked(False)
        task = self.task = DownloadTask(self)
        self.progress.setValue(0)
        self.model_status.setText('Downloading and verifying the reviewed meeting setup…')
        task.progress.connect(self.progress.setValue)
        task.failed.connect(self._transfer_failed)
        task.paused.connect(lambda _: self._transfer_failed('Setup paused. Choose Resume to continue.'))
        task.finished.connect(lambda: self._download_finished(task))
        self._buttons()
        try:
            task.start(lambda progress: call_download(self.download_callback, plan, progress, pause_event=task.pause_event))
        except Exception:
            self.task = None
            self.model_status.setText('Could not start setup. Check models and retry.')
            self._buttons()
            return False
        return True

    def _transfer_failed(self, message):
        self._transfer_message = message
        self.model_status.setText(message)

    def _download_finished(self, task):
        if self.task is not task:
            return
        self.task = None
        if self._active_ui:
            self.check_models()  # A transfer callback cannot certify installed files.
        self._buttons()

    def pause(self):
        if self.task is not None:
            self.task.pause()
            self._buttons()

    def start(self):
        if not self.start_button.isEnabled():
            return False
        output = self.output.currentData()
        request = CaptureRequest(True, self.microphone.currentData(), output.endpoint_id, self.duration.value() * 60)
        self.start_button.setEnabled(False)
        self.consent.setChecked(False)
        try:
            accepted = self.start_callback(request, expected_config=copy.deepcopy(self.config)) is True
        except Exception:
            accepted = False
        if not accepted:
            self.status.setText('Recording did not start. Finish other work, check the current Settings and try again.')
            self._buttons()
            return False
        self.close()
        return True

    def showEvent(self, event):
        super().showEvent(event)
        if self.screen() is not None:
            available = self.screen().availableGeometry()
            self.resize(min(self.width(), max(self.minimumWidth(), available.width() - 32)),
                        min(self.height(), max(self.minimumHeight(), available.height() - 32)))
        self._active_ui = True
        self.check_models()
        self._buttons()

    def hideEvent(self, event):
        self._active_ui = False
        self.consent.setChecked(False)
        self.inspection = self.devices = None
        for kind in self._generation:
            self._generation[kind] += 1
        self._check_again = False
        self.pause()
        self._buttons()
        super().hideEvent(event)
