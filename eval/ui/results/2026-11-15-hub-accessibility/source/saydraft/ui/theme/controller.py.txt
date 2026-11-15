"""Follow Qt's platform appearance hints without overriding Windows preferences."""

import json
from pathlib import Path

from PySide6 import QtCore, QtGui


class ThemeController(QtCore.QObject):
    changed = QtCore.Signal(str)

    def __init__(self, application, *, mode="system", style_hints=None, root=None):
        mode = self._validate_mode(mode)
        root = Path(root) if root is not None else Path(__file__).parent
        metadata = json.loads(self._read(root / "metadata.json"))
        size = metadata.get("bodySizePx")
        if type(metadata.get("schema")) is not int or metadata["schema"] != 1 or type(size) not in (int, float) or not 8 <= size <= 64:
            raise ValueError("Invalid theme metadata")
        sheets = {name: self._read(root / file) for name, file in (("light", "tokens.qss"), ("dark", "tokens-dark.qss"))}
        for name in ("check", "radio", "down", "up"):
            for theme in ("light", "dark"):
                self._read(root / f"{name}-{theme}.svg")
        super().__init__(application)
        self.application = application
        self.closed = False
        self.mode = mode
        self.current = None
        self.hints = style_hints or application.styleHints()
        self.accessibility = self.hints.accessibility()
        self.original_sheet = application.styleSheet()
        self.resize_base = None
        self.applied_sheet = self.applied_font = None
        self.fallback = "dark" if application.palette().color(QtGui.QPalette.Window).lightness() < 128 else "light"
        self.body_size = round(size)
        self.sheets = sheets
        self.icon_root = str(root.resolve())
        self.previous_paths = None
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.refresh)
        self.connections = []
        self.quit_connected = self.started = False

    @staticmethod
    def _read(path):
        with path.open("r", encoding="utf-8") as stream:
            content = stream.read(65537)
        if not content.strip() or len(content) > 65536:
            raise ValueError("Invalid theme resource")
        return content

    @staticmethod
    def _validate_mode(mode):
        if mode not in ("system", "light", "dark"):
            raise ValueError("Unknown theme mode")
        return mode

    def start(self):
        if self.started or self.closed:
            return
        self.previous_paths = QtCore.QDir.searchPaths("saydraftTheme")
        QtCore.QDir.setSearchPaths("saydraftTheme", [self.icon_root])
        for signal in (self.hints.colorSchemeChanged, self.accessibility.contrastPreferenceChanged):
            signal.connect(self.schedule)
            self.connections.append(signal)
        self.application.aboutToQuit.connect(self.close)
        self.quit_connected = self.started = True
        self.refresh()

    def _body_font(self, native=False):
        if native:
            if self.applied_font is not None and self.application.font() == self.applied_font:
                self.application.setFont(self.resize_base)
            self.applied_font = None
        else:
            font = QtGui.QFont(self.application.font())
            if QtGui.QFontInfo(font).pixelSize() < self.body_size:
                self.resize_base = QtGui.QFont(font)
                font.setPixelSize(self.body_size)
                self.application.setFont(font)
                self.applied_font = font

    def set_mode(self, mode):
        self.mode = self._validate_mode(mode)
        self.refresh()

    def schedule(self, *_args):
        # The platform palette is still old during colorSchemeChanged. Defer and
        # coalesce on a parented timer; no callback survives controller closure.
        if not self.closed:
            self.timer.start()

    def refresh(self):
        if self.closed:
            return
        if self.accessibility.contrastPreference() == QtCore.Qt.ContrastPreference.HighContrast:
            current = "high-contrast"
        elif self.mode != "system":
            current = self.mode
        else:
            current = {QtCore.Qt.ColorScheme.Dark: "dark", QtCore.Qt.ColorScheme.Light: "light"}.get(self.hints.colorScheme(), self.fallback)
        if current == self.current:
            return
        self.current = current
        self._body_font(native=current == "high-contrast")
        sheet = self.original_sheet
        if current != "high-contrast":
            sheet += "\n" + self.sheets[current]
        self.applied_sheet = sheet
        self.application.setStyleSheet(sheet)
        self.changed.emit(current)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.timer.stop()
        for signal in self.connections:
            try:
                signal.disconnect(self.schedule)
            except (RuntimeError, TypeError):
                pass
        if self.quit_connected:
            self.application.aboutToQuit.disconnect(self.close)
        if self.applied_sheet is not None and self.application.styleSheet() == self.applied_sheet:
            self.application.setStyleSheet(self.original_sheet)
        if self.applied_font is not None and self.application.font() == self.applied_font:
            self.application.setFont(self.resize_base)
        if self.previous_paths is not None and QtCore.QDir.searchPaths("saydraftTheme") == [self.icon_root]:
            QtCore.QDir.setSearchPaths("saydraftTheme", self.previous_paths)
        self.deleteLater()
