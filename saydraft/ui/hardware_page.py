"""Show persisted local benchmarks and request a check on the serial worker."""

from datetime import datetime
import statistics

from PySide6 import QtCore, QtWidgets

from saydraft.models.hardware import latest_report
from saydraft.models.manifest import get_model


class HardwarePage(QtWidgets.QWidget):
    def __init__(self, *, callback=None, directory=None):
        super().__init__()
        self.callback = callback
        self.busy = False
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName("Local hardware and performance results")
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.check_button = QtWidgets.QPushButton("Check performance")
        self.check_button.setEnabled(callback is not None)
        self.check_button.clicked.connect(self.start)
        layout = QtWidgets.QVBoxLayout(self)
        explanation = QtWidgets.QLabel("Tests your speech model using bundled audio and your enabled AI cleanup "
                                      "model using fixed sample text. Models must already be installed. "
                                      "No microphone is used. Cleanup checks can take several minutes.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addWidget(self.summary)
        layout.addWidget(self.details)
        layout.addWidget(self.check_button)
        layout.addWidget(self.status)
        self.render(latest_report(directory))

    def render(self, report):
        if not report:
            self.summary.setText("Performance has not been checked.")
            self.details.setPlainText("Check performance to get a local recommendation.")
            return
        tier = report.get("assessment", {}).get("tier", "pending")
        self.summary.setText("Recommendation pending measurements." if tier == "pending" else
                             f"Recommended tier: {tier.title()}")
        features = report.get("cpu_features") or {}
        ram = report.get("ram_bytes")
        checked = report.get("measured_at", "Unknown")
        try:
            checked = datetime.fromisoformat(checked).astimezone().strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
        rows = [f"Checked: {checked}",
                f"CPU: {report.get('logical_cores', 'Unknown')} logical cores; "
                f"{features.get('physical_cores', 'Unknown')} physical cores",
                f"RAM: {ram / 1024**3:.1f} GiB" if ram else "RAM: Unknown"]
        adapters = report.get("adapters") or []
        for name, vram in dict.fromkeys((item["name"], item["vram_bytes"]) for item in adapters):
            rows.append(f"GPU: {name} · {vram / 1024**3:.1f} GiB dedicated memory")
        rows.append("Vulkan: " + (", ".join(item["name"] for item in report.get("vulkan") or []) or "Unavailable"))
        rows.append("CUDA: " + (", ".join(item["name"] for item in report.get("cuda") or []) or "Unavailable"))
        measured = report.get("measurements", {})
        if measured.get("asr_seconds") is not None:
            model = measured.get("asr_model", "Selected speech model")
            try:
                model = get_model(model)["label"]
            except ValueError:
                pass
            rows.append(f"Speech: {measured['asr_seconds']:.3f} s median for 8 s audio · {model}")
        else:
            rows.append("Speech performance: Not measured")
        rows.append("AI cleanup performance: " + ("Measured" if measured.get("cleanup_status") == "ok" else "Not measured"))
        groups = {}
        for row in measured.get("cleanup", []):
            groups.setdefault(row["parameters_b"], []).append(60 / row["seconds"])
        for size, rates in groups.items():
            rows.append(f"AI cleanup: {size:.2g}B · {statistics.median(rates):.1f} tokens/s median "
                        f"over {len(rates)} × 60 tokens")
        self.details.setPlainText("\n".join(rows))
        if measured.get("asr_status") == "model_missing":
            self.status.setText("Install the speech model in Models, apply Settings, then check again.")
        elif measured.get("asr_status") == "failed":
            self.status.setText("Speech check failed. Verify the model in Models and try again.")
        elif measured.get("cleanup_status") == "failed":
            self.status.setText("AI cleanup could not be measured. Check your installed cleanup model and try again.")
        else:
            self.status.setText("Recommendation only. Choose your model and AI cleanup options in Settings.")

    def start(self):
        if self.busy or self.callback is None:
            return
        self.busy = True
        self.check_button.setEnabled(False)
        self.status.setText("Checking local performance… Dictation will be ready when this finishes.")
        try:
            accepted = self.callback()
        except Exception:
            accepted = False
        if not accepted:
            self.busy = False
            self.check_button.setEnabled(True)
            self.status.setText("Could not start. Finish any current dictation and try again.")

    def finish(self, report):
        self.busy = False
        self.check_button.setEnabled(self.callback is not None)
        if report is None:
            self.status.setText("Check failed. Previous results are kept; try again.")
        else:
            self.render(report)
