"""Tier preference separate from measured hardware evidence."""

from PySide6 import QtCore, QtWidgets

from saydraft.models.tiers import TIERS, effective_tier


class TierPicker(QtWidgets.QWidget):
    changed = QtCore.Signal()
    defaults_requested = QtCore.Signal()

    def __init__(self, config, report=None):
        super().__init__()
        self.report = report
        self.combo = QtWidgets.QComboBox()
        self.combo.setAccessibleName("Performance tier")
        self.combo.addItem("Automatic (performance check)", "auto")
        for tier in TIERS:
            self.combo.addItem(tier.title(), tier)
        self.combo.setCurrentIndex(max(0, self.combo.findData(config.get("app", {}).get("tier", "auto"))))
        self.note = QtWidgets.QLabel()
        self.note.setWordWrap(True)
        self.note.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.defaults_button = QtWidgets.QPushButton("Use tier defaults")
        self.defaults_button.clicked.connect(self.defaults_requested)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self.combo, self.note, self.defaults_button):
            layout.addWidget(widget)
        self.combo.currentIndexChanged.connect(self.refresh)
        self.combo.currentIndexChanged.connect(self.changed)
        self.refresh()

    def selected_tier(self):
        return effective_tier({"app": {"tier": self.combo.currentData()}}, self.report)

    def refresh(self, _index=None):
        measured = effective_tier({}, self.report)
        selected = self.selected_tier()
        self.note.setText(f"Performance check: {measured.title()}. Selected tier: {selected.title()}. "
            "A manual tier changes feature availability, not measured speed. Use tier defaults to stage "
            "speech and cleanup choices, review them, then Save. Downloads stay explicit.")
        self.defaults_button.setEnabled(selected in TIERS)

    def update_report(self, report):
        self.report = report
        self.refresh()
