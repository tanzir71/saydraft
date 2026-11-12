"""Model choices and attribution shared by setup and Settings."""

from html import escape

from PySide6 import QtCore, QtWidgets

from saydraft.asr.selection import configured_model_id
from saydraft.model_download import download_asr_model
from saydraft.models.manifest import get_model, load_manifest, model_bundle
from .download_task import DownloadTask, call_download


class ModelPicker(QtWidgets.QWidget):
    busy_changed = QtCore.Signal(bool)

    def __init__(self, config, *, callback=None, parent=None):
        super().__init__(parent)
        self.callback = callback or download_asr_model
        self.task = None
        self.combo = QtWidgets.QComboBox()
        models = [model for model in load_manifest()["models"] if model.get("role", "asr") == "asr"]
        models.sort(key=lambda model: (model["engine"] != "parakeet", model["id"].replace("-v3-", "-v1-")))
        for model in models:
            label = (model["label"] if model["engine"] == "parakeet" or
                     model.get("model_size") == "large-v3-turbo" else model["model_size"])
            self.combo.addItem(label, model["id"])
        selected = configured_model_id(config)
        index = self.combo.findData(selected)
        if index < 0:  # Keep a custom legacy cache/path preference; no unpinned download offered.
            self.combo.addItem(config["stt"]["model_size"], selected)
            index = self.combo.count() - 1
        self.combo.setCurrentIndex(index)
        self.license_label = QtWidgets.QLabel()
        self.license_label.setWordWrap(True)
        self.license_label.setOpenExternalLinks(True)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.download_button = QtWidgets.QPushButton("Download / Resume")
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.setEnabled(False)
        self.download_button.clicked.connect(self.start_download)
        self.pause_button.clicked.connect(self.pause)
        self.combo.currentIndexChanged.connect(self.update_license)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.download_button)
        buttons.addWidget(self.pause_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.combo)
        layout.addWidget(self.license_label)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        self.update_license()

    @property
    def model_id(self):
        return self.combo.currentData()

    def update_license(self):
        try:
            model = get_model(self.model_id)
        except ValueError:
            self.license_label.setText("Existing local model. Choose a listed model to download verified files.")
            self.download_button.setEnabled(False)
            return
        package = model_bundle(self.model_id)
        size = sum(file["size"] for item in package for file in item["files"]) / 1_000_000
        label = (f'{escape(model["publisher"])} · {size:.1f} MB · '
                 f'<a href="{escape(model["license_url"])}">{escape(model["license"])} license</a>')
        for dependency in package[1:]:
            label += (f'<br>Includes {escape(dependency["label"])} · {escape(dependency["publisher"])} · '
                      f'<a href="{escape(dependency["license_url"])}">{escape(dependency["license"])} license</a>')
        self.license_label.setText(label)
        self.license_label.setAccessibleName("; ".join(
            f'{item["publisher"]}, {item["license"]}' for item in package) + f'; {size:.1f} megabytes total')
        self.download_button.setEnabled(self.task is None)

    def start_download(self):
        if self.task is not None:
            return
        try:
            get_model(self.model_id)
        except ValueError:
            self.status.setText("No pinned download is available for this local model.")
            return
        task = DownloadTask(self)
        self.task = task
        self.busy_changed.emit(True)
        self.combo.setEnabled(False)
        self.download_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText("Downloading verified model files…")
        task.progress.connect(self.progress.setValue)
        task.succeeded.connect(self._succeeded)
        task.failed.connect(self._failed)
        task.paused.connect(self.status.setText)
        task.finished.connect(self._finished)
        # Preserve the original Whisper-size callback contract for integrations.
        argument = self.model_id.removeprefix("whisper-")
        task.start(lambda progress: call_download(self.callback, argument, progress,
                                                  pause_event=task.pause_event))

    @QtCore.Slot(str)
    def _succeeded(self, path):
        self.progress.setValue(100)
        self.status.setText("Model ready. Apply Settings or finish setup to use it.")

    @QtCore.Slot(str)
    def _failed(self, error):
        self.status.setText(f"Could not download model: {error}. Choose Download / Resume to retry.")

    @QtCore.Slot()
    def _finished(self):
        self.task = None
        self.busy_changed.emit(False)
        self.combo.setEnabled(True)
        self.download_button.setEnabled(True)
        self.pause_button.setEnabled(False)

    def pause(self):
        if self.task is not None:
            self.task.pause()
            self.pause_button.setEnabled(False)
            self.status.setText("Pausing download…")
