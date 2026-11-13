"""Explicit licensed cleanup model/runtime setup; applying Settings stays separate."""

from html import escape
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from saydraft.config import default_config
from saydraft.model_download import download_cleanup_runtime
from saydraft.models.cleanup import cleanup_bundle, download_cleanup_model, recommend_cleanup, transfer_bytes
from saydraft.models.manifest import get_model, load_manifest
from saydraft.models.runtime_ids import runtime_model_id
from .download_task import DownloadTask, call_download
from .progress import ThemedProgressBar


class CleanupPicker(QtWidgets.QWidget):
    ready = QtCore.Signal(str, str)
    finished = QtCore.Signal()

    def __init__(self, config, *, callback=None, runtime_callback=None, report=None, parent=None):
        super().__init__(parent)
        self.callback, self.task = callback or download_cleanup_model, None
        self.runtime_callback = runtime_callback or download_cleanup_runtime
        self.combo = QtWidgets.QComboBox()
        self.combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.combo.setMinimumContentsLength(20)
        self.combo.setAccessibleName("AI cleanup model")
        self.combo.addItem("Custom GGUF path", None)
        for model in load_manifest()["models"]:
            if model.get("role") == "llm":
                self.combo.addItem(model["label"], model["id"])
        self.backend = QtWidgets.QComboBox()
        self.backend.setAccessibleName("AI cleanup processor")
        self.backend.addItem("CPU", "cpu")
        self.backend.addItem("GPU (Vulkan)", "vulkan")
        llm = config["llm"]
        suggested = recommend_cleanup(report, config)
        fresh = (not llm["enabled"] and llm["model_path"] == default_config()["llm"]["model_path"]
                 and config.get("app", {}).get("tier", "auto") == "auto")
        if fresh and suggested["model_id"]:
            self.combo.setCurrentIndex(self.combo.findData(suggested["model_id"]))
        backend = suggested["backend"] if fresh and suggested["model_id"] else llm.get("backend", "cpu")
        self.backend.setCurrentIndex(max(0, self.backend.findData(backend)))
        self.recommendation = QtWidgets.QLabel()
        self.recommendation.setWordWrap(True)
        self.recommendation.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.license_label = QtWidgets.QLabel()
        self.license_label.setWordWrap(True)
        self.license_label.setOpenExternalLinks(True)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.progress = ThemedProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setAccessibleName("Cleanup model and runtime download progress")
        self.download_button = QtWidgets.QPushButton("Download / Resume AI cleanup")
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.setEnabled(False)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.download_button)
        buttons.addWidget(self.pause_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self.recommendation, self.combo, self.backend, self.license_label):
            layout.addWidget(widget)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        self.combo.currentIndexChanged.connect(self.update_details)
        self.backend.currentIndexChanged.connect(self.update_details)
        self.download_button.clicked.connect(self.start_download)
        self.pause_button.clicked.connect(self.pause)
        self.refresh_recommendation(report, config)
        self.update_details()

    def refresh_recommendation(self, report, config=None):
        suggestion = recommend_cleanup(report, config)
        if suggestion["model_id"]:
            model = get_model(suggestion["model_id"])
            prefix = "Tier defaults" if (config or {}).get("app", {}).get("tier", "auto") != "auto" else "Performance recommendation"
            self.recommendation.setText(f"{prefix}: {suggestion['tier'].title()} · {model['label']}. "
                                        "Download or verify the package, then enable AI cleanup and Apply Settings.")
        else:
            self.recommendation.setText("Rules-only recommendation." if suggestion["tier"] == "lite" else
                                        "Run Check performance for a recommendation. No model is selected automatically.")

    def update_details(self):
        model_id = self.combo.currentData()
        self.download_button.setEnabled(self.task is None)
        self.download_button.setText("Download / Resume")
        self.download_button.setAccessibleName("Download or resume AI cleanup model and processor files" if model_id else
                                              "Download or resume processor files for a custom GGUF")
        package = (cleanup_bundle(model_id, self.backend.currentData()) if model_id else
                   [get_model(runtime_model_id(self.backend.currentData()))])
        size = sum(transfer_bytes(model) for model in package) / 1e6
        rows = [f"{size:.1f} MB total download · " + ("model and processor support files" if model_id else
                "processor files only; keep your custom GGUF path below")]
        for model in package:
            rows.append(f'{escape(model["publisher"])} · '
                f'<a href="{escape(model["license_url"])}">{escape(model["license"])} license</a> · '
                f'<a href="{escape(model["source"])}">Source and credits</a>')
        self.license_label.setText("<br>".join(rows))
        self.license_label.setAccessibleName(f"{size:.1f} megabytes total; " + "; ".join(
            model["publisher"] + ", " + model["license"] for model in package))

    def start_download(self):
        model_id, backend = self.combo.currentData(), self.backend.currentData()
        if self.task is not None:
            return
        task = self.task = DownloadTask(self)
        self._download_backend = backend
        self._download_model = model_id
        self.combo.setEnabled(False)
        self.backend.setEnabled(False)
        self.download_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText("Downloading or verifying the chosen model and processor files…")
        task.progress.connect(self.progress.setValue)
        task.succeeded.connect(self._succeeded)
        task.failed.connect(self._failed)
        task.paused.connect(self.status.setText)
        task.finished.connect(self._finished)
        callback, args = ((self.callback, (model_id, backend)) if model_id else (self.runtime_callback, (backend,)))
        task.start(lambda progress: call_download(callback, *args, progress, pause_event=task.pause_event))

    @QtCore.Slot(str)
    def _succeeded(self, path):
        if self._download_model is None:
            if not path or not Path(path).is_dir():
                self.status.setText("Processor setup failed. Choose Download / Resume to retry.")
                return
            self.progress.setValue(100)
            self.status.setText("Processor files verified. Keep your GGUF path, enable AI cleanup and Apply Settings.")
            return
        if not path or Path(path).suffix.casefold() != ".gguf" or not Path(path).is_file():
            self.status.setText("Setup did not return a usable model. Choose Download / Resume to retry.")
            return
        self.progress.setValue(100)
        self.ready.emit(path, self._download_backend)
        self.status.setText("Model and processor files verified. Enable AI cleanup and Apply Settings to use them.")

    @QtCore.Slot(str)
    def _failed(self, error):
        self.status.setText(f"Could not set up cleanup: {error}. Choose Download / Resume to retry.")

    @QtCore.Slot()
    def _finished(self):
        self.task = None
        self.combo.setEnabled(True)
        self.backend.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.update_details()
        self.finished.emit()

    def pause(self):
        if self.task is not None:
            self.task.pause()
            self.pause_button.setEnabled(False)
            self.status.setText("Pausing download…")
