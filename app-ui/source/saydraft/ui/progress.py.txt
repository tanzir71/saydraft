"""Keep progress text legible on both sides of a themed horizontal fill."""

from PySide6 import QtCore, QtGui, QtWidgets


class ThemedProgressBar(QtWidgets.QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(QtCore.Qt.AlignCenter)

    def paintEvent(self, event):
        controller = getattr(QtWidgets.QApplication.instance(), "_saydraft_theme", None)
        if (controller is None or controller.closed or controller.current == "high-contrast"
                or self.orientation() != QtCore.Qt.Horizontal or not self.isTextVisible()):
            return super().paintEvent(event)
        option = QtWidgets.QStyleOptionProgressBar()
        self.initStyleOption(option)
        option.textVisible = False
        painter = QtWidgets.QStylePainter(self)
        painter.drawControl(QtWidgets.QStyle.CE_ProgressBar, option)
        text = self.text()
        if text:
            rect = self.style().subElementRect(QtWidgets.QStyle.SE_ProgressBarContents, option, self)
            filled = QtCore.QRectF(rect)
            span = self.maximum() - self.minimum()
            fraction = (self.value() - self.minimum()) / span if span > 0 else 1
            width = rect.width() * max(0, min(1, fraction))
            reverse = (self.layoutDirection() == QtCore.Qt.RightToLeft) != self.invertedAppearance()
            if reverse:
                filled.setLeft(filled.right() - width)
            else:
                filled.setWidth(width)
            painter.setFont(self.font())
            painter.setPen(option.palette.color(QtGui.QPalette.Text))
            painter.drawText(rect, self.alignment(), text)
            painter.setClipRect(filled)
            painter.setPen(option.palette.color(QtGui.QPalette.HighlightedText))
            painter.drawText(rect, self.alignment(), text)
        painter.end()
