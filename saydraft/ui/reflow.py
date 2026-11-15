"""Let native buttons and rows follow the available width and application font."""

from PySide6 import QtCore, QtGui, QtWidgets


def wrapped_text(text, font, width):
    """Insert display line breaks using Qt shaping, preserving the source text."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        layout = QtGui.QTextLayout(paragraph, font)
        option = QtGui.QTextOption()
        option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        encoded = paragraph.encode("utf-16-le")
        layout.beginLayout()
        while (line := layout.createLine()).isValid():
            line.setLineWidth(max(1, width))
            start, end = line.textStart(), line.textStart() + line.textLength()
            lines.append(encoded[start * 2:end * 2].decode("utf-16-le").rstrip())
        layout.endLayout()
    return "\n".join(lines)


class _NativeWrap:
    def __init__(self, text="", parent=None):
        self._wrap_ready = False
        self._source_text, self._wrapping = str(text), False
        super().__init__(text, parent)
        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        if text:
            self.setAccessibleName(text)
        self._wrap_ready = True
        self._rewrap()

    def text(self):
        return self._source_text

    def setText(self, text):
        previous = self._source_text
        self._source_text = str(text)
        if not self.accessibleName() or self.accessibleName() == previous:
            self.setAccessibleName(self._source_text)
        self._rewrap()
        self.updateGeometry()

    def _text_size(self, text):
        option = QtWidgets.QStyleOptionButton()
        self.initStyleOption(option)
        option.text = text
        size = self.fontMetrics().size(QtCore.Qt.TextShowMnemonic, text)
        if not option.icon.isNull():
            size.setWidth(size.width() + option.iconSize.width() + 4)
            size.setHeight(max(size.height(), option.iconSize.height()))
        return self.style().sizeFromContents(self._contents_type, option, size, self)

    def _for_width(self, width):
        extra = self._text_size(self._source_text).width() - self.fontMetrics().size(
            QtCore.Qt.TextShowMnemonic, self._source_text).width()
        return wrapped_text(self._source_text, self.font(), width - extra)

    def sizeHint(self):
        return self._text_size(self._source_text)

    def minimumSizeHint(self):
        hint = self.sizeHint()
        hint.setWidth(min(hint.width(), self._text_size("W").width()))
        return hint

    def heightForWidth(self, width):
        return self._text_size(self._for_width(width)).height()

    def _rewrap(self):
        if not self._wrap_ready or self._wrapping:
            return
        self._wrapping = True
        try:
            display = self._for_width(self.width())
            if super().text() != display:
                super().setText(display)
        finally:
            self._wrapping = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rewrap()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.FontChange, QtCore.QEvent.StyleChange):
            self._rewrap()
            self.updateGeometry()


class WrapCheckBox(_NativeWrap, QtWidgets.QCheckBox):
    _contents_type = QtWidgets.QStyle.CT_CheckBox


class WrapPushButton(_NativeWrap, QtWidgets.QPushButton):
    _contents_type = QtWidgets.QStyle.CT_PushButton


class AdaptiveRow(QtWidgets.QBoxLayout):
    """Keep a normal horizontal row, stacking controls when their labels won't fit."""

    def __init__(self, parent=None, *, compact=False):
        super().__init__(QtWidgets.QBoxLayout.LeftToRight, parent)
        self.compact = compact

    def _items(self):
        return [self.itemAt(index) for index in range(self.count()) if not self.itemAt(index).isEmpty()]

    def _gap(self):
        return max(0, self.spacing())

    def _stacked(self, width):
        left, _, right, _ = self.getContentsMargins()
        items = self._items()
        available = max(1, width - left - right)
        gap = self._gap() * max(0, len(items) - 1)
        natural = sum(item.sizeHint().width() for item in items) + gap
        if natural > available:
            return True
        if not self.compact or not items:
            return False
        # An Ignored, word-wrapped status label has a zero width hint. Account
        # for its allocated stretch and choose the arrangement with less height.
        stretches = [self.stretch(index) for index in range(self.count()) if not self.itemAt(index).isEmpty()]
        total = sum(stretches)
        horizontal, vertical = [], []
        for item, stretch in zip(items, stretches):
            extra = (available - natural) * stretch // total if total else 0
            horizontal.append(item.heightForWidth(max(1, item.sizeHint().width() + extra))
                              if item.hasHeightForWidth() else item.sizeHint().height())
            vertical.append(item.heightForWidth(available) if item.hasHeightForWidth() else item.sizeHint().height())
        return sum(vertical) + gap < max(horizontal, default=0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        left, top, right, bottom = self.getContentsMargins()
        stacked = self._stacked(width)
        heights = [item.heightForWidth(max(1, width - left - right) if stacked else item.sizeHint().width())
                   if item.hasHeightForWidth() else item.sizeHint().height() for item in self._items()]
        return top + bottom + (sum(heights) + self._gap() * max(0, len(heights) - 1) if stacked else max(heights, default=0))

    def minimumSize(self):
        left, top, right, bottom = self.getContentsMargins()
        items = self._items()
        heights = [item.minimumSize().height() for item in items]
        height = (sum(heights) + self._gap() * max(0, len(items)-1)
                  if self.direction() == QtWidgets.QBoxLayout.TopToBottom else max(heights, default=0))
        return QtCore.QSize(left + right + max((item.minimumSize().width() for item in items), default=0),
                            top + bottom + height)

    def setGeometry(self, rect):
        direction = QtWidgets.QBoxLayout.TopToBottom if self._stacked(rect.width()) else QtWidgets.QBoxLayout.LeftToRight
        if direction != self.direction():
            self.setDirection(direction)
        super().setGeometry(rect)
