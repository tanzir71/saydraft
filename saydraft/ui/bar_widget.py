"""Flat Saydraft Bar and its small, separate non-activating input target."""

from __future__ import annotations

import json
import time
from enum import Enum
from importlib.resources import files

from PySide6 import QtCore, QtGui, QtWidgets

from .bar_motion import RmsEnvelope, insertion_message, shimmer_opacity


class PillState(str, Enum):
    HIDDEN = "hidden"
    IDLE = "idle"
    HOVER = "hover"
    RECORDING = "recording"
    PROCESSING = "processing"
    WARNING = "warning"
    ERROR = "error"
    COMMAND = "command"


def window_flags(*, output_only=False):
    flags = (QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
             | QtCore.Qt.Tool | QtCore.Qt.WindowDoesNotAcceptFocus | QtCore.Qt.NoDropShadowWindowHint)
    return flags | QtCore.Qt.WindowTransparentForInput if output_only else flags


class LevelMeter(QtWidgets.QWidget):
    def __init__(self, parent=None, *, clock=time.monotonic):
        super().__init__(parent)
        self.clock = clock
        self.envelope = RmsEnvelope(clock())
        self.frozen = False
        self.shimmer_seconds = None
        self.foreground = QtGui.QColor(parent.colors["barFg"])
        self.setFixedSize(67, 24)  # 14 × 2 px bars + 13 × 3 px gaps.
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

    @property
    def level(self):
        return self.envelope.level

    @property
    def heights(self):
        return self.envelope.heights

    def set_level(self, rms):
        if not self.frozen:
            self.envelope.sample(rms, self.clock())

    def advance(self):
        if not self.frozen:
            self.envelope.advance(self.clock())
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        for index, height in enumerate(self.heights):
            color = QtGui.QColor(self.foreground)
            if self.shimmer_seconds is not None:
                color.setAlphaF(shimmer_opacity(index, self.shimmer_seconds))
            painter.setBrush(color)
            painter.drawRoundedRect(QtCore.QRectF(index * 5, (24 - height) / 2, 2, height), 1, 1)


class PreviewStrip(QtWidgets.QLabel):
    def paintEvent(self, _event):
        # Draw text into its own layer so DestinationIn fades only the glyphs.
        layer = QtGui.QPixmap(self.size() * self.devicePixelRatioF())
        layer.setDevicePixelRatio(self.devicePixelRatioF())
        layer.fill(QtCore.Qt.transparent)
        text = QtGui.QPainter(layer)
        text.setFont(self.font())
        text.setPen(QtGui.QColor(self.parentWidget().colors["barFg"]))
        text.drawText(self.rect().adjusted(8, 0, -8, 0), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight, self.text())
        if self.fontMetrics().horizontalAdvance(self.text()) > self.width() - 16 or self.property("truncated"):
            text.setCompositionMode(QtGui.QPainter.CompositionMode_DestinationIn)
            fade = QtGui.QLinearGradient(0, 0, 32, 0)
            fade.setColorAt(0, QtGui.QColor(0, 0, 0, 0))
            fade.setColorAt(1, QtGui.QColor(0, 0, 0, 255))
            text.fillRect(self.rect(), fade)
        text.end()
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, layer)


class BarTarget(QtWidgets.QToolButton):
    """Only this small window receives input; the visual window is output-only."""

    def __init__(self, bar):
        super().__init__(bar)
        self.setWindowFlags(window_flags())
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.bar = bar
        self.kind = ""
        self.clicked.connect(self._activate)

    def _activate(self):
        if self.kind == "expand":
            self.bar.start_requested.emit()
        elif self.kind == "stop":
            self.bar.stop_requested.emit()
        elif self.kind == "fix":
            self.bar.fix_requested.emit(self.bar.fix_page)

    def enterEvent(self, event):
        if self.kind == "expand":
            self.bar.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.kind == "expand":
            self.bar.set_hovered(False)
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        # Windows layered-window hit testing ignores fully transparent pixels.
        # Alpha 1 keeps the padded target interactive without painting a panel.
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 1))
        painter.setPen(QtCore.Qt.NoPen)
        if self.kind == "expand":
            if self.bar.state == PillState.IDLE:
                color = QtGui.QColor(self.bar.colors["ink"])
                color.setAlphaF(.60)
                painter.setBrush(color)
                painter.drawRoundedRect(QtCore.QRectF(6, 8, 36, 8), 4, 4)
            else:
                painter.setBrush(QtGui.QColor(self.bar.colors["barBg"]))
                painter.drawRoundedRect(QtCore.QRectF(0, 0, 160, 32), 16, 16)
                painter.setFont(self.bar.caption_font)
                painter.setPen(QtGui.QColor(self.bar.colors["barFg"]))
                hint = self.fontMetrics().elidedText(self.bar.hint, QtCore.Qt.ElideMiddle, 144)
                painter.drawText(QtCore.QRect(8, 0, 144, 32), QtCore.Qt.AlignCenter, hint)
        elif self.kind == "stop":
            painter.setBrush(QtGui.QColor(self.bar.colors["signal"]))
            painter.drawEllipse(QtCore.QPointF(12, 12), 4, 4)
        elif self.kind == "fix":
            painter.setFont(self.bar.caption_font)
            painter.setPen(QtGui.QColor(self.bar.colors["barFg"]))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "Fix ↗")


class SaydraftPill(QtWidgets.QWidget):
    start_requested = QtCore.Signal()
    stop_requested = QtCore.Signal()
    fix_requested = QtCore.Signal(str)

    def __init__(self, *, qt_modules=None, hotkey_hint="Ctrl+Win", clock=time.monotonic,
                 screen_geometry_provider=None, focus_point_provider=None, timer_single_shot=None):
        super().__init__(None, window_flags(output_only=True))
        self.qt, self.clock = qt_modules, clock
        self.screen_geometry_provider = screen_geometry_provider
        self.focus_point_provider = focus_point_provider
        self.timer_single_shot = timer_single_shot
        self.colors = json.loads(files("saydraft.ui.theme").joinpath("metadata.json").read_text("utf-8"))["bar"]
        self.hotkey_hint = self._chord(hotkey_hint)
        self.paste_hint = "Shift+Alt+Z"
        self.idle_enabled = True
        self.state = PillState.HIDDEN
        self.hands_free = False
        self.hands_free_provider = None
        self.fix_page = "models"
        self.started_at = self.processing_at = 0.
        self._visibility_generation = 0
        self._anchor = None
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("Saydraft Bar")
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setStyleSheet("SaydraftPill, LevelMeter, PreviewStrip { background: transparent; border: none; }")
        self.caption_font = QtGui.QFont(self.font())
        self.caption_font.setPixelSize(12)
        self.message_font = QtGui.QFont(self.font())
        self.message_font.setPixelSize(max(16, self.message_font.pixelSize()))
        self.level_meter = LevelMeter(self, clock=clock)
        self.preview_label = PreviewStrip(self)
        self.preview_label.setFont(self.caption_font)
        self.preview_label.setTextFormat(QtCore.Qt.PlainText)
        self.preview_label.setAccessibleName("English live preview")
        self.preview_label.hide()
        # Keep the original class's inspection fields; the capsule is painted.
        self.status_label = QtWidgets.QLabel(self)
        self.elapsed_label = QtWidgets.QLabel(self)
        self.hotkey_label = QtWidgets.QLabel(self.hotkey_hint, self)
        self.spinner_label = QtWidgets.QLabel(self)
        for label in (self.status_label, self.elapsed_label, self.hotkey_label, self.spinner_label):
            label.hide()
        self.target = BarTarget(self)
        self.dismiss_button = self.target
        self.animation_timer = QtCore.QTimer(self)
        self.animation_timer.setInterval(16)
        self.animation_timer.timeout.connect(self.advance_frame)
        self.spinner_timer = self.animation_timer  # Legacy API; no spinner is rendered.
        self.elapsed_timer = QtCore.QTimer(self)
        self.elapsed_timer.setInterval(250)
        self.elapsed_timer.timeout.connect(self.refresh_elapsed)
        self._hide_timer = QtCore.QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._timed_collapse)
        self._hide_generation = None
        self.setFixedSize(36, 8)
        self.level_meter.hide()

    @staticmethod
    def _chord(value):
        return "+".join(part.strip().capitalize() if len(part.strip()) > 1 else part.upper()
                        for part in str(value).split("+") if part.strip())

    @property
    def hint(self):
        return f"Hold {self.hotkey_hint} to dictate"

    @property
    def capsule_rect(self):
        width = 164 if self.state in (PillState.RECORDING, PillState.PROCESSING) else 268 if self.state == PillState.COMMAND else self.width()
        height = 36 if self.state in (PillState.RECORDING, PillState.PROCESSING, PillState.COMMAND) else self.height()
        return QtCore.QRect((self.width() - width) // 2, self.height() - height, width, height)

    def set_hotkey_hint(self, hotkey_hint):
        self.hotkey_hint = self._chord(hotkey_hint)
        self.hotkey_label.setText(self.hotkey_hint)
        self.target.setAccessibleDescription(self.hint)
        self.target.update()

    def set_paste_hint(self, paste_hint):
        self.paste_hint = self._chord(paste_hint)

    def set_idle_enabled(self, enabled):
        self.idle_enabled = bool(enabled)
        if self.state in (PillState.HIDDEN, PillState.IDLE, PillState.HOVER):
            self.finish_success()

    def show_idle(self):
        self._transition(PillState.IDLE)
        self.status_label.setText(self.hint)
        self._layout(36, 8)

    def set_hovered(self, hovered):
        if self.state not in (PillState.IDLE, PillState.HOVER):
            return
        self.state = PillState.HOVER if hovered else PillState.IDLE
        self._layout(160, 32) if hovered else self._layout(36, 8)

    def show_recording(self, *, hands_free=False, command=False):
        self._transition(PillState.COMMAND if command else PillState.RECORDING)
        self._anchor = None
        self.started_at = self.clock()
        self.hands_free = bool(hands_free)
        self.level_meter.envelope.reset(self.clock())
        self.level_meter.frozen = False
        self.level_meter.shimmer_seconds = None
        self.status_label.setText("⌘ Command" if command else "Recording")
        self.level_meter.show()
        self._layout(268 if command else 164, 36)
        self.refresh_elapsed()
        self.elapsed_timer.start()
        self.animation_timer.start()

    def set_hands_free(self, enabled):
        self.hands_free = bool(enabled)
        self._sync_target()

    def update_level(self, rms):
        if self.state in (PillState.RECORDING, PillState.COMMAND):
            self.level_meter.set_level(rms)

    def update_preview(self, text):
        if self.state not in (PillState.RECORDING, PillState.COMMAND) or not self.isVisible() or not text.strip():
            return
        self.preview_label.setText(text[-60:])
        self.preview_label.setProperty("truncated", len(text) > 60)
        self.preview_label.setAccessibleDescription(text[-60:])
        self.preview_label.show()
        self._layout(360, 68)

    def clear_preview(self):
        self.preview_label.clear()
        self.preview_label.hide()
        if self.state in (PillState.RECORDING, PillState.COMMAND):
            self._layout(268 if self.state == PillState.COMMAND else 164, 36)

    def refresh_elapsed(self):
        elapsed = max(0, int(self.clock() - self.started_at))
        minutes, seconds = divmod(elapsed, 60)
        self.elapsed_label.setText(f"{minutes}:{seconds:02d}")
        self.setAccessibleName(f"{self.status_label.text()} · {self.elapsed_label.text()}")

    def show_processing(self):
        self.level_meter.advance()
        self._transition(PillState.PROCESSING)
        self.processing_at = self.clock()
        self.level_meter.frozen = True
        self.level_meter.shimmer_seconds = 0.
        self.status_label.setText("Processing")
        self.level_meter.show()
        self._layout(164, 36)
        self.animation_timer.start()

    def advance_frame(self):
        if self.state in (PillState.RECORDING, PillState.COMMAND) and self.hands_free_provider is not None:
            current = bool(self.hands_free_provider())
            if current != self.hands_free:
                self.set_hands_free(current)
        if self.state == PillState.PROCESSING:
            elapsed = max(0., self.clock() - self.processing_at)
            self.level_meter.shimmer_seconds = elapsed
            self.status_label.setText("Cleaning up" if elapsed > 1.5 else "Processing")
            self.level_meter.move(84 if elapsed > 1.5 else 48, 6)
            self.setAccessibleName(self.status_label.text())
        self.level_meter.advance()
        self.update()

    def advance_spinner(self):
        self.advance_frame()

    def finish_success(self):
        if self.idle_enabled:
            self.show_idle()
        else:
            self.hide()

    def show_not_inserted(self, reason, *, saved, paste_hint=None):
        self._transition(PillState.WARNING)
        title, detail = insertion_message(reason, saved=saved, paste_hint=self.paste_hint if paste_hint is None else paste_hint)
        self.status_label.setText(title)
        self.elapsed_label.setText(detail)
        self._message_layout()
        self.hide_after(2500)

    def show_error(self, message, *, fix_page=None):
        self._transition(PillState.ERROR)
        self.fix_page = fix_page or ("microphone" if "microphone" in str(message).lower() else "models")
        self.status_label.setText(str(message).replace("\n", " ")[:160])
        self.elapsed_label.setText("Open Microphone settings" if self.fix_page == "microphone" else "Open Models settings")
        self._message_layout()

    def _message_layout(self):
        metrics = QtGui.QFontMetrics(self.message_font)
        width = max(280, max(metrics.horizontalAdvance(self.status_label.text()), metrics.horizontalAdvance(self.elapsed_label.text())) + 40)
        if self.state == PillState.ERROR:
            width += 56
        self._layout(width, 64)
        self.setAccessibleName(f"{self.status_label.text()}. {self.elapsed_label.text()}")

    def _transition(self, state):
        self._visibility_generation += 1
        self._hide_timer.stop()
        self.animation_timer.stop()
        self.elapsed_timer.stop()
        self.level_meter.hide()
        self.preview_label.clear()
        self.preview_label.hide()
        self.target.hide()
        self.state = state

    def _layout(self, width, height):
        if self._anchor is None or self.state == PillState.IDLE:
            self._anchor = self._screen_geometry()
        width = min(width, max(36, self._anchor.width() - 32))
        self.setFixedSize(width, height)
        self.preview_label.setGeometry(0, 0, width, 24)
        capsule = self.capsule_rect
        self.level_meter.move(capsule.x() + (151 if self.state == PillState.COMMAND else 48), capsule.y() + 6)
        self.move(self._anchor.x() + (self._anchor.width() - width) // 2,
                  self._anchor.y() + self._anchor.height() - height - 24)
        self.show()
        self._sync_target()
        self.update()

    def _screen_geometry(self):
        from .pill import focused_window_center
        if self.screen_geometry_provider is not None:
            return self.screen_geometry_provider()
        point = self.focus_point_provider() if self.focus_point_provider is not None else focused_window_center()
        screen = QtGui.QGuiApplication.screenAt(point) if point is not None else None
        screen = screen or QtGui.QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else QtCore.QRect(0, 0, 800, 600)

    def _sync_target(self):
        if not self.isVisible():
            self.target.hide()
            return
        capsule = self.capsule_rect
        self.target.kind = ""
        if self.state in (PillState.IDLE, PillState.HOVER):
            self.target.kind = "expand"
            rect = QtCore.QRect(-6, -8, 48, 24) if self.state == PillState.IDLE else QtCore.QRect(0, 0, 160, 40)
            self.target.setAccessibleName("Start hands-free dictation")
            self.target.setAccessibleDescription(self.hint)
        elif self.state in (PillState.RECORDING, PillState.COMMAND) and self.hands_free:
            self.target.kind = "stop"
            rect = QtCore.QRect(capsule.right() - 31, capsule.y() + 6, 24, 24)
            self.target.setAccessibleName("Stop hands-free dictation")
        elif self.state == PillState.ERROR:
            self.target.kind = "fix"
            rect = QtCore.QRect(self.width() - 64, 8, 56, 48)
            self.target.setAccessibleName(self.elapsed_label.text())
        else:
            self.target.hide()
            return
        self.target.setFont(self.caption_font)
        self.target.setGeometry(QtCore.QRect(self.mapToGlobal(rect.topLeft()), rect.size()))
        self.target.show()
        self.target.raise_()
        self.target.update()

    def hide_after(self, milliseconds):
        generation = self._visibility_generation
        if self.timer_single_shot is not None:
            self.timer_single_shot(int(milliseconds), lambda: self.finish_success() if generation == self._visibility_generation else None)
        else:
            self._hide_generation = generation
            self._hide_timer.start(int(milliseconds))

    def _timed_collapse(self):
        if self._hide_generation == self._visibility_generation:
            self.finish_success()

    def hideEvent(self, event):
        self._visibility_generation += 1
        self.state = PillState.HIDDEN
        self.preview_label.clear()
        self.preview_label.hide()
        self.target.hide()
        for timer in (self.animation_timer, self.elapsed_timer, self._hide_timer):
            timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.target.hide()
        super().closeEvent(event)

    def paintEvent(self, _event):
        if self.state in (PillState.HIDDEN, PillState.IDLE, PillState.HOVER):
            return  # The expand target paints the idle/hover capsule exactly once.
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color = self.colors["barWarn"] if self.state == PillState.WARNING else self.colors["barError"] if self.state == PillState.ERROR else self.colors["barBg"]
        painter.setBrush(QtGui.QColor(color))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(self.capsule_rect, 18, 18)
        if self.preview_label.isVisible():
            painter.drawRoundedRect(QtCore.QRectF(0, 0, self.width(), 24), 12, 12)
        painter.setPen(QtGui.QColor(self.colors["barFg"]))
        painter.setFont(self.caption_font)
        if self.state == PillState.COMMAND:
            # The bundled text fonts do not contain U+2318. Draw an original
            # vector command mark instead of depending on an OS fallback font.
            painter.save()
            painter.translate(self.capsule_rect.x() + 16, self.capsule_rect.y() + 11)
            painter.scale(.85, .85)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor(self.colors["barFg"]), 1.4))
            mark = QtGui.QPainterPath()
            mark.moveTo(4, 4)
            mark.lineTo(10, 4)
            mark.lineTo(10, 2)
            mark.cubicTo(10, -.7, 14, -.7, 14, 2)
            mark.cubicTo(14, 4.7, 10, 4.7, 10, 4)
            mark.lineTo(10, 10)
            mark.lineTo(12, 10)
            mark.cubicTo(14.7, 10, 14.7, 14, 12, 14)
            mark.cubicTo(9.3, 14, 9.3, 10, 10, 10)
            mark.lineTo(4, 10)
            mark.lineTo(4, 12)
            mark.cubicTo(4, 14.7, 0, 14.7, 0, 12)
            mark.cubicTo(0, 9.3, 4, 9.3, 4, 10)
            mark.lineTo(4, 4)
            mark.lineTo(2, 4)
            mark.cubicTo(-.7, 4, -.7, 0, 2, 0)
            mark.cubicTo(4.7, 0, 4.7, 4, 4, 4)
            painter.drawPath(mark)
            painter.restore()
            painter.drawText(self.capsule_rect.adjusted(36, 0, -100, 0), QtCore.Qt.AlignVCenter, "Command")
        elif self.state == PillState.PROCESSING and self.clock() - self.processing_at > 1.5:
            painter.setOpacity(.80)
            painter.drawText(self.rect().adjusted(9, 0, -75, 0), QtCore.Qt.AlignVCenter, "Cleaning up")
        elif self.state in (PillState.WARNING, PillState.ERROR):
            painter.setFont(self.message_font)
            right = 72 if self.state == PillState.ERROR else 16
            bounds = self.rect().adjusted(16, 5, -right, -5)
            metrics = painter.fontMetrics()
            for index, text in enumerate((self.status_label.text(), self.elapsed_label.text())):
                line = QtCore.QRect(bounds.x(), bounds.y() + 26 * index, bounds.width(), 26)
                painter.drawText(line, QtCore.Qt.AlignVCenter, metrics.elidedText(text, QtCore.Qt.ElideRight, bounds.width()))

    def render_image(self):
        """Composite only these two owned widgets; never capture the desktop."""
        image = self.grab().toImage()
        if self.target.isVisible():
            painter = QtGui.QPainter(image)
            painter.drawPixmap(self.mapFromGlobal(self.target.pos()), self.target.grab())
            painter.end()
        return image
