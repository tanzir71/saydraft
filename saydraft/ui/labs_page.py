"""Explicit optional preview setup; toggles never start a download."""

from html import escape

from PySide6 import QtCore, QtWidgets

from saydraft.asr.model_ids import PREVIEW_MODEL
from saydraft.core.preview import preview_eligibility
from saydraft.model_download import download_preview_model
from saydraft.models.hardware import latest_report
from saydraft.models.manifest import get_model
from .download_task import DownloadTask, call_download
from .progress import ThemedProgressBar
from .command_setup import CommandSetup


class LabsPage(QtWidgets.QWidget):
    def __init__(self, config, *, callback=None, report_loader=latest_report):
        super().__init__()
        self.callback = callback or download_preview_model
        self.report_loader = report_loader
        self.task = None
        self.config = config
        model = get_model(PREVIEW_MODEL)
        size = model["archive"]["size"] / 1_000_000
        storage = (model["archive"]["size"] + sum(f["size"] for f in model["files"]) + 64 * 1024**2) / 1e9
        self.description = QtWidgets.QLabel(
            "English live preview (experimental) shows partial words above the Bar. "
            "Requires the Pro tier. Default recognition still produces the final text.")
        self.description.setWordWrap(True)
        self.license = QtWidgets.QLabel(
            f'{escape(model["publisher"])} · {size:.1f} MB download · allow {storage:.2f} GB free space<br>'
            f'<a href="{escape(model["license_url"])}">{escape(model["license"])} license</a> · '
            f'<a href="{escape(model["source"])}">Model and conversion credits</a>')
        self.license.setWordWrap(True)
        self.license.setOpenExternalLinks(True)
        self.eligibility = QtWidgets.QLabel()
        self.eligibility.setWordWrap(True)
        self.live = QtWidgets.QCheckBox("Show English live preview")
        self.streaming = QtWidgets.QCheckBox("Use streaming result")
        self.streaming.setToolTip("Uses a complete streaming result after release. Default-ASR words remain in History metadata.")
        self.live.setChecked(config.get("labs", {}).get("live_preview", False))
        self.streaming.setChecked(config.get("labs", {}).get("use_streaming_result", False))
        self.live.toggled.connect(self._toggle)
        self.download = QtWidgets.QPushButton("Download / Resume English preview")
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.download.clicked.connect(self.start_download)
        self.pause_button.clicked.connect(self.pause)
        self.progress = ThemedProgressBar()
        self.progress.setRange(0, 100)
        self.status = QtWidgets.QLabel("Download once, then enable preview and Apply. Installed files are reused.")
        self.status.setWordWrap(True)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.download)
        buttons.addWidget(self.pause_button)
        layout = QtWidgets.QVBoxLayout(self)
        for widget in (self.description, self.license, self.eligibility, self.live, self.streaming):
            layout.addWidget(widget)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        self.command = CommandSetup(config, report=self.report_loader())
        layout.addWidget(self.command)
        layout.addStretch()
        self.update_eligibility(config)

    def update_eligibility(self, config, report=None):
        self.config = config
        reason = preview_eligibility(config, self.report_loader() if report is None else report)
        self.allowed = reason is None
        self.eligibility.setText({"needs_pro": "Check performance on the Performance tab or select Pro in Models; the Pro tier is required.",
            "english_only": "Choose Auto or English on the Languages tab. Preview stops if other speech is detected.",
            None: "English preview is available. Enabling it starts no download."}[reason])
        self.live.setEnabled(self.allowed)
        if not self.allowed:
            self.live.setChecked(False)
        self._toggle()
        self.download.setEnabled(self.allowed and self.task is None)
        self.pause_button.setEnabled(self.task is not None)
        self.command.update_eligibility(config, self.report_loader() if report is None else report)

    def _toggle(self):
        enabled = self.live.isChecked() and self.live.isEnabled()
        self.streaming.setEnabled(enabled)
        if not enabled:
            self.streaming.setChecked(False)

    def apply_to(self, config):
        self.update_eligibility(config)
        config.setdefault("labs", {}).update(live_preview=self.live.isChecked(),
                                             use_streaming_result=self.streaming.isChecked())
        self.command.apply_to(config)

    def start_download(self):
        self.update_eligibility(self.config)
        if not self.allowed or self.task is not None:
            return
        task = self.task = DownloadTask(self)
        self.download.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText("Downloading and verifying English preview…")
        task.progress.connect(self.progress.setValue)
        task.succeeded.connect(self._succeeded)
        task.failed.connect(self._failed)
        task.paused.connect(self.status.setText)
        task.finished.connect(self._finished)
        task.start(lambda progress: call_download(self.callback, progress, pause_event=task.pause_event))

    @QtCore.Slot(str)
    def _succeeded(self, path):
        self.status.setText("Preview model ready. Enable preview and Apply Settings to use it.")

    @QtCore.Slot(str)
    def _failed(self, error):
        self.status.setText(f"Preview download failed: {error}. Download / Resume to retry.")

    @QtCore.Slot()
    def _finished(self):
        self.task = None
        self.update_eligibility(self.config)

    def pause(self):
        self.command.pause()
        if self.task is not None:
            self.task.pause()
            self.pause_button.setEnabled(False)
            self.status.setText("Pausing preview download…")
