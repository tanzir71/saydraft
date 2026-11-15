"""Small original line icons rendered from trusted paths at 100% and 200%."""

from PySide6 import QtCore, QtGui, QtSvg


def line_icon(paths, palette):
    icon = QtGui.QIcon()
    for mode, role in ((QtGui.QIcon.Normal, QtGui.QPalette.WindowText), (QtGui.QIcon.Selected, QtGui.QPalette.HighlightedText)):
        color = palette.color(role).name()
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round">{paths}</svg>'
        pixmap = QtGui.QPixmap(40, 40)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        QtSvg.QSvgRenderer(svg.encode()).render(painter, QtCore.QRectF(0, 0, 20, 20))
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon
