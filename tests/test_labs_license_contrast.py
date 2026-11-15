"""Readable native license links across live appearance and font changes."""

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.asr.model_ids import PREVIEW_MODEL
from saydraft.config import default_config
from saydraft.models.manifest import get_model
from saydraft.ui.fonts import install_bundled_fonts
from saydraft.ui.labs_page import LabsPage
from saydraft.ui.theme import install_theme
from tests.test_theme import Hints


def contrast(left, right):
    def luminance(color):
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
                  for value in channels]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    values = sorted([luminance(left), luminance(right)])
    return (values[1] + .05) / (values[0] + .05)


def anchors(label):
    document = QtGui.QTextDocument()
    document.setDefaultFont(label.font())
    document.setHtml(label.text())
    result = []
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isAnchor():
                result.append((fragment.charFormat().anchorHref(), fragment.charFormat().foreground().color()))
            iterator += 1
        block = block.next()
    return result


@pytest.mark.parametrize("pixels", [16, 32])
def test_existing_labs_license_links_remain_readable_through_live_theme_changes(tmp_path, pixels):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert install_bundled_fonts(app)
    previous = (app.styleSheet(), QtGui.QPalette(app.palette()), QtGui.QFont(app.font()))
    app.setStyleSheet("")
    hints = Hints()
    theme = install_theme(app, mode="light", style_hints=hints)
    calls = []
    page = LabsPage(default_config(), callback=lambda *args: calls.append(True), report_loader=lambda: None)
    page.resize(880, 800)
    page.show()
    model = get_model(PREVIEW_MODEL)
    expected = [model["license_url"], model["source"]]
    try:
        for index, mode in enumerate(("light", "dark", "high-contrast", "light", "dark")):
            native = QtGui.QPalette(previous[1])
            if mode == "high-contrast":
                for group in (QtGui.QPalette.Active, QtGui.QPalette.Inactive, QtGui.QPalette.Disabled):
                    for role in (QtGui.QPalette.Window, QtGui.QPalette.Base, QtGui.QPalette.Button):
                        native.setColor(group, role, QtGui.QColor("black"))
                    for role in (QtGui.QPalette.WindowText, QtGui.QPalette.Text, QtGui.QPalette.ButtonText):
                        native.setColor(group, role, QtGui.QColor("yellow"))
            app.setPalette(native)
            hints.contrast = (QtCore.Qt.ContrastPreference.HighContrast if mode == "high-contrast"
                              else QtCore.Qt.ContrastPreference.NoPreference)
            theme.set_mode("light" if mode == "high-contrast" else mode)
            font = QtGui.QFont(app.font())
            font.setPixelSize(pixels)
            app.setFont(font)
            for _ in range(5):
                app.processEvents()
            assert QtGui.QFontInfo(page.license.font()).pixelSize() == pixels
            image = page.license.grab().toImage()
            assert image.save(str(tmp_path / f"{index}-{mode}-{pixels}.png"))
            background = page.grab().toImage().pixelColor(0, 0)
            links = anchors(page.license)
            assert [url for url, _ in links] == expected
            assert all(contrast(color, background) >= 4.5 for _, color in links), (
                mode, [(url, color.name(), background.name()) for url, color in links])
            assert page.license.focusPolicy() != QtCore.Qt.NoFocus
            assert page.license.accessibleName() == "English preview model license and credits"
            assert not calls and page.task is None
    finally:
        page.close()
        page.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        theme.close()
        app.setStyleSheet(previous[0])
        app.setPalette(previous[1])
        app.setFont(previous[2])
