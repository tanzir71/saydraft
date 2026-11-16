"""A complete Qt popup style; avoid mixing branded rows with Windows menu chrome."""

from PySide6 import QtCore, QtGui, QtWidgets
from .theme.style import color, high_contrast, role_font, scaled


class TrayMenu(QtWidgets.QMenu):
    def __init__(self):
        super().__init__()
        self.setObjectName("saydraftTrayMenu")
        self._base_style = QtWidgets.QStyleFactory.create("Fusion")
        self._base_style.setParent(self)
        self.setStyle(self._base_style)
        self.setWindowFlag(QtCore.Qt.NoDropShadowWindowHint, True)
        self.aboutToShow.connect(self.refresh_appearance)
        self.refresh_appearance()

    def refresh_appearance(self):
        native = high_contrast(self)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, not native)
        self.setFont(role_font("body", widget=self))
        self.setMinimumWidth(scaled(240))
        if native:
            self.setStyleSheet("")
            return

        def ink(name):
            return color(self, name).name()

        self.setStyleSheet(f"""
QMenu#saydraftTrayMenu {{ background: transparent; border: none; padding: 7px; }}
QMenu#saydraftTrayMenu::item {{ color: {ink("ink")}; background: transparent; border: none; border-radius: 6px; padding: 9px 16px 9px 36px; min-height: 18px; }}
QMenu#saydraftTrayMenu::item:selected {{ background: {ink("field")}; }}
QMenu#saydraftTrayMenu::item:disabled {{ color: {ink("inkMuted")}; }}
QMenu#saydraftTrayMenu::separator {{ height: 1px; background: {ink("hairline")}; margin: 5px 8px; }}
QMenu#saydraftTrayMenu::icon {{ left: 10px; }}
""")

    def paintEvent(self, event):
        if not high_contrast(self):
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setBrush(color(self, "surface"))
            painter.setPen(QtGui.QPen(color(self, "hairline"), 1))
            painter.drawRoundedRect(
                QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10
            )
            painter.end()
        super().paintEvent(event)
