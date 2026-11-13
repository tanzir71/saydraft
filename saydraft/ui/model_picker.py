"""Model choices and attribution shared by setup and Settings."""

from html import escape

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.asr.selection import configured_model_id
from saydraft.model_download import download_asr_model
from saydraft.models.manifest import get_model, load_manifest, model_bundle
from saydraft.models.progress import FileProgress
from .download_task import DownloadTask, call_download
from .progress import ThemedProgressBar


class ModelPicker(QtWidgets.QWidget):
    busy_changed = QtCore.Signal(bool)

    def __init__(self, config, *, callback=None, success_message=None, parent=None):
        super().__init__(parent)
        self.callback = callback or download_asr_model
        self.success_message = success_message or "Model ready. Apply Settings or finish setup to use it."
        self.task = None
        self.combo = QtWidgets.QComboBox()
        self.combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.combo.setMinimumContentsLength(20)
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
        self.license_label.setTextInteractionFlags(QtCore.Qt.LinksAccessibleByMouse | QtCore.Qt.LinksAccessibleByKeyboard)
        self.progress = ThemedProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setAccessibleName("Model package download progress")
        self.status = QtWidgets.QLabel("")
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        self.file_status = QtWidgets.QLabel("")
        self.file_status.setTextFormat(QtCore.Qt.PlainText)
        self.file_status.setWordWrap(True)
        self.file_status.setAccessibleName("Current model file and verification progress")
        policy = self.file_status.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
        self.file_status.setSizePolicy(policy)
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
        layout.addWidget(self.file_status)
        layout.addWidget(self.status)
        self.license_timer = QtCore.QTimer(self)
        self.license_timer.setSingleShot(True)
        self.license_timer.timeout.connect(self._render_license)
        self.update_license()

    @property
    def model_id(self):
        return self.combo.currentData()

    def update_license(self):
        self.file_status.clear()
        self.file_status.hide()
        if self.task is None:
            self.progress.reset()
            self.progress.hide()
            self.status.clear()
        self._package = {}
        try:
            get_model(self.model_id)
        except ValueError:
            self.license_label.setText("Existing local model. Choose a listed model to download verified files.")
            self.download_button.setEnabled(False)
            return
        package = model_bundle(self.model_id)
        self._package = {item["id"]: item for item in package}
        size = sum(file["size"] for item in package for file in item["files"]) / 1_000_000
        self._render_license()
        self.license_label.setAccessibleName("; ".join(
            f'{item["publisher"]}, {item["license"]}' for item in package) + f'; {size:.1f} megabytes total')
        self.download_button.setEnabled(self.task is None)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange) and hasattr(self, "license_timer"):
            self.license_timer.start(0)

    def _render_license(self):
        if not self._package:
            return
        model = self._package[self.model_id]
        package = list(self._package.values())
        size = sum(file["size"] for item in package for file in item["files"]) / 1_000_000
        color = self.license_label.palette().color(QtGui.QPalette.WindowText).name()
        label = (f'{escape(model["publisher"])} · {size:.1f} MB · '
                 f'<a style="color:{color}" href="{escape(model["license_url"])}">{escape(model["license"])} license</a>')
        for dependency in package[1:]:
            label += (f'<br>Includes {escape(dependency["label"])} · {escape(dependency["publisher"])} · '
                      f'<a style="color:{color}" href="{escape(dependency["license_url"])}">{escape(dependency["license"])} license</a>')
        self.license_label.setText(label)

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
        self.progress.show()
        self.file_status.clear()
        self.file_status.hide()
        self.status.setText("Downloading verified model files…")
        task.progress.connect(self.progress.setValue)
        task.file_progress.connect(self._file_progress)
        task.succeeded.connect(self._succeeded)
        task.failed.connect(self._failed)
        task.paused.connect(self.status.setText)
        task.finished.connect(self._finished)
        # Preserve the original Whisper-size callback contract for integrations.
        argument = self.model_id.removeprefix("whisper-")
        task.start(lambda progress: call_download(self.callback, argument, progress,
            pause_event=task.pause_event, file_progress_callback=task.file_progress.emit))

    @QtCore.Slot(object)
    def _file_progress(self, update):
        if not isinstance(update, FileProgress) or self.task is None:
            return
        package = self._package
        if update.model_id not in package:
            return
        model = package[update.model_id]
        if not any(file["path"] == update.filename and file["size"] == update.total_bytes for file in model["files"]):
            return
        phase = {"checking": "Checking installed file", "downloading": "Downloading",
                 "verifying": "Verifying SHA-256", "verified": "SHA-256 verified"}[update.phase]
        self.file_status.setText(f'{model["label"]} · {update.filename}\n{phase} · '
            f'{update.completed_bytes / 1_000_000:.1f} / {update.total_bytes / 1_000_000:.1f} MB')
        self.file_status.show()

    @QtCore.Slot(str)
    def _succeeded(self, path):
        self.progress.setValue(100)
        self.status.setText(self.success_message)

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
