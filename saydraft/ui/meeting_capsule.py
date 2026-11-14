"""Persistent meeting indicator; a painted acknowledgement precedes capture."""

import time

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.core.meeting_controller import MeetingStatus


_COPY = {
    'indicator': 'Preparing the recording indicator…',
    'checking': 'Checking the installed speech, speaker and summary models…',
    'preparing': 'Starting microphone and computer audio…',
    'recording': 'Microphone and computer audio are recording.',
    'stopping': 'Stopping microphone and computer audio…',
    'stop_unconfirmed': 'Still stopping. Microphone and computer audio may still be recording.',
    'transcribing': 'Recording stopped. Transcribing locally…',
    'summarizing': 'Recording stopped. Writing a local summary…',
    'saving': 'Recording stopped. Saving a separate meeting Note…',
    'cancelled': 'Recording stopped. This meeting was discarded.',
    'discarded': 'The unsaved meeting was discarded.',
    'failed': 'The meeting could not start. Review setup and try again.',
}
_ERRORS = {
    'needs_pro': 'Meeting summaries require the Pro tier. Review the Performance and Models settings.',
    'model_missing': 'Review and download the local summary model and runtime in setup first.',
    'model_busy': 'The local editing model is still busy. Wait for it to finish and try again.',
    'indicator_unavailable': 'The recording indicator could not be shown. Recording did not start.',
    'no_audio': 'Recording stopped, but no audio was collected.',
}


class MeetingCapsule(QtWidgets.QWidget):
    indicator_ready = QtCore.Signal(object)
    stop_requested = QtCore.Signal(object, bool)
    retry_requested = QtCore.Signal(object)
    discard_requested = QtCore.Signal(object)
    notes_requested = QtCore.Signal(object)

    def __init__(self, *, clock=time.monotonic):
        super().__init__(None, QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setWindowTitle('Saydraft meeting')
        self.setObjectName('meetingCapsule')
        self.setAccessibleDescription('Meeting recording indicator. Stop recording before closing this window.')
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setStyleSheet('#meetingCapsule { border-radius: 18px; }')
        self.setMinimumWidth(360)
        self.setMaximumWidth(520)
        self.clock = clock
        self.status = None
        self._ack_sent = None
        self._dismissed_ticket = None
        self._started_at = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        row = QtWidgets.QHBoxLayout()
        self.heading = QtWidgets.QLabel('Meeting notes')
        self.heading.setAccessibleName('Meeting recording state')
        self.heading.setTextFormat(QtCore.Qt.PlainText)
        font = self.heading.font()
        font.setBold(True)
        self.heading.setFont(font)
        self.elapsed = QtWidgets.QLabel()
        self.elapsed.setAccessibleName('Approximate meeting recording duration')
        row.addWidget(self.heading, 1)
        row.addWidget(self.elapsed)
        layout.addLayout(row)
        self.description = QtWidgets.QLabel()
        self.description.setWordWrap(True)
        self.description.setTextFormat(QtCore.Qt.PlainText)
        self.description.setAccessibleName('Meeting progress')
        layout.addWidget(self.description)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setAccessibleName('Meeting transcription progress')
        layout.addWidget(self.progress)
        buttons = QtWidgets.QHBoxLayout()
        self.primary = QtWidgets.QPushButton()
        self.primary.setProperty('primary', True)
        self.secondary = QtWidgets.QPushButton()
        self.primary.clicked.connect(self._primary)
        self.secondary.clicked.connect(self._secondary)
        buttons.addWidget(self.primary)
        buttons.addWidget(self.secondary)
        layout.addLayout(buttons)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._elapsed)

    @property
    def recording_may_continue(self):
        return self.status is not None and self.status.capture_stopped is not True

    def accept_status(self, status):
        if type(status) is not MeetingStatus:
            return False
        if self.status is None or self.status.ticket is not status.ticket:
            self._started_at = self._ack_sent = self._dismissed_ticket = None
        self.status = status
        self.heading.setText('Recording meeting' if self.recording_may_continue else 'Meeting notes')
        text = _COPY.get(status.phase, 'Review the meeting in Saydraft.')
        if status.phase == 'failed':
            text = _ERRORS.get(status.reason, text)
        elif status.phase == 'finished':
            text = ('Saved a meeting Note. No speech was recognized.' if status.reason == 'no_speech' else
                    'Saved the transcript and local summary in Notes. Review names, dates and decisions.' if status.reason == 'ok' else
                    'Saved the transcript in Notes. The local summary was unavailable.')
        elif status.phase == 'recovery':
            text = ('Recording stopped. The unsaved text is kept in this session. Retry saving or discard it.'
                    if status.retained == 'text' else
                    'Recording stopped. Audio is kept in memory for retry and has not been saved to disk. Retry or discard it.')
        self.description.setText(text)
        self.progress.setVisible(status.phase == 'transcribing' and status.progress is not None)
        if status.progress is not None:
            self.progress.setValue(status.progress)
        if status.phase in ('preparing', 'recording') and self._started_at is None:
            self._started_at = self.clock()
        self.elapsed.setVisible(self.recording_may_continue and self._started_at is not None)
        self.timer.start() if self.recording_may_continue else self.timer.stop()
        self._elapsed()
        self.primary.setEnabled(True)
        self.secondary.setVisible(True)
        self.secondary.setEnabled(True)
        if self.recording_may_continue:
            self.primary.setText('Retry stop' if status.phase == 'stop_unconfirmed' else 'Stop and make Notes')
            self.secondary.setText('Discard recording' if status.phase == 'recording' else 'Cancel')
        elif status.phase == 'recovery':
            self.primary.setText('Retry')
            self.secondary.setText('Discard')
        elif status.phase == 'finished':
            self.primary.setText('View Notes')
            self.secondary.setText('Close')
        elif status.phase in ('transcribing', 'summarizing', 'saving', 'checking'):
            self.primary.setText('Cancel processing')
            self.secondary.setText('Hide')
        else:
            self.primary.setText('Close')
            self.secondary.hide()
        self.adjustSize()
        screen = self.screen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center().x() - self.width() // 2, area.bottom() - self.height() - 24)
        if self.recording_may_continue or status.phase == 'recovery' or self._dismissed_ticket is not status.ticket:
            self.show()
        self.update()
        return True

    def _elapsed(self):
        seconds = max(0, int(self.clock() - self._started_at)) if self._started_at is not None else 0
        self.elapsed.setText(f'{seconds // 60:02d}:{seconds % 60:02d}')

    def paintEvent(self, event):
        # A translucent custom QWidget must explicitly paint its styled panel;
        # QWidget's default paintEvent leaves its text on a transparent surface.
        option = QtWidgets.QStyleOption()
        option.initFrom(self)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        background = self.palette().color(QtGui.QPalette.Window)
        background.setAlpha(255)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(self.rect(), 18, 18)
        self.style().drawPrimitive(QtWidgets.QStyle.PE_Widget, option, painter, self)
        painter.end()
        status = self.status
        if status is not None and status.phase == 'indicator' and self._ack_sent is not status and self.isVisible():
            self._ack_sent = status
            QtCore.QTimer.singleShot(0, lambda: self.indicator_ready.emit(status)
                if self.status is status and self.isVisible() else None)

    def setVisible(self, visible):
        if not visible and self.recording_may_continue:
            return
        super().setVisible(visible)

    def hide(self):
        self.setVisible(False)

    def closeEvent(self, event):
        if self.recording_may_continue:
            event.ignore()
            self.stop_requested.emit(self.status, False)
            return
        if self.status is not None:
            self._dismissed_ticket = self.status.ticket
        self.timer.stop()
        super().closeEvent(event)

    def _primary(self):
        status = self.status
        if status is None:
            return
        if self.recording_may_continue:
            self.stop_requested.emit(status, False)
        elif status.phase == 'recovery':
            self.retry_requested.emit(status)
        elif status.phase == 'finished':
            self.notes_requested.emit(status)
        elif status.phase in ('transcribing', 'summarizing', 'saving', 'checking'):
            self.stop_requested.emit(status, True)
            self.primary.setEnabled(False)
        else:
            self.close()

    def _secondary(self):
        if self.recording_may_continue:
            self.stop_requested.emit(self.status, True)
        elif self.status is not None and self.status.phase == 'recovery':
            self.discard_requested.emit(self.status)
        else:
            self.close()
