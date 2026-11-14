"""Local Hub overview: aggregate statistics and the last five saved dictations."""

from datetime import datetime

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.privacy.netguard import NetworkGuard
from saydraft.data.history_view import timestamp_label
from .icons import line_icon


class HomePage(QtWidgets.QScrollArea):
    history_requested = QtCore.Signal(int)
    privacy_requested = QtCore.Signal()
    meeting_requested = QtCore.Signal()

    def __init__(self, store, *, shortcut=lambda: "Ctrl+Win", model=lambda: "", tier=lambda: "pending",
                 now=datetime.now):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        content = QtWidgets.QWidget()
        self.setWidget(content)
        self.store, self.shortcut, self.model, self.tier, self.now = store, shortcut, model, tier, now
        self._rendered_keys = None
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self.greeting = QtWidgets.QLabel()
        self.greeting.setProperty("role", "display")
        self.greeting.setWordWrap(True)
        layout.addWidget(self.greeting)
        shortcut_row = QtWidgets.QHBoxLayout()
        shortcut_row.addWidget(QtWidgets.QLabel("Hold"))
        self.keycaps = QtWidgets.QHBoxLayout()
        self.keycaps.setSpacing(6)
        shortcut_row.addLayout(self.keycaps)
        shortcut_row.addWidget(QtWidgets.QLabel("to dictate. Release to insert."), 1)
        layout.addLayout(shortcut_row)
        metrics = QtWidgets.QHBoxLayout()
        self.values = {}
        for key, caption in (("words", "Words this week"), ("wpm", "Average WPM"), ("saved", "Estimated time saved")):
            card = QtWidgets.QGroupBox()
            content = QtWidgets.QVBoxLayout(card)
            value = QtWidgets.QLabel("—")
            value.setProperty("role", "display")
            value.setAccessibleName(caption)
            label = QtWidgets.QLabel(caption)
            label.setWordWrap(True)
            content.addWidget(value)
            content.addWidget(label)
            self.values[key] = value
            metrics.addWidget(card, 1)
        self.values["saved"].setToolTip("Estimated against typing at 40 words per minute, minus speaking time.")
        layout.addLayout(metrics)
        self.measurement_note = QtWidgets.QLabel()
        self.measurement_note.setProperty("role", "muted")
        self.measurement_note.setWordWrap(True)
        layout.addWidget(self.measurement_note)
        chips = QtWidgets.QHBoxLayout()
        self.model_label = QtWidgets.QLabel()
        self.model_label.setTextFormat(QtCore.Qt.PlainText)
        self.model_label.setWordWrap(True)
        chips.addWidget(self.model_label, 1)
        self.offline_button = QtWidgets.QPushButton()
        self.offline_button.clicked.connect(self.privacy_requested)
        chips.addWidget(self.offline_button)
        layout.addLayout(chips)
        self.meeting_button = QtWidgets.QPushButton('Meeting notes · Labs')
        self.meeting_button.clicked.connect(self.meeting_requested)
        layout.addWidget(self.meeting_button, alignment=QtCore.Qt.AlignLeft)
        heading = QtWidgets.QLabel("Recent dictations")
        heading.setProperty("role", "eyebrow")
        layout.addWidget(heading)
        self.recent = QtWidgets.QListWidget()
        self.recent.setAccessibleName("Last five dictations; activate an entry to open History")
        self.recent.setWordWrap(True)
        self.recent.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.recent.itemActivated.connect(self._open_history)
        self.recent.itemClicked.connect(self._open_history)
        layout.addWidget(self.recent, 1)
        self.empty = QtWidgets.QLabel("Your first dictation will appear here.")
        self.empty.setProperty("role", "muted")
        layout.addWidget(self.empty)
        self.refresh()

    def _open_history(self, item):
        self.history_requested.emit(item.data(QtCore.Qt.UserRole))

    def refresh_status(self):
        active = NetworkGuard.is_installed()
        self.offline_button.setText("Offline" if active else "Offline policy unavailable")
        self.offline_button.setAccessibleName("Offline mode active. Open Privacy." if active else "Offline policy unavailable. Open Privacy.")
        self.offline_button.setIcon(line_icon('<path d="m4 10 4 4 8-8"/>', self.offline_button.palette()) if active else QtGui.QIcon())

    def refresh(self):
        now = self.now()
        self.greeting.setText("Good morning." if now.hour < 12 else "Good afternoon." if now.hour < 18 else "Good evening.")
        chord = str(self.shortcut()).replace("control", "Ctrl").replace("windows", "Win")
        keys = tuple(key.strip().title() for key in chord.split("+"))
        if keys != self._rendered_keys:
            while self.keycaps.count():
                widget = self.keycaps.takeAt(0).widget()
                widget.hide()
                widget.deleteLater()
            for key in keys:
                label = QtWidgets.QLabel(key)
                label.setTextFormat(QtCore.Qt.PlainText)
                label.setProperty("role", "eyebrow")
                label.setProperty("keycap", True)
                self.keycaps.addWidget(label)
            self._rendered_keys = keys
        stats = self.store.weekly_stats(today=now.date())
        self.values["words"].setText(f"{stats.words:,}")
        wpm, saved = stats.words_per_minute, stats.seconds_saved
        self.values["wpm"].setText(f"{wpm:.0f}" if wpm is not None else "—")
        self.values["saved"].setText("—" if saved is None else f"{saved / 60:.0f} min" if saved >= 60 else f"{saved:.0f} sec")
        self.measurement_note.setText("Speaking-time measurements are incomplete for this week." if not stats.duration_complete
            else "WPM uses speaking time. Time saved is an estimate against 40 WPM typing.")
        tier = str(self.tier() or "pending")
        self.model_label.setText(f"{self.model()} · {tier.title() + ' tier' if tier != 'pending' else 'Tier not measured'}")
        self.refresh_status()
        self.recent.clear()
        rows = self.store.list_recent(limit=5)
        for row in rows:
            text = " ".join(row.cleaned_text.split()) or "Recording saved for retry"
            preview = text if len(text) <= 180 else text[:177] + "..."
            item = QtWidgets.QListWidgetItem(f"{row.app_name or 'Unknown app'} · {timestamp_label(row.created_at, now=now)}\n{preview}")
            item.setData(QtCore.Qt.UserRole, row.id)
            self.recent.addItem(item)
        self.empty.setVisible(not rows)
