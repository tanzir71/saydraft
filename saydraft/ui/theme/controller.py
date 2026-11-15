"""Follow Qt's platform appearance hints without overriding Windows preferences."""

import json
from pathlib import Path
import weakref

from PySide6 import QtCore, QtGui, QtWidgets


class ThemeController(QtCore.QObject):
    changed = QtCore.Signal(str)

    def __init__(self, application, *, mode="system", style_hints=None, root=None):
        mode = self._validate_mode(mode)
        root = Path(root) if root is not None else Path(__file__).parent
        metadata = json.loads(self._read(root / "metadata.json"))
        size = metadata.get("bodySizePx")
        if type(metadata.get("schema")) is not int or metadata["schema"] != 2 or type(size) not in (int, float) or not 8 <= size <= 64:
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
        self.metadata = metadata
        self.previous_metadata = getattr(application, "_saydraft_ui_tokens", None)
        self.previous_mode_property = application.property("saydraftTheme")
        self.role_fonts = {}
        self.updating_fonts = False
        self.font_timer = QtCore.QTimer(self)
        self.font_timer.setSingleShot(True)
        self.font_timer.timeout.connect(self.refresh_fonts)
        self.sheets = sheets
        self.icon_root = str(root.resolve())
        self.previous_paths = None
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.refresh)
        self.connections = []
        self.quit_connected = self.started = False
        self.owns_style_propagation = False

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
        # Qt style sheets otherwise retain earlier fonts on existing widgets
        # when the application font changes. This affects palette inheritance too.
        attribute = QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles
        if not QtCore.QCoreApplication.testAttribute(attribute):
            QtCore.QCoreApplication.setAttribute(attribute, True)
            self.owns_style_propagation = True
        self.previous_paths = QtCore.QDir.searchPaths("saydraftTheme")
        QtCore.QDir.setSearchPaths("saydraftTheme", [self.icon_root])
        self.application._saydraft_ui_tokens = self.metadata
        self.application.installEventFilter(self)
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
            from .style import body_pixels
            if body_pixels() < self.body_size:
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
        self.application.setProperty("saydraftTheme", current)
        self._body_font(native=current == "high-contrast")
        sheet = self.original_sheet
        if current != "high-contrast":
            sheet += "\n" + self.sheets[current]
        self.applied_sheet = sheet
        self.application.setStyleSheet(sheet)
        self.refresh_fonts()
        self.changed.emit(current)

    def eventFilter(self, watched, event):
        if self.closed or self.updating_fonts:
            return False
        kind = event.type()
        if kind == QtCore.QEvent.ApplicationFontChange:
            self.font_timer.start(0)
        if isinstance(watched, QtWidgets.QWidget) and kind in (
                QtCore.QEvent.Polish, QtCore.QEvent.FontChange, QtCore.QEvent.ApplicationFontChange,
                QtCore.QEvent.DynamicPropertyChange):
            self._role_font(watched)
        return False

    def _role_font(self, widget):
        role = widget.property("role")
        if not role:
            if isinstance(widget, (QtWidgets.QPushButton, QtWidgets.QToolButton)):
                role = "button"
            elif isinstance(widget, QtWidgets.QHeaderView):
                role = "label"
            else:
                return
        from .style import role_font
        font = role_font(role, widget=widget)
        if widget.font() == font:
            return
        identifier = id(widget)
        previous = self.role_fonts.get(identifier)
        original = previous[1] if previous is not None and previous[0]() is widget else QtGui.QFont(widget.font())
        self.role_fonts[identifier] = (weakref.ref(widget), original, QtGui.QFont(font))
        self.updating_fonts = True
        try:
            widget.setFont(font)
            widget.updateGeometry()
        finally:
            self.updating_fonts = False

    def refresh_fonts(self):
        if self.closed:
            return
        for widget in self.application.allWidgets():
            self._role_font(widget)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.timer.stop()
        self.font_timer.stop()
        self.application.removeEventFilter(self)
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
        for reference, original, applied in self.role_fonts.values():
            widget = reference()
            if widget is not None:
                try:
                    if widget.font() == applied:
                        widget.setFont(original)
                except RuntimeError:
                    pass  # Qt may already have destroyed a child during shutdown.
        self.role_fonts.clear()
        self.application._saydraft_ui_tokens = self.previous_metadata
        self.application.setProperty("saydraftTheme", self.previous_mode_property)
        if self.previous_paths is not None and QtCore.QDir.searchPaths("saydraftTheme") == [self.icon_root]:
            QtCore.QDir.setSearchPaths("saydraftTheme", self.previous_paths)
        if self.owns_style_propagation and QtCore.QCoreApplication.testAttribute(QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles):
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles, False)
        self.deleteLater()
