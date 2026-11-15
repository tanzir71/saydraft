"""First-run model choices, explicit PC checks and asynchronous package verification."""

from concurrent.futures import ThreadPoolExecutor
import copy
import math

from PySide6 import QtCore, QtWidgets

from saydraft.models.hardware import probe_hardware
from saydraft.models.manifest import get_model
from saydraft.models.tiers import tier_defaults
from saydraft.asr.selection import select_model
from saydraft.models.setup import capability_recommendation, inspect_speech_package, setup_model_id
from .model_picker import ModelPicker


class OnboardingModelsPage(QtWidgets.QWizardPage):
    checked = QtCore.Signal(object, object)
    benchmark_settled = QtCore.Signal()
    finish_checked = QtCore.Signal(int, str, object)

    def __init__(self, config, *, download_callback=None, hardware_probe=None, status_provider=None,
                 benchmark_callback=None, benchmark_cancel_callback=None, config_provider=None,
                 benchmark_directory=None):
        super().__init__()
        self.setTitle("Set up models")
        self.probe = hardware_probe or probe_hardware
        self.inspect = status_provider or inspect_speech_package
        self._pool = self._future = self._active = None
        self._pending = {}
        self._generations = {"hardware": 0, "installed": 0, "finish": 0}
        self._serial = 0
        self._closed = False
        self._candidate = None
        self.benchmark_callback = benchmark_callback
        self.benchmark_cancel_callback = benchmark_cancel_callback
        self._provided_config = config_provider is not None
        self.config_provider = config_provider or (lambda: copy.deepcopy(config))
        self.benchmark_directory = benchmark_directory
        self._benchmark_generation = 0
        self._benchmark_cancelled = False
        self._benchmark_model = None
        self.benchmark_report = None
        self.readiness_state = "unknown"
        self._local_receipts = {}
        self._last_complete = False
        self._notifying_complete = False
        self._visit_started = False
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
        self.recommendation = paragraph("Check this PC offers a provisional starting recommendation.", "PC setup recommendation")
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
        paragraph("Capability recommendations are provisional. After installation, use Check model performance below. "
                  "The capability check does not change your saved tier or enable AI cleanup.",
                  container=detail_layout)
        layout.addWidget(self.details)
        self.details.hide()
        self.details_toggle.toggled.connect(self._toggle_details)
        self.initial_model_id = setup_model_id(config)
        picker_config = copy.deepcopy(config)
        select_model(picker_config, self.initial_model_id, manual=False)
        self.picker = ModelPicker(picker_config, callback=download_callback,
            success_message="Transfer complete. Installed files are checked separately below.")
        self.picker.combo.setAccessibleName("Setup speech model")
        layout.addWidget(self.picker)
        self.readiness = paragraph("Installed files have not been checked.", "Speech package readiness")
        self.refresh_button = QtWidgets.QPushButton("Check installed files")
        layout.addWidget(self.refresh_button)
        self.benchmark_button = QtWidgets.QPushButton('Check model performance')
        self.benchmark_button.setAccessibleName('Check selected model performance')
        self.stop_benchmark_button = QtWidgets.QPushButton('Stop check')
        benchmark_actions = QtWidgets.QHBoxLayout()
        benchmark_actions.addWidget(self.benchmark_button)
        benchmark_actions.addWidget(self.stop_benchmark_button)
        layout.addLayout(benchmark_actions)
        self.benchmark_status = paragraph('After installation, check speed using bundled speech. '
            'This opens no microphone and downloads nothing.', 'Setup performance status')
        self.benchmark_details = paragraph('', 'Measured setup performance')
        self.benchmark_button.clicked.connect(self.start_benchmark)
        self.stop_benchmark_button.clicked.connect(self.cancel_benchmark)
        paragraph("Thai, Chinese, Korean, Japanese, Hindi, Urdu, Indonesian, Malay, Bengali and Arabic share the optional All languages model. "
                  "Portuguese, including Brazilian Portuguese, is also covered by the default model. "
                  "Choosing a language or model starts no transfer. After setup, choose your language "
                  "in Hub → Settings → Languages.")
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
        self._update_actions()

    @property
    def benchmark_active(self):
        return bool(self._benchmark_generation)

    def isComplete(self):
        return self.readiness_state in ('verified', 'compatible') and self.picker.task is None

    def validatePage(self):
        return self.isComplete()

    def _notify_complete(self):
        complete = self.isComplete()
        if complete != self._last_complete:
            self._last_complete = complete
            self._notifying_complete = True
            try:
                self.completeChanged.emit()
            finally:
                self._notifying_complete = False

    def _readiness_result(self, model_id, result):
        if not isinstance(result, dict):
            return {'state': 'failed', 'missing': []}
        result = dict(result)
        if result.get('state') == 'local' and not model_id.startswith('whisper-'):
            return {'state': 'failed', 'missing': []}
        fingerprint = result.get('fingerprint')
        if (result.get('state') == 'local' and isinstance(fingerprint, str)
                and len(fingerprint) == 64 and all(c in '0123456789abcdef' for c in fingerprint)
                and self._local_receipts.get(model_id) == fingerprint):
            result['state'] = 'compatible'
        return result

    def verify_for_finish(self, model_id):
        if self._closed or self.picker.task is not None:
            return 0
        self._generations['finish'] += 1
        generation = self._generations['finish']
        self._serial += 1
        self._pending['finish'] = (self._serial, 'finish', generation, model_id)
        self._start_next()
        return generation

    def cancel_finish_check(self):
        self._generations['finish'] += 1
        self._pending.pop('finish', None)

    def start_benchmark(self):
        if (self._closed or self.benchmark_active or self.picker.task is not None or
                self._future is not None or self._pending or not callable(self.benchmark_callback)):
            return False
        try:
            config = copy.deepcopy(self.config_provider())
            current_model = setup_model_id(config)
            if current_model != self.picker.model_id and self._provided_config:
                # Unchanged choices follow newer saved settings. Treat this as
                # a refreshed baseline, so Finish does not disable their routing.
                self.initial_model_id = current_model
                index = self.picker.combo.findData(current_model)
                if index < 0:
                    self.picker.combo.addItem(config['stt']['model_size'], current_model)
                    index = self.picker.combo.count() - 1
                self.picker.combo.setCurrentIndex(index)
                self.benchmark_status.setText('Speech settings changed. Review the updated model, then choose Check model performance again.')
                return False
            if current_model != self.picker.model_id:
                select_model(config, self.picker.model_id, manual=True)
            generation = self.benchmark_callback(config, directory=self.benchmark_directory)
        except Exception:
            generation = 0
        if type(generation) is not int or generation <= 0:
            self.benchmark_status.setText('Could not start. Finish other app work, then try the check again.')
            return False
        self._benchmark_generation = generation
        self._benchmark_model = self.picker.model_id
        self._benchmark_cancelled = False
        self.benchmark_report = None
        self.benchmark_details.clear()
        self.benchmark_status.setText('Checking the selected model locally. First model loading can take longer than the timed speech samples.')
        self._update_actions()
        self.benchmark_settled.emit()
        return True

    def cancel_benchmark(self):
        if not self.benchmark_active:
            return False
        self._benchmark_cancelled = True
        self.benchmark_status.setText('Stopping check. Waiting for the current native operation to finish…')
        self._update_actions()
        try:
            return bool(self.benchmark_cancel_callback and
                self.benchmark_cancel_callback(self._benchmark_generation))
        except Exception:
            return False

    @QtCore.Slot(int, str)
    def accept_benchmark_progress(self, generation, phase):
        if (generation != self._benchmark_generation or self._closed or self._benchmark_cancelled
                or not self.isVisible() or self._benchmark_model != self.picker.model_id):
            return
        message = {'hardware': 'Checking CPU, memory and graphics capabilities…',
            'preparing': 'Loading the selected installed speech model…',
            'warmup': 'Warming speech recognition with bundled audio…',
            'cleanup': 'Measuring enabled local AI cleanup; settings stay unchanged…',
            'saving': 'Finishing the measured performance report…'}
        if phase.startswith('speech_') and phase[-1:] in ('1', '2', '3'):
            text = f'Timing speech sample {phase[-1]} of 3 on the bundled eight-second recording…'
        else:
            text = message.get(phase)
        if text:
            self.benchmark_status.setText(text)

    @QtCore.Slot(int, object)
    def accept_benchmark_finished(self, generation, result):
        if generation != self._benchmark_generation:
            return
        publish = (not self._closed and not self._benchmark_cancelled and self.isVisible()
            and self._benchmark_model == self.picker.model_id)
        self._benchmark_generation = 0
        self._update_actions()
        self.benchmark_settled.emit()
        if not publish:
            if not self._closed:
                self.benchmark_status.setText('Check stopped. Choose Check model performance to try again.')
            return
        result = result if isinstance(result, dict) else {}
        if result.get('state') == 'cancelled':
            self.benchmark_status.setText('Check stopped. Choose Check model performance to try again.')
            return
        report = result.get('report')
        measured = report.get('measurements', {}) if isinstance(report, dict) else {}
        measured = measured if isinstance(measured, dict) else {}
        seconds = measured.get('asr_seconds')
        if (result.get('state') != 'complete' or measured.get('asr_status') != 'ok'
                or measured.get('asr_model') != self._benchmark_model
                or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0):
            self.benchmark_status.setText('Install the selected speech model, then check again.'
                if result.get('state') == 'model_missing' else 'Performance could not be measured. Previous reports are kept; try again.')
            return
        self.benchmark_report = report
        tier = report.get('assessment', {}).get('tier', 'pending')
        tier = tier if tier in ('lite', 'standard', 'pro') else 'pending'
        self.benchmark_status.setText('Tier pending: speech measured; more hardware or cleanup measurements are needed.'
            if tier == 'pending' else f'Measured recommendation: {tier.title()}. Saved manual tier and AI settings stay unchanged.')
        if tier != 'pending':
            recommended = tier_defaults(tier, report)['asr_model']
            self._candidate = {'candidate_tier': tier, 'speech_model': recommended, 'provisional': False}
            self.recommendation.setText(f'Measured {tier.title()} recommendation · {get_model(recommended)["label"]}. '
                'Use speech recommendation stages this speech model without downloading or enabling AI cleanup.')
        rows = [f"Speech: {measured['asr_seconds']:.3f} s median for eight seconds of audio (3 timed samples)."]
        if measured.get('llm_08_tps') is not None:
            rows.append(f"0.8B cleanup: {measured['llm_08_tps']:.1f} tokens/s.")
        if measured.get('llm_2_tps') is not None:
            rows.append(f"2B cleanup: {measured['llm_2_tps']:.1f} tokens/s.")
        if measured.get('cleanup_status') != 'ok':
            rows.append('AI cleanup speed is unmeasured. This check never enables or installs AI cleanup.')
        rows.append('An explicit successful check keeps its report separately from setup preferences.')
        self.benchmark_details.setText('\n'.join(rows))
        fingerprint = measured.get('local_model_fingerprint')
        if (self._benchmark_model.startswith('whisper-') and isinstance(fingerprint, str) and len(fingerprint) == 64
                and all(c in '0123456789abcdef' for c in fingerprint)):
            self._local_receipts[self._benchmark_model] = fingerprint
            self._request('installed')
        self._update_actions()

    def _selection_changed(self):
        self.cancel_benchmark()
        self.benchmark_report = None
        self.benchmark_details.clear()
        self.readiness_state = "unknown"
        self._notify_complete()
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
        self._notify_complete()
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
            self._notify_complete()
            self.readiness.setText("Checking installed package checksums…")
            self.readiness.show()
        self._start_next()

    def _start_next(self):
        if (self._closed or self._future is not None or not self._pending
                or not self.isVisible() and 'finish' not in self._pending):
            self._update_actions()
            return
        kind = 'finish' if 'finish' in self._pending else "hardware" if "hardware" in self._pending else "installed"
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

        try:
            self._future = self._pool.submit(run)
        except Exception:
            pool, self._pool = self._pool, None
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self.checked.emit(job, None)
        self._update_actions()

    @QtCore.Slot(object, object)
    def _accept_check(self, job, result):
        if self._closed or self._active != job:
            return
        self._active = self._future = None
        _, kind, generation, model_id = job
        if generation == self._generations[kind] and (kind in ("hardware", 'finish') or model_id == self.picker.model_id):
            if kind == "hardware":
                self._show_recommendation(result)
            elif kind == 'finish':
                self.finish_checked.emit(generation, model_id, self._readiness_result(model_id, result))
            else:
                result = self._readiness_result(model_id, result)
                state = result.get("state") if isinstance(result, dict) else None
                self.readiness_state = state if state in ("verified", "missing", "custom", 'local', 'compatible') else "failed"
                self.readiness.setText({
                    "verified": "Speech package installed and SHA-256 verified.",
                    "missing": "Model setup needed. Use Download / Resume to complete the selected package.",
                    "custom": "Custom model unavailable. Check its local path or choose a listed model to install.",
                    'local': 'Existing local model files found. Use Check model performance to confirm they load offline before continuing. These files are not catalog-verified.',
                    'compatible': 'Local model loaded offline; its files match the completed check. Catalog SHA-256 verification is not claimed.',
                    "failed": "Could not check installed files. Check storage and try again.",
                }[self.readiness_state])
                if state == "missing" and result.get("missing"):
                    self.readiness.setText(self.readiness.text() + "\nNeeded: " + "; ".join(result["missing"]))
                self._notify_complete()
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
                                        "Speech and AI cleanup are not measured by this capability check.")
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
        active = self.benchmark_active
        self.picker.setEnabled(not active and not self._closed)
        self.hardware_button.setEnabled(not self._closed and not active and "hardware" not in busy)
        self.refresh_button.setEnabled(not self._closed and not active and self.picker.task is None and "installed" not in busy)
        self.use_button.setEnabled(not self._closed and not active and self.picker.task is None and
            self._candidate is not None and self._candidate["candidate_tier"] != "pending")
        self.benchmark_button.setEnabled(not self._closed and not active and not busy and
            self.picker.task is None and callable(self.benchmark_callback))
        self.stop_benchmark_button.setEnabled(not self._closed and active and not self._benchmark_cancelled)

    def cancel_checks(self):
        self.cancel_benchmark()
        if not self._closed and ("hardware" in self._pending or self._active is not None and self._active[1] == "hardware"):
            self.recommendation.setText("PC check cancelled. Choose Check this PC to try again.")
        for kind in self._generations:
            self._generations[kind] += 1
        self._pending.clear()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._visit_started and not self._notifying_complete:
            self._visit_started = True
            self._request("installed")

    def hideEvent(self, event):
        if not self._notifying_complete:
            self._visit_started = False
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
