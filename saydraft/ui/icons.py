"""Small original line icons rendered from trusted paths at 100% and 200%."""

from pathlib import Path
import re

from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

_ROOT = Path(__file__).resolve().parents[2] / "assets/icons"
_CACHE = {}


def svg_icon(name, palette=None, *, size=20, tone="inkMuted"):
    """Render only bounded, bundled line art; never resolve SVG external resources."""
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", name):
        raise ValueError("Unknown icon name")
    from .theme.style import high_contrast, mode
    app = QtWidgets.QApplication.instance()
    if app is None:
        return QtGui.QIcon()
    palette = palette or app.palette()
    # Key by visible colors: the Bar creates a temporary palette each frame.
    # QPalette.cacheKey() would force SVG disk reads and rasterization at 60 Hz.
    scheme = (getattr(app, "_saydraft_ui_tokens", None) or {}).get("app", {}).get(mode(), {})
    palette_colors = tuple(palette.color(group, role).rgba() for group in (QtGui.QPalette.Active, QtGui.QPalette.Disabled)
                           for role in (QtGui.QPalette.WindowText, QtGui.QPalette.HighlightedText))
    key = (name, palette_colors, mode(), int(size), tone, scheme.get(tone), scheme.get("ink"), scheme.get("inkFaint"))
    if key in _CACHE:
        return QtGui.QIcon(_CACHE[key])
    try:
        raw = (_ROOT / f"{name}.svg").read_bytes()
        if len(raw) > 32768:
            return QtGui.QIcon()
        source = raw.decode("utf-8")
        if re.search(r"<!|<\s*(?:image|use|script|foreignObject)\b|\bhref\s*=|url\s*\(", source, re.I):
            return QtGui.QIcon()
    except (OSError, UnicodeError):
        return QtGui.QIcon()
    icon = QtGui.QIcon()
    for icon_mode, palette_role in ((QtGui.QIcon.Normal, QtGui.QPalette.WindowText),
                                    (QtGui.QIcon.Active, QtGui.QPalette.WindowText),
                                    (QtGui.QIcon.Selected, QtGui.QPalette.HighlightedText),
                                    (QtGui.QIcon.Disabled, QtGui.QPalette.WindowText)):
        if high_contrast():
            group = QtGui.QPalette.Disabled if icon_mode == QtGui.QIcon.Disabled else QtGui.QPalette.Active
            ink = palette.color(group, palette_role)
        else:
            scheme = (getattr(app, "_saydraft_ui_tokens", None) or {}).get("app", {}).get(mode(), {})
            selected = "ink" if icon_mode == QtGui.QIcon.Selected else "inkFaint" if icon_mode == QtGui.QIcon.Disabled else tone
            ink = QtGui.QColor(scheme.get(selected, palette.color(palette_role).name()))
        renderer = QtSvg.QSvgRenderer(source.replace("currentColor", ink.name()).encode("utf-8"))
        if not renderer.isValid():
            return QtGui.QIcon()
        for density in (1, 2):
            pixmap = QtGui.QPixmap(size * density, size * density)
            pixmap.setDevicePixelRatio(density)
            pixmap.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            renderer.render(painter, QtCore.QRectF(0, 0, size, size))
            painter.end()
            icon.addPixmap(pixmap, icon_mode)
    if len(_CACHE) > 256:
        _CACHE.clear()
    _CACHE[key] = QtGui.QIcon(icon)
    return icon


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
