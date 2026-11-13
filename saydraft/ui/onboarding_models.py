"""First-run model choices, explicit PC checks and asynchronous package verification."""

from concurrent.futures import ThreadPoolExecutor

from PySide6 import QtCore, QtWidgets

from saydraft.models.hardware import probe_hardware
from saydraft.models.manifest import get_model
from saydraft.models.setup import capability_recommendation, inspect_speech_package
from .model_picker import ModelPicker


class OnboardingModelsPage(QtWidgets.QWizardPage):
    checked = QtCore.Signal(object, object)

    def __init__(self, config, *, download_callback=None, hardware_probe=None, status_provider=None):
        super().__init__()
        self.setTitle("Set up models")
        self.probe = hardware_probe or probe_hardware
        self.inspect = status_provider or inspect_speech_package
        self._pool = self._future = self._active = None
        self._pending = {}
        self._generations = {"hardware": 0, "installed": 0}
        self._serial = 0
        self._closed = False
        self._candidate = None
        self.readiness_state = "unknown"
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)

        def paragraph(text, name="", container=layout):
            label = QtWidgets.QLabel(text)
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            label.setAccessibleName(name)
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
            label.setSizePolicy(policy)
            container.addWidget(label)
            return label

        paragraph("Check this PC for a starting model, then review its size and license. "
                  "Download / Resume starts setup.")
        self.hardware_button = QtWidgets.QPushButton("Check this PC")
        self.use_button = QtWidgets.QPushButton("Use speech recommendation")
        self.use_button.setEnabled(False)
        actions = QtWidgets.QHBoxLayout()
        actions.addWidget(self.hardware_button)
        actions.addWidget(self.use_button)
        layout.addLayout(actions)
        self.recommendation = paragraph("PC capabilities have not been checked.", "PC setup recommendation")
        self.details_toggle = QtWidgets.QToolButton()
        self.details_toggle.setText("PC details")
        self.details_toggle.setAccessibleName("PC recommendation details")
        self.details_toggle.setCheckable(True)
        self.details_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.details_toggle.setArrowType(QtCore.Qt.RightArrow)
        layout.addWidget(self.details_toggle)
        self.details = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(self.details)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.hardware_details = paragraph("", "PC capability details", detail_layout)
        paragraph("Capability recommendations are provisional. After installation, measure speed in "
                  "Hub → Settings → Performance. This check does not change your saved tier or enable AI cleanup.",
                  container=detail_layout)
        layout.addWidget(self.details)
        self.details.hide()
        self.details_toggle.toggled.connect(self._toggle_details)
        self.picker = ModelPicker(config, callback=download_callback,
            success_message="Transfer complete. Installed files are checked separately below.")
        self.picker.combo.setAccessibleName("Setup speech model")
        layout.addWidget(self.picker)
        self.readiness = paragraph("Installed files have not been checked.", "Speech package readiness")
        self.refresh_button = QtWidgets.QPushButton("Check installed files")
        layout.addWidget(self.refresh_button)
        paragraph("Bengali and Arabic share the optional All languages model. One download enables both. "
                  "Choosing a language or model starts no transfer.")
        layout.addStretch()
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setWidget(body)
        QtWidgets.QVBoxLayout(self).addWidget(self.scroll)
        self.hardware_button.clicked.connect(lambda: self._request("hardware"))
        self.refresh_button.clicked.connect(lambda: self._request("installed"))
        self.use_button.clicked.connect(self.use_recommendation)
        self.picker.combo.currentIndexChanged.connect(self._selection_changed)
        self.picker.busy_changed.connect(self._download_changed)
        self.checked.connect(self._accept_check, QtCore.Qt.QueuedConnection)
        self.destroyed.connect(self._shutdown)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self._shutdown)

    def _selection_changed(self):
        self.readiness_state = "unknown"
        self.readiness.setText("Installed files have not been checked.")
        self.readiness.show()
        self._generations["installed"] += 1
        self._pending.pop("installed", None)
        if self.isVisible():
            self._request("installed")

    def _download_changed(self, busy):
        self._generations["installed"] += 1
        self._pending.pop("installed", None)
        self.readiness_state = "unknown"
        if busy:
            self.readiness.hide()
        elif self.isVisible():
            self._request("installed")
        self._update_actions()

    def _request(self, kind):
        if self._closed or kind == "installed" and self.picker.task is not None:
            return
        self._generations[kind] += 1
        self._serial += 1
        self._pending[kind] = (self._serial, kind, self._generations[kind], self.picker.model_id)
        if kind == "hardware":
            self._candidate = None
            self.hardware_details.clear()
            self.recommendation.setText("Checking CPU, memory and graphics capabilities…")
        else:
            self.readiness_state = "checking"
            self.readiness.setText("Checking installed package checksums…")
            self.readiness.show()
        self._start_next()

    def _start_next(self):
        if self._closed or self._future is not None or not self._pending or not self.isVisible():
            self._update_actions()
            return
        kind = "hardware" if "hardware" in self._pending else "installed"
        job = self._pending.pop(kind)
        self._active = job
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Saydraft-setup-check")

        def run():
            try:
                result = self.probe() if kind == "hardware" else self.inspect(job[3])
            except Exception:
                result = None
            if not self._closed:
                try:
                    self.checked.emit(job, result)
                except RuntimeError:
                    pass

        self._future = self._pool.submit(run)
        self._update_actions()

    @QtCore.Slot(object, object)
    def _accept_check(self, job, result):
        if self._closed or self._active != job:
            return
        self._active = self._future = None
        _, kind, generation, model_id = job
        if generation == self._generations[kind] and (kind == "hardware" or model_id == self.picker.model_id):
            if kind == "hardware":
                self._show_recommendation(result)
            else:
                state = result.get("state") if isinstance(result, dict) else None
                self.readiness_state = state if state in ("verified", "missing", "custom") else "failed"
                self.readiness.setText({
                    "verified": "Speech package installed and SHA-256 verified.",
                    "missing": "Model setup needed. Use Download / Resume to complete the selected package.",
                    "custom": "Custom local model. Manage this model in Hub → Settings → Models.",
                    "failed": "Could not check installed files. Check storage and try again.",
                }[self.readiness_state])
                if state == "missing" and result.get("missing"):
                    self.readiness.setText(self.readiness.text() + "\nNeeded: " + "; ".join(result["missing"]))
        self._start_next()

    def _show_recommendation(self, report):
        report = report if isinstance(report, dict) else {}
        self._candidate = capability_recommendation(report)
        ram = report.get("ram_bytes")
        memory = f"{ram / 1024**3:.1f} GiB" if type(ram) is int and ram > 0 else "Unknown"
        graphics = "Detected" if report.get("vulkan") or report.get("cuda") else (
            "Not detected" if isinstance(report.get("vulkan"), list) and isinstance(report.get("cuda"), list) else "Unknown")
        self.hardware_details.setText(f"Memory: {memory} · Graphics acceleration: {graphics}")
        tier = self._candidate["candidate_tier"]
        if tier == "pending":
            self.recommendation.setText("Recommendation pending: CPU or memory information is unavailable. "
                                        "You can choose a speech model below.")
        else:
            model = get_model(self._candidate["speech_model"])
            self.recommendation.setText(f'{tier.title()} candidate · {model["label"]}. '
                                        "Speech and AI cleanup speed have not been measured.")
        self.use_button.setEnabled(tier != "pending")

    def use_recommendation(self):
        if (self.picker.task is None and self._candidate is not None
                and self._candidate["candidate_tier"] != "pending"):
            self.picker.combo.setCurrentIndex(self.picker.combo.findData(self._candidate["speech_model"]))

    def _toggle_details(self, expanded):
        self.details.setVisible(expanded)
        self.details_toggle.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)

    def _update_actions(self):
        busy = {self._active[1]} if self._active is not None else set()
        busy.update(self._pending)
        self.hardware_button.setEnabled(not self._closed and "hardware" not in busy)
        self.refresh_button.setEnabled(not self._closed and self.picker.task is None and "installed" not in busy)
        self.use_button.setEnabled(not self._closed and self.picker.task is None and
            self._candidate is not None and self._candidate["candidate_tier"] != "pending")

    def cancel_checks(self):
        if not self._closed and ("hardware" in self._pending or self._active is not None and self._active[1] == "hardware"):
            self.recommendation.setText("PC check cancelled. Choose Check this PC to try again.")
        for kind in self._generations:
            self._generations[kind] += 1
        self._pending.clear()

    def showEvent(self, event):
        super().showEvent(event)
        self._request("installed")

    def hideEvent(self, event):
        self.cancel_checks()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._shutdown()
        super().closeEvent(event)

    @QtCore.Slot()
    def _shutdown(self):
        if not self._closed:
            self._closed = True
            self.cancel_checks()
            self.picker.pause()
            if self._pool is not None:
                self._pool.shutdown(wait=False, cancel_futures=True)
