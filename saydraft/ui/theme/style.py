"""Shared token, palette and live-font helpers for owned Qt widgets."""

from functools import lru_cache
import json
from pathlib import Path
import re

from PySide6 import QtGui, QtWidgets


@lru_cache(maxsize=1)
def _bundled_metadata():
    try:
        data = (Path(__file__).parent / "metadata.json").read_bytes()
        if len(data) > 65536:
            return {}
        value = json.loads(data)
        return value if isinstance(value, dict) and value.get("schema") == 2 else {}
    except (OSError, ValueError):
        return {}


def metadata():
    app = QtWidgets.QApplication.instance()
    return getattr(app, "_saydraft_ui_tokens", None) or _bundled_metadata()


def mode(widget=None):
    app = QtWidgets.QApplication.instance()
    selected = app.property("saydraftTheme") if app else None
    if selected in ("light", "dark", "high-contrast"):
        return selected
    palette = widget.palette() if widget is not None else app.palette() if app else QtGui.QPalette()
    return "dark" if palette.color(QtGui.QPalette.Window).lightness() < 128 else "light"


def high_contrast(widget=None):
    return mode(widget) == "high-contrast"


def body_pixels():
    app = QtWidgets.QApplication.instance()
    font = app.font() if app else QtGui.QFont()
    size = font.pixelSize()
    if size <= 0:
        size = QtGui.QFontInfo(font).pixelSize()
    if size <= 0:
        screen = app.primaryScreen() if app else None
        size = round(max(6, font.pointSizeF()) * (screen.logicalDotsPerInch() if screen else 96) / 72)
    return max(8, size)


def scaled(value):
    """Design measurements use a 14px body; never compound a heading's font."""
    return max(1, round(float(value) * body_pixels() / 14))


def parse_color(value):
    match = re.fullmatch(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)\s*\)", value)
    if match:
        red, green, blue = (int(v) for v in match.groups()[:3])
        alpha = float(match[4])
        if all(0 <= channel <= 255 for channel in (red, green, blue)) and 0 <= alpha <= 1:
            return QtGui.QColor(red, green, blue, round(alpha * 255))
    return QtGui.QColor(value)


_PALETTE_ROLES = {
    "bg": QtGui.QPalette.Window, "surface": QtGui.QPalette.Base, "field": QtGui.QPalette.Base,
    "sunk": QtGui.QPalette.Mid, "selected": QtGui.QPalette.Highlight,
    "ink": QtGui.QPalette.WindowText, "inkMuted": QtGui.QPalette.WindowText,
    "inkFaint": QtGui.QPalette.PlaceholderText, "hairline": QtGui.QPalette.WindowText,
    "inverse": QtGui.QPalette.Highlight, "onInverse": QtGui.QPalette.HighlightedText,
    "signal": QtGui.QPalette.Highlight, "signalTint": QtGui.QPalette.Highlight,
    "onSignalTint": QtGui.QPalette.HighlightedText, "ok": QtGui.QPalette.WindowText,
    "okTint": QtGui.QPalette.Base, "warn": QtGui.QPalette.WindowText,
    "warnTint": QtGui.QPalette.Base, "danger": QtGui.QPalette.WindowText,
    "dangerTint": QtGui.QPalette.Base, "windowStroke": QtGui.QPalette.WindowText,
}


def color(widget, name):
    palette = widget.palette()
    if not high_contrast(widget):
        value = metadata().get("app", {}).get(mode(widget), {}).get(name)
        if value:
            result = parse_color(value)
            if result.isValid():
                return result
    return palette.color(_PALETTE_ROLES.get(name, QtGui.QPalette.WindowText))


def bar_color(widget, name):
    roles = {"bg": "surface", "raised": "field", "fg": "ink", "fgMuted": "inkMuted",
             "hairline": "hairline", "signal": "signal", "warn": "warn", "warnTint": "warnTint",
             "danger": "danger", "dangerTint": "dangerTint"}
    value = metadata().get("bar", {}).get(name)
    if value and not high_contrast(widget):
        result = parse_color(value)
        if result.isValid():
            return result
    return color(widget, roles.get(name, "ink"))


def role_font(role="body", *, widget=None):
    app = QtWidgets.QApplication.instance()
    font = QtGui.QFont(app.font() if app else QtGui.QFont())
    aliases = {"display": "title", "eyebrow": "label", "sub": "subheading", "muted": "body", "mono": "label"}
    spec = metadata().get("type", {}).get(aliases.get(role, role))
    if not isinstance(spec, dict):
        return font
    if not high_contrast(widget):
        families = metadata().get("fonts", {})
        family = families.get(spec.get("family", "body"))
        if family:
            font.setFamilies([family, *families.get("fallbacks", []), "Segoe UI"])
    font.setPixelSize(max(8, round(body_pixels() * spec.get("ratio", 1))))
    font.setWeight(QtGui.QFont.Weight(spec.get("weight", 400)))
    if widget is not None:
        if widget.property("fontRatio") is not None:
            font.setPixelSize(max(8, round(body_pixels() * float(widget.property("fontRatio")))))
        if widget.property("fontWeight") is not None:
            font.setWeight(QtGui.QFont.Weight(int(widget.property("fontWeight"))))
    tracking = str(spec.get("tracking", "0%")).removesuffix("%")
    font.setLetterSpacing(QtGui.QFont.PercentageSpacing, 100 + float(tracking))
    return font


def set_role(widget, role):
    widget.setProperty("role", role)
    font = role_font(role, widget=widget)
    if widget.font() != font:
        widget.setFont(font)
    return widget


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
    widget.updateGeometry()


def clear_metadata_cache():
    _bundled_metadata.cache_clear()
