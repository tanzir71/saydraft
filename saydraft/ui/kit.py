"""Desktop v2 primitives. Native controls retain keyboard and accessibility behavior."""

import math

from PySide6 import QtCore, QtGui, QtWidgets

from .icons import svg_icon
from .reflow import AdaptiveRow, WrapPushButton
from .theme.style import body_pixels, color, focus_visible, high_contrast, repolish, scaled, set_role


class Label(QtWidgets.QLabel):
    def __init__(self, text="", role="body", parent=None, *, wrap=True):
        super().__init__(str(text), parent)
        self.setTextFormat(QtCore.Qt.PlainText)
        self.setWordWrap(wrap)
        self.setMinimumWidth(0)
        set_role(self, role)
        policy = self.sizePolicy()
        policy.setHeightForWidth(wrap)
        self.setSizePolicy(policy)


class StatusLabel(Label):
    textChanged = QtCore.Signal(str)

    def __init__(self, text="", parent=None):
        super().__init__(text, "body", parent)

    def setText(self, text):
        changed = str(text) != self.text()
        super().setText(str(text))
        if changed:
            self.textChanged.emit(str(text))


class ActionButton(WrapPushButton):
    def __init__(self, text, parent=None, *, icon=None, primary=False, ghost=False, danger=False, small=False):
        self._icon_name = icon
        super().__init__(text, parent)
        self.setProperty("primary", bool(primary))
        self.setProperty("ghost", bool(ghost))
        self.setProperty("danger", bool(danger))
        if small:
            self.setProperty("size", "s")
        set_role(self, "button")
        self._refresh_icon()

    def _refresh_icon(self):
        if getattr(self, "_icon_name", None):
            tone = "onInverse" if self.property("primary") else "danger" if self.property("danger") else "ink"
            self.setIcon(svg_icon(self._icon_name, self.palette(), size=scaled(16), tone=tone))
            self.setIconSize(QtCore.QSize(scaled(16), scaled(16)))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange, QtCore.QEvent.FontChange):
            self._refresh_icon()


class IconButton(QtWidgets.QToolButton):
    def __init__(self, icon, name, parent=None):
        self._icon_name = icon
        super().__init__(parent)
        self.setAccessibleName(name)
        self.setToolTip(name)
        self.setAutoRaise(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self._refresh_icon()

    def _refresh_icon(self):
        if getattr(self, "_icon_name", None):
            self.setIcon(svg_icon(self._icon_name, self.palette(), size=scaled(16)))
            self.setIconSize(QtCore.QSize(scaled(16), scaled(16)))

    def sizeHint(self):
        return QtCore.QSize(scaled(32), scaled(32))

    def minimumSizeHint(self):
        return self.sizeHint()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange, QtCore.QEvent.FontChange):
            self._refresh_icon()
            self.updateGeometry()


class SearchField(QtWidgets.QLineEdit):
    def __init__(self, name, placeholder, parent=None, *, width=240):
        self._design_width = width
        super().__init__(parent)
        self.setProperty("search", True)
        self.setAccessibleName(name)
        self.setPlaceholderText(placeholder)
        self.setMinimumWidth(0)
        self._search_action = self.addAction(QtGui.QIcon(), QtWidgets.QLineEdit.LeadingPosition)
        self._refresh_icon()

    def _refresh_icon(self):
        if hasattr(self, "_search_action"):
            self._search_action.setIcon(svg_icon("search", self.palette(), size=scaled(16)))
            self.setMaximumWidth(scaled(self._design_width))

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(scaled(self._design_width))
        return hint

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange, QtCore.QEvent.FontChange):
            self._refresh_icon()
            self.updateGeometry()


class Toggle(QtWidgets.QCheckBox):
    """A painted switch with Qt's actual checkbox role, signals and Space behavior."""
    def __init__(self, text="", parent=None):
        self._position = 0.0
        super().__init__(text, parent)
        self.setProperty("toggle", True)
        self.setAccessibleName(text)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self._animation = QtCore.QPropertyAnimation(self, b"position", self)
        self._animation.setDuration(160)
        self._animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    @QtCore.Property(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = min(1.0, max(0.0, float(value)))
        self.update()

    def _animate(self, checked):
        self._animation.stop()
        target = 1.0 if checked else 0.0
        if self.isVisible() and not high_contrast(self) and QtWidgets.QApplication.isEffectEnabled(QtCore.Qt.UI_AnimateCombo):
            self._animation.setStartValue(self._position)
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self.position = target

    def sizeHint(self):
        # The extra four pixels on each edge leave room for the offset focus ring.
        return QtCore.QSize(scaled(48), scaled(30))

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, point):
        return self.rect().contains(point)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.FontChange, QtCore.QEvent.StyleChange, QtCore.QEvent.PaletteChange):
            if hasattr(self, "_animation"):
                self._animation.stop()
                self.position = 1.0 if self.isChecked() else 0.0
            self.updateGeometry()
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(.45)
        scale = body_pixels() / 14
        track = QtCore.QRectF((self.width() - 40 * scale) / 2, (self.height() - 22 * scale) / 2, 40 * scale, 22 * scale)
        if self.isChecked():
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color(self, "inverse"))
        else:
            painter.setPen(QtGui.QPen(color(self, "inkMuted"), 1.5 * scale))
            painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(track, 11 * scale, 11 * scale)
        diameter = (12 + 4 * self._position) * scale
        center_x = track.left() + (11 + 18 * self._position) * scale
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color(self, "onInverse" if self.isChecked() else "inkMuted"))
        painter.drawEllipse(QtCore.QPointF(center_x, track.center().y()), diameter / 2, diameter / 2)
        if focus_visible(self):
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(color(self, "ink"), max(2, 2 * scale)))
            ring = track.adjusted(-3 * scale, -3 * scale, 3 * scale, 3 * scale)
            painter.drawRoundedRect(ring, 14 * scale, 14 * scale)


class Segmented(QtWidgets.QFrame):
    """Native exclusive radios, optionally bound to an existing hidden combo."""
    currentIndexChanged = QtCore.Signal(int)
    currentTextChanged = QtCore.Signal(str)

    def __init__(self, choices=(), parent=None, *, name="Options", combo=None, labels=None, on_background=False):
        super().__init__(parent)
        self.setProperty("segmented", True)
        self.setProperty("onBackground", on_background)
        self.setAccessibleName(name)
        self._name, self._index, self._labels = name, -1, labels
        self._choices = list(choices)
        self.source_combo = combo
        self.buttons, self._data = [], []
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        self.row = AdaptiveRow(self)
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(0)
        self.row.setContentsMargins(3, 3, 3, 3)
        self.row.setSpacing(2)
        if combo is not None:
            combo.setParent(self)
            combo.hide()
            combo.setFocusPolicy(QtCore.Qt.NoFocus)
            combo.currentIndexChanged.connect(self.setCurrentIndex)
            combo.installEventFilter(self)
            for signal in (combo.model().rowsInserted, combo.model().rowsRemoved, combo.model().modelReset):
                signal.connect(self._rebuild)
        self._rebuild()

    def _rebuild(self, *_args):
        while self.row.count():
            item = self.row.takeAt(0)
            if item.widget():
                self.group.removeButton(item.widget())
                item.widget().deleteLater()
        self.buttons, self._data = [], []
        if self.source_combo is not None:
            choices = [(self._labels[i] if self._labels and i < len(self._labels) else self.source_combo.itemText(i),
                        self.source_combo.itemData(i)) for i in range(self.source_combo.count())]
            initial = self.source_combo.currentIndex()
        else:
            choices = [value if isinstance(value, tuple) else (str(value), value) for value in self._choices]
            initial = max(0, self._index)
        for index, (text, value) in enumerate(choices):
            button = QtWidgets.QRadioButton(str(text), self)
            button.setProperty("segment", True)
            set_role(button, "button")
            button.setAccessibleName(f"{self._name}: {text}")
            self.group.addButton(button, index)
            self.row.addWidget(button)
            self.buttons.append(button)
            self._data.append(value)
            button.installEventFilter(self)
            button.toggled.connect(lambda checked, i=index: self.setCurrentIndex(i) if checked else None)
        self._index = -1
        if self.buttons:
            self.setCurrentIndex(min(max(0, initial), len(self.buttons) - 1))
        self.updateGeometry()

    def count(self):
        return len(self.buttons)

    def sizeHint(self):
        # A previous narrow layout may have stacked the radios. Keep the
        # preferred width horizontal so a wider parent can restore the row.
        hints = [button.sizeHint() for button in self.buttons]
        return QtCore.QSize(6 + sum(h.width() for h in hints) + 2 * max(0, len(hints)-1),
                            6 + max((h.height() for h in hints), default=0))

    def currentIndex(self):
        return self._index

    def currentText(self):
        if self.source_combo is not None:
            return self.source_combo.currentText()
        return self.buttons[self._index].text() if self._index >= 0 else ""

    def currentData(self):
        return self.source_combo.currentData() if self.source_combo is not None else self._data[self._index] if self._index >= 0 else None

    def findData(self, value):
        return next((i for i, data in enumerate(self._data) if data == value), -1)

    def findText(self, value):
        return next((i for i, button in enumerate(self.buttons) if button.text() == value), -1)

    def setCurrentText(self, text):
        index = self.source_combo.findText(text) if self.source_combo is not None else self.findText(text)
        self.setCurrentIndex(index)

    def setCurrentIndex(self, index):
        if not 0 <= index < len(self.buttons):
            return
        changed = index != self._index
        self._index = index
        for i, button in enumerate(self.buttons):
            blocker = QtCore.QSignalBlocker(button)
            button.setChecked(i == index)
            button.setFocusPolicy(QtCore.Qt.StrongFocus if i == index else QtCore.Qt.NoFocus)
            del blocker
        if self.source_combo is not None and self.source_combo.currentIndex() != index:
            self.source_combo.setCurrentIndex(index)
        if changed:
            self.currentIndexChanged.emit(index)
            self.currentTextChanged.emit(self.currentText())

    def eventFilter(self, watched, event):
        if watched is self.source_combo and event.type() == QtCore.QEvent.EnabledChange:
            self.setEnabled(watched.isEnabledTo(self))
        if watched in self.buttons and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Up, QtCore.Qt.Key_Right, QtCore.Qt.Key_Down, QtCore.Qt.Key_Home, QtCore.Qt.Key_End):
                index = 0 if key == QtCore.Qt.Key_Home else len(self.buttons) - 1 if key == QtCore.Qt.Key_End else (
                    self._index + (-1 if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Up) else 1)) % len(self.buttons)
                self.setCurrentIndex(index)
                self.buttons[index].setFocus(QtCore.Qt.TabFocusReason)
                event.accept()
                return True
        return super().eventFilter(watched, event)


class Kbd(Label):
    def __init__(self, text, parent=None, *, bar=False):
        super().__init__(text, "caption", parent, wrap=False)
        self.setProperty("keycap", True)
        self.setProperty("bar", bar)
        self.setProperty("fontWeight", 500)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        self.setFocusPolicy(QtCore.Qt.NoFocus)


def shortcut_keys(binding):
    names = {"ctrl": "Ctrl", "control": "Ctrl", "win": "Win", "windows": "Win", "alt": "Alt", "shift": "Shift",
             "space": "Space", "esc": "Esc", "escape": "Esc", "xbutton1": "Mouse 4", "xbutton2": "Mouse 5", "middle_mouse": "Mouse 3"}
    return [names.get(key.strip().lower(), key.strip().upper()) for key in str(binding).split("+") if key.strip()]


class KeyCombo(QtWidgets.QWidget):
    def __init__(self, binding="", parent=None, *, bar=False):
        super().__init__(parent)
        self.bar = bar
        self.setProperty("bare", True)
        self.row = QtWidgets.QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(5)
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        self.set_binding(binding)

    def set_binding(self, binding):
        while self.row.count():
            widget = self.row.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        keys = shortcut_keys(binding)
        for key in keys:
            self.row.addWidget(Kbd(key, self, bar=self.bar))
        self.setAccessibleName(" plus ".join(keys) if keys else "Not assigned")
        if not keys:
            self.row.addWidget(Label("Not assigned", "caption", self))
        self.updateGeometry()


class Badge(Label):
    def __init__(self, text="", tone="neutral", parent=None):
        self._source_text = str(text)
        super().__init__(str(text).upper(), "label", parent, wrap=False)
        self.setAccessibleName(str(text))
        self.setProperty("badge", tone)
        self.setIndent(scaled(12))
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)

    def setText(self, text):
        self._source_text = str(text)
        self.setAccessibleName(str(text))
        super().setText(str(text).upper())

    def set_tone(self, tone):
        self.setProperty("badge", tone)
        repolish(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        tone = self.property("badge")
        role = {"signal": "onSignalTint", "ok": "ok", "warn": "warn", "danger": "danger"}.get(tone, "inkMuted")
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color(self, role))
        painter.drawEllipse(QtCore.QPointF(scaled(10), self.height() / 2), scaled(3), scaled(3))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.FontChange:
            self.setIndent(scaled(12))
            self.updateGeometry()


class Card(QtWidgets.QFrame):
    def __init__(self, parent=None, *, name="", padding=0):
        super().__init__(parent)
        self.setProperty("card", True)
        if name:
            self.setAccessibleName(name)
        self.body = QtWidgets.QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(0)
        self.setMinimumWidth(0)


class _SettingLayout(AdaptiveRow):
    def _stacked(self, width):
        left, _, right, _ = self.getContentsMargins()
        items = self._items()
        return len(items) > 1 and items[-1].sizeHint().width() + min(scaled(200), items[0].sizeHint().width()) + self._gap() > width - left - right

    def heightForWidth(self, width):
        left, top, right, bottom = self.getContentsMargins()
        items = self._items()
        if len(items) < 2 or self._stacked(width):
            return super().heightForWidth(width)
        text_width = max(1, width - left - right - self._gap() - items[-1].sizeHint().width())
        height = items[0].heightForWidth(text_width) if items[0].hasHeightForWidth() else items[0].sizeHint().height()
        return top + bottom + max(height, items[-1].sizeHint().height())

    def setGeometry(self, rect):
        items = self._items()
        if len(items) > 1:
            items[-1].setAlignment(QtCore.Qt.AlignLeft if self._stacked(rect.width()) else QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        super().setGeometry(rect)


class SettingRow(QtWidgets.QFrame):
    def __init__(self, title, control=None, description="", parent=None, *, badge=None, first=False):
        super().__init__(parent)
        self.setProperty("row", True)
        self.setProperty("rowFirst", first)
        self.row = _SettingLayout(self)
        self.row.setContentsMargins(20, 12, 16, 12)
        self.row.setSpacing(16)
        self.text_block = QtWidgets.QWidget(self)
        self.text_block.setProperty("bare", True)
        text = QtWidgets.QVBoxLayout(self.text_block)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(4)
        self.title = Label(title, "sub", self.text_block)
        if badge is not None:
            heading = AdaptiveRow()
            heading.setContentsMargins(0, 0, 0, 0)
            heading.setSpacing(8)
            heading.addWidget(self.title)
            heading.addWidget(badge)
            text.addLayout(heading)
        else:
            text.addWidget(self.title)
        self.description = Label(description, "small", self.text_block)
        self.description.setVisible(bool(description))
        text.addWidget(self.description)
        self.row.addWidget(self.text_block, 1)
        self.control = control
        if control is not None:
            if not control.accessibleName():
                control.setAccessibleName(title)
            if description:
                control.setAccessibleDescription(description)
            self.title.setBuddy(control)
            self.row.addWidget(control)
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def add_detail(self, widget):
        self.text_block.layout().addWidget(widget)


class SettingsGroup(QtWidgets.QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.label = Label(title.upper(), "label", self)
        self.label.setContentsMargins(4, 0, 0, 0)
        layout.addWidget(self.label)
        self.card = Card(self, name=title)
        layout.addWidget(self.card)

    def add_row(self, title, control=None, description="", *, badge=None):
        row = SettingRow(title, control, description, self.card, badge=badge, first=self.card.body.count() == 0)
        self.card.body.addWidget(row)
        return row


class PageHeader(QtWidgets.QWidget):
    def __init__(self, title, description="", parent=None, *, actions=()):
        super().__init__(parent)
        self.row = AdaptiveRow(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(16)
        block = QtWidgets.QWidget(self)
        block.setProperty("bare", True)
        text = QtWidgets.QVBoxLayout(block)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(8)
        self.title = Label(title, "title", block)
        text.addWidget(self.title)
        self.description = Label(description, "muted", block)
        self.description.setVisible(bool(description))
        text.addWidget(self.description)
        self.description_row = AdaptiveRow()
        self.description_row.setContentsMargins(0, 0, 0, 0)
        self.description_row.setSpacing(6)
        text.addLayout(self.description_row)
        self.row.addWidget(block, 1)
        self.actions = QtWidgets.QWidget(self)
        self.actions.setProperty("bare", True)
        self.action_row = AdaptiveRow(self.actions)
        self.action_row.setContentsMargins(0, 0, 0, 0)
        self.action_row.setSpacing(8)
        for action in actions:
            self.action_row.addWidget(action)
        self.row.addWidget(self.actions, 0, QtCore.Qt.AlignBottom)
        self.actions.setVisible(bool(actions))
        policy = self.sizePolicy()
        policy.setVerticalPolicy(QtWidgets.QSizePolicy.Maximum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)


class LevelMeter(QtWidgets.QProgressBar):
    """RMS display only; receives numbers, never an audio buffer or capture port."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Input level")
        self.setAccessibleDescription("Microphone input level, zero to one hundred percent")
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)
        self.clipping = False
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.setMaximumWidth(scaled(317))

    def sizeHint(self):
        return QtCore.QSize(scaled(317), scaled(22))

    def minimumSizeHint(self):
        return QtCore.QSize(80, scaled(22))

    def set_rms(self, rms, *, display_gain=20):
        level = float(rms)
        if not math.isfinite(level):
            level = 0.0
        level = min(1.0, max(0.0, level))
        self.clipping = level >= .98
        self.setValue(round(min(1.0, level * display_gain) * 100))
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.FontChange:
            self.setMaximumWidth(scaled(317))
            self.updateGeometry()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(.45)
        total = max(1, self.maximum() - self.minimum())
        lit = math.ceil(max(0, self.value() - self.minimum()) / total * 40)
        gap = min(scaled(3), max(.5, self.width() / 80))
        width = max(.5, (self.width() - 39 * gap) / 40)
        height = min(self.height(), scaled(18))
        for index in range(40):
            active = index < lit
            role = "signal" if active and self.clipping and index >= 34 else "ink" if active else "sunk"
            painter.setBrush(color(self, role))
            painter.setPen(QtGui.QPen(color(self, "ink"), 1) if high_contrast(self) else QtCore.Qt.NoPen)
            painter.drawRoundedRect(QtCore.QRectF(index * (width + gap), (self.height() - height) / 2, width, height), scaled(1.5), scaled(1.5))


class Progress(QtWidgets.QProgressBar):
    """Existing progress API, with the readable caption outside the six-pixel track."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.caption = Label("", "caption", self)
        self.setTextVisible(False)
        self.setMaximumHeight(scaled(6))
        self.valueChanged.connect(self._caption)
        self._caption()

    def setFormat(self, text):
        super().setFormat(text)
        if hasattr(self, "caption"):
            self._caption()

    def setRange(self, minimum, maximum):
        super().setRange(minimum, maximum)
        if hasattr(self, "caption"):
            self._caption()

    def reset(self):
        super().reset()
        if hasattr(self, "caption"):
            self._caption()

    def _caption(self, *_args):
        if self.maximum() <= self.minimum():
            self.caption.setText("Preparing…")
        else:
            percentage = max(0, round((self.value() - self.minimum()) / (self.maximum() - self.minimum()) * 100))
            text = self.format().replace("%p", str(percentage)).replace("%v", str(max(0, self.value()))).replace("%m", str(self.maximum()))
            self.caption.setText(text)


class StatCard(Card):
    def __init__(self, title, unit="", caption="", parent=None):
        super().__init__(parent, name=title)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(8)
        self.label = Label(title.upper(), "label", self)
        self.value = Label("0", "readout", self, wrap=False)
        self.unit = Label(unit, "small", self)
        self.body.addWidget(self.label)
        row = AdaptiveRow()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.value)
        row.addWidget(self.unit, 1, QtCore.Qt.AlignBottom)
        self.body.addLayout(row)
        self.caption = Label(caption, "caption", self)
        self.body.addWidget(self.caption)
        self._title = title

    def set_value(self, value, caption=None):
        self.value.setText(str(value))
        self.setAccessibleName(f"{self._title}: {value} {self.unit.text()}".rstrip())
        if caption is not None:
            self.caption.setText(caption)


class SaveBar(QtWidgets.QFrame):
    saved = QtCore.Signal()
    discarded = QtCore.Signal()

    def __init__(self, parent=None, *, status_label=None):
        super().__init__(parent)
        self.setProperty("saveBar", True)
        self.setAccessibleName("Unsaved changes")
        self.body = QtWidgets.QVBoxLayout(self)
        self.body.setContentsMargins(18, 6, 6, 6)
        self.body.setSpacing(4)
        self.status_label = status_label if status_label is not None else StatusLabel("", self)
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(QtCore.Qt.PlainText)
        self.status_area = QtWidgets.QScrollArea()
        self.status_area.setProperty("bare", True)
        self.status_area.viewport().setProperty("bare", True)
        self.status_area.viewport().setAutoFillBackground(False)
        self.status_area.setAccessibleName("Save validation details")
        self.status_area.setWidgetResizable(True)
        self.status_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.status_area.setWidget(self.status_label)
        self.status_area.setMaximumHeight(scaled(100))
        self.body.addWidget(self.status_area)
        self.status_timer = QtCore.QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self._fit_status)
        self.status_area.viewport().installEventFilter(self)
        if hasattr(self.status_label, "textChanged"):
            self.status_label.textChanged.connect(lambda _text: self.set_count(self.count))
        row = AdaptiveRow(compact=True)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.count_label = Label("", "button", self)
        row.addWidget(self.count_label, 1)
        self.discard_button = ActionButton("Discard", self, ghost=True)
        self.save_button = ActionButton("Save changes", self, primary=True)
        self.discard_button.clicked.connect(self.discarded)
        self.save_button.clicked.connect(self.saved)
        row.addWidget(self.discard_button)
        row.addWidget(self.save_button)
        self.body.addLayout(row)
        self._shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(28)
        self._shadow.setOffset(0, 10)
        self.setGraphicsEffect(self._shadow)
        self.set_count(0)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Resize:
            self.status_timer.start(0)
        return super().eventFilter(watched, event)

    def _fit_status(self):
        width = max(1, self.status_area.viewport().width())
        height = max(1, self.status_label.heightForWidth(width))
        self.status_label.setMinimumHeight(height)
        self.status_area.setFixedHeight(min(height + 4, scaled(80)))

    def event(self, event):
        result = super().event(event)
        if event.type() in (QtCore.QEvent.LayoutRequest, QtCore.QEvent.FontChange) and hasattr(self, "status_timer"):
            self.status_timer.start(0)
        return result

    def set_count(self, count):
        self.count = max(0, int(count))
        self.count_label.setText(f"{self.count} unsaved change{'s' if self.count != 1 else ''}")
        self.status_area.setVisible(bool(self.status_label.text()) and self.status_label.text() not in ("Saved", "Changes discarded"))
        self.status_label.show()
        self.status_timer.start(0)
        shade = color(self, "ink")
        shade.setAlphaF(.2)
        self._shadow.setColor(shade)
        self._shadow.setEnabled(not high_contrast(self))
        self.setVisible(self.count > 0)
        self.updateGeometry()


def page_layout(page, title, description="", *, actions=(), margins=(40, 24, 40, 28)):
    layout = QtWidgets.QVBoxLayout(page)
    layout.setContentsMargins(*margins)
    layout.setSpacing(24)
    header = PageHeader(title, description, page, actions=actions)
    layout.addWidget(header)
    return layout, header


def control_row(*widgets):
    container = QtWidgets.QWidget()
    container.setProperty("bare", True)
    row = AdaptiveRow(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    for widget in widgets:
        row.addWidget(widget)
    return container
