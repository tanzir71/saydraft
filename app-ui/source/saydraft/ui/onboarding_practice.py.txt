"""In-window chat/email practice; queued results never enter another application."""

import math
import threading

from PySide6 import QtCore, QtWidgets

from saydraft.core.practice import MAX_TEXT, PracticeResult
from saydraft.data.history_view import transcript_diff
from .private_text import PrivatePlainTextEdit

_GROUPS = ('messages', 'email')
_PROMPTS = {
    'messages': "Try: ‘Um, let's meet Tuesday—no, Thursday at three.’ Review the correction before continuing.",
    'email': "Try: ‘Hi Sam, please bring the following. First, the draft. Second, the figures. Thanks.’ Review the list below.",
}


class OnboardingPracticePage(QtWidgets.QWizardPage):
    settled = QtCore.Signal()

    def __init__(self, *, config_provider, open_callback=None, start_callback=None,
                 stop_callback=None, close_callback=None):
        super().__init__()
        self.setTitle('Try it')
        self.config_provider = config_provider
        self.open_callback, self.start_callback = open_callback, start_callback
        self.stop_callback, self.close_callback = stop_callback, close_callback
        self._generation = self._capture = self._last_capture = 0
        self._cancelled_capture = 0
        self._ready = self._closing = self._cleanup_failed = self._closed = False
        self._want_open = False
        self._externally_stopped = False
        self._phase = ''
        self._permit = threading.Event()
        self._window = None
        self.results = {}
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)

        def paragraph(text, name):
            label = QtWidgets.QLabel(text)
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            label.setAccessibleName(name)
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
            label.setSizePolicy(policy)
            layout.addWidget(label)
            return label

        paragraph('Nothing is sent, saved in History, or pasted outside setup. '
                  'Practice audio stays in memory.', 'Practice privacy')
        self.prompt = paragraph('', 'Practice speaking prompt')
        self.tabs = QtWidgets.QTabWidget()
        self.boxes = {}
        for group, label in (('messages', 'Chat'), ('email', 'Email')):
            box = PrivatePlainTextEdit()
            box.setReadOnly(True)
            box.setAccessibleName(f'Practice {label.lower()} field')
            box.setPlaceholderText('Click here and hold your dictation shortcut, or choose Record below.')
            box.setFixedHeight(max(92, box.fontMetrics().height() * 3 + 16))
            self.boxes[group] = box
            self.tabs.addTab(box, label)
        layout.addWidget(self.tabs)
        self.shortcut_label = paragraph('', 'Practice shortcut')
        self.prepare_button = QtWidgets.QPushButton('Prepare practice')
        self.record_button = QtWidgets.QPushButton('Record')
        self.cancel_button = QtWidgets.QPushButton('Cancel recording')
        for button in (self.prepare_button, self.record_button, self.cancel_button):
            layout.addWidget(button)
        self.meter = QtWidgets.QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setValue(0)
        self.meter.setTextVisible(False)
        self.meter.setAccessibleName('Practice microphone level')
        layout.addWidget(self.meter)
        self.status = paragraph('Prepare an installed model to try your microphone and shortcut.', 'Practice status')
        self.raw_label = paragraph('Before cleanup', 'Raw practice label')
        self.raw = PrivatePlainTextEdit()
        self.raw.setReadOnly(True)
        self.raw.setAccessibleName('Practice transcript before cleanup')
        self.raw.setMinimumHeight(90)
        layout.addWidget(self.raw)
        paragraph('After cleanup', 'Cleaned practice label')
        self.cleaned = PrivatePlainTextEdit()
        self.cleaned.setReadOnly(True)
        self.cleaned.setAccessibleName('Practice transcript after cleanup')
        self.cleaned.setMinimumHeight(90)
        layout.addWidget(self.cleaned)
        self.review_height_timer = QtCore.QTimer(self)
        self.review_height_timer.setSingleShot(True)
        self.review_height_timer.timeout.connect(self._review_heights)
        self.comparison_timer = QtCore.QTimer(self)
        self.comparison_timer.setSingleShot(True)
        self.comparison_timer.timeout.connect(self._show_comparison)
        self._review_heights()
        paragraph('Changes', 'Practice changes label')
        self.chips = QtWidgets.QWidget()
        self.chip_layout = QtWidgets.QVBoxLayout(self.chips)
        self.chip_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chips)
        paragraph('The selected chat/email field shows the cleaned result. Both fields are practice '
                  'targets; they do not send messages. You can continue to Style without recording.', 'Practice result guidance')
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setWidget(body)
        QtWidgets.QVBoxLayout(self).addWidget(self.scroll)
        self.prepare_button.clicked.connect(lambda: self.prepare(explicit=True))
        self.record_button.clicked.connect(self.toggle_recording)
        self.cancel_button.clicked.connect(self.cancel_recording)
        self.tabs.currentChanged.connect(self._target_changed)
        self.destroyed.connect(self._shutdown)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self._shutdown)
        self._target_changed()
        self._controls()

    @property
    def group(self):
        return _GROUPS[self.tabs.currentIndex()]

    def isComplete(self):
        return not self._cleanup_failed

    def last_raw(self, group):
        result = self.results.get(group)
        return result.raw if result is not None else ''

    def _controls(self):
        connected = all(callable(value) for value in
            (self.open_callback, self.start_callback, self.stop_callback, self.close_callback))
        self.prepare_button.setEnabled(connected and not self._closed and not self._generation and not self._cleanup_failed)
        self.record_button.setEnabled(connected and self._ready and not self._closing and not self._cleanup_failed)
        self.record_button.setText('Stop and preview' if self._capture else 'Record')
        self.cancel_button.setEnabled(bool(self._capture) and not self._closing and not self._cleanup_failed)

    def prepare(self, *, explicit=False):
        if explicit:
            self._externally_stopped = False
        if (self._closed or self._cleanup_failed or self._generation or not callable(self.open_callback)
                or self._externally_stopped
                or not self.isVisible() or not self.window().isActiveWindow()):
            return False
        self._want_open = True
        self._permit = threading.Event()
        self._permit.set()
        try:
            config = self.config_provider()
            generation = self.open_callback(config, int(self.window().winId()), self._permit.is_set, self.group)
        except Exception:
            generation = 0
        if type(generation) is not int or generation <= 0:
            self._permit.clear()
            self.status.setText('The app is busy. Choose Prepare practice again when it is idle.')
            return False
        self._generation = generation
        self._capture = self._last_capture = 0
        self._closing = self._ready = False
        self.shortcut_label.setText('Hold to dictate: ' + str(config['hotkeys']['speech']).replace('+', ' + '))
        self.status.setText('Preparing your installed speech model. The microphone is not recording.')
        self._controls()
        return True

    def toggle_recording(self):
        if not self._generation or not self._ready or self._closing or self._cleanup_failed:
            return False
        if self._capture:
            return bool(self.stop_callback(self._generation, self._capture))
        capture = self.start_callback(self._generation)
        if type(capture) is int and capture > 0:
            self._capture = self._last_capture = capture
            self.status.setText('Starting practice recording…')
            self._controls()
            return True
        self.status.setText('Could not start. Keep setup focused and try again.')
        return False

    def cancel_recording(self):
        if self._capture and callable(self.stop_callback):
            self._cancelled_capture = self._capture
            self._phase = 'stopping'
            self.record_button.setEnabled(False)
            return self.stop_callback(self._generation, self._capture, cancel=True)
        return False

    @QtCore.Slot(int, int, str)
    def accept_status(self, generation, capture, state):
        if self._closed or not self._generation or generation != self._generation:
            return
        if state == 'cleanup_failed':
            self._permit.clear()
            self._cleanup_failed = self._closing = True
            self._want_open = False
            self.status.setText('Could not confirm practice stopped. Cancel setup and restart Saydraft before continuing.')
            self.scroll.ensureWidgetVisible(self.status, 0, 8)
            self._controls()
            self.completeChanged.emit()
            self.settled.emit()
            return
        if self._cleanup_failed:
            return
        if state == 'stopped':
            self._generation = self._capture = 0
            self._ready = self._closing = False
            self.meter.setValue(0)
            self._controls()
            self.settled.emit()
            if self._want_open and self.isVisible() and self.window().isActiveWindow():
                QtCore.QTimer.singleShot(0, self.prepare)
            return
        if state in ('closing', 'closing_external'):
            if state == 'closing_external':
                self._externally_stopped = True
                self._want_open = False
            if not self._closing or state == 'closing_external':
                self._want_open = False  # External stop/settings changes require a fresh explicit Prepare.
                if self._phase not in ('failed', 'model_unavailable', 'microphone_unavailable'):
                    self.status.setText('Practice stopped. Choose Prepare practice when you are ready to try again.')
            self._permit.clear()
            self._closing = True
            self._ready = False
            self._controls()
            return
        if self._closing or not self._permit.is_set():
            return
        if capture and capture < self._last_capture:
            return
        if state == 'ready':
            self._ready = True
            if not self._capture:
                self.status.setText('Ready. Focus a practice field and hold your shortcut, or choose Record. A recording is limited to one minute.')
        elif state in ('arming', 'recording'):
            if capture <= 0:
                return
            self._capture = self._last_capture = capture
            self.status.setText('Starting practice recording…' if state == 'arming' else 'Listening. Speak your example, then release the shortcut or choose Stop and preview.')
            self.scroll.ensureWidgetVisible(self.status, 0, 8)
        elif state == 'idle':
            if capture != self._capture:
                return
            self._capture = 0
            self.meter.setValue(0)
            if self._phase in ('arming', 'recording', 'processing', 'stopping'):
                self.status.setText('Practice ended. Ready for another example.')
        elif state in ('processing', 'stopping'):
            if capture != self._capture:
                return
            self.status.setText('Recognizing and cleaning locally…' if state == 'processing' else 'Cancelling practice recording…')
            if state == 'stopping':
                self._cancelled_capture = capture
            self.record_button.setEnabled(False)
            self._phase = state
            return
        else:
            messages = {'model_unavailable': 'The selected speech model is unavailable. Return to Set up models to install it.',
                'microphone_unavailable': 'Could not open the selected input. Return to Microphone to check it.',
                'too_short': 'That recording was too short. Hold the shortcut a little longer and try again.',
                'no_text': 'No usable practice text was recognized. Try a shorter, clear sentence.',
                'result_too_long': 'That result is too long for practice. Try a shorter example.',
                'failed': 'Practice could not complete. Try again or return to check your model and microphone.'}
            if state in messages:
                self.status.setText(messages[state])
                if state in ('failed', 'model_unavailable'):
                    self._want_open = False
        self._phase = state
        self._controls()

    @QtCore.Slot(int, int, float)
    def accept_level(self, generation, capture, level):
        if (generation == self._generation and capture == self._capture and self._permit.is_set()
                and capture != self._cancelled_capture and not self._closing and math.isfinite(level)):
            self.meter.setValue(max(0, min(100, round(level * 400))))

    @QtCore.Slot(object)
    def accept_result(self, result):
        if (not isinstance(result, PracticeResult) or self._closed or self._closing
                or result.generation != self._generation or result.capture != self._capture
                or result.capture == self._cancelled_capture
                or result.group != self.group or not self._permit.is_set() or not self.isVisible()
                or not self.window().isActiveWindow() or len(result.raw) > MAX_TEXT or len(result.text) > MAX_TEXT * 4):
            return
        self.results[result.group] = result
        self._phase = 'complete'
        self._show_result()
        self.status.setText('Practice complete. Review the words and changes; nothing was sent or saved in History.')
        self.comparison_timer.start(0)

    def _show_result(self):
        result = self.results.get(self.group)
        self.raw.setPlainText(result.raw if result else '')
        self.cleaned.setPlainText(result.text if result else '')
        self.boxes[self.group].setPlainText(result.text if result else '')
        while self.chip_layout.count():
            widget = self.chip_layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        changes = [run for run in transcript_diff(result.raw, result.text) if run.kind != 'equal'] if result else []
        for run in changes[:8]:
            text = ('Added: ' if run.kind == 'insert' else 'Removed: ') + run.text.strip()
            label = QtWidgets.QLabel(text[:120] + ('…' if len(text) > 120 else ''))
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            label.setProperty('keycap', True)
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
            label.setSizePolicy(policy)
            self.chip_layout.addWidget(label)
        if result and not changes:
            self.chip_layout.addWidget(QtWidgets.QLabel('No text changes in this example.'))
        if result and result.enter_requested:
            label = QtWidgets.QLabel('Enter requested · practice only; nothing sent')
            label.setWordWrap(True)
            label.setProperty('keycap', True)
            self.chip_layout.addWidget(label)

    def _review_heights(self):
        for field in (self.raw, self.cleaned):
            field.setFixedHeight(max(72, field.fontMetrics().height() * 2 + 20))
        for field in self.boxes.values():
            field.setFixedHeight(max(92, field.fontMetrics().height() * 3 + 16))

    def _show_comparison(self):
        if self._closed or not self.isVisible():
            return
        self.scroll.widget().layout().activate()
        rect = self.raw_label.geometry().united(self.cleaned.geometry())
        self.scroll.ensureVisible(rect.center().x(), rect.center().y(), rect.width() // 2 + 4, rect.height() // 2 + 8)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.FontChange, QtCore.QEvent.StyleChange) and hasattr(self, 'review_height_timer'):
            self.review_height_timer.start(0)

    def _target_changed(self):
        self.prompt.setText(_PROMPTS[self.group])
        self._show_result()
        if self._generation:
            self.stop_session(reopen=True)

    def stop_session(self, *, reopen=False):
        self._want_open = reopen and not self._closed and not self._cleanup_failed and not self._externally_stopped
        self._permit.clear()
        self._ready = False
        if self._generation and not self._closing:
            self._closing = True
            try:
                self.close_callback(self._generation)
            except Exception:
                self.accept_status(self._generation, 0, 'cleanup_failed')
        self._controls()

    def eventFilter(self, watched, event):
        if watched is self._window:
            if event.type() in (QtCore.QEvent.WindowDeactivate, QtCore.QEvent.WindowBlocked):
                self.stop_session(reopen=self.isVisible())
            elif event.type() == QtCore.QEvent.WindowActivate and self._want_open and not self._generation:
                QtCore.QTimer.singleShot(0, self.prepare)
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        if self._window is not self.window():
            self._window = self.window()
            self._window.installEventFilter(self)
        self._want_open = not self._externally_stopped
        QtCore.QTimer.singleShot(0, self.prepare)
        super().showEvent(event)

    def hideEvent(self, event):
        self.stop_session()
        super().hideEvent(event)

    @QtCore.Slot()
    def _shutdown(self):
        self.stop_session()
        self._closed = True
        self.results.clear()

    def closeEvent(self, event):
        self._shutdown()
        super().closeEvent(event)
