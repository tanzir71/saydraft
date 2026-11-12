import json
from pathlib import Path
import shutil

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.ui.theme import install_theme
from saydraft.ui.theme.controller import ThemeController

APP = None


class Hints(QtCore.QObject):
    colorSchemeChanged = QtCore.Signal(object)
    contrastPreferenceChanged = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.scheme = QtCore.Qt.ColorScheme.Light
        self.contrast = QtCore.Qt.ContrastPreference.NoPreference

    def accessibility(self): return self
    def colorScheme(self): return self.scheme
    def contrastPreference(self): return self.contrast


@pytest.fixture
def setup_theme():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    original_sheet, original_font = APP.styleSheet(), QtGui.QFont(APP.font())
    hints = Hints()
    controllers = []
    def install(**kwargs):
        controller = install_theme(APP, style_hints=hints, **kwargs)
        if controller is not None and controller not in controllers:
            controllers.append(controller)
        return controller
    yield APP, hints, install
    for controller in controllers:
        controller.close()
    APP.setStyleSheet(original_sheet)
    APP.setFont(original_font)


def test_platform_changes_coalesce_and_high_contrast_wins(setup_theme):
    app, hints, install = setup_theme
    before = app.styleSheet()
    controller = install()
    changes = []
    controller.changed.connect(changes.append)
    assert controller.current == "light"
    hints.scheme = QtCore.Qt.ColorScheme.Dark
    hints.colorSchemeChanged.emit(hints.scheme)
    hints.colorSchemeChanged.emit(hints.scheme)
    assert controller.current == "light"
    app.processEvents()
    assert changes == ["dark"]
    assert "#111111" in app.styleSheet()
    hints.contrast = QtCore.Qt.ContrastPreference.HighContrast
    hints.contrastPreferenceChanged.emit(hints.contrast)
    app.processEvents()
    assert controller.current == "high-contrast" and app.styleSheet() == before
    controller.set_mode("light")
    assert controller.current == "high-contrast"
    hints.contrast = QtCore.Qt.ContrastPreference.NoPreference
    hints.contrastPreferenceChanged.emit(hints.contrast)
    app.processEvents()
    assert controller.current == "light"


def test_unknown_platform_and_minimum_font_restore_without_overriding_larger_text(setup_theme):
    app, hints, install = setup_theme
    hints.scheme = QtCore.Qt.ColorScheme.Unknown
    font = QtGui.QFont(app.font())
    font.setPixelSize(10)
    font.setWeight(QtGui.QFont.DemiBold)
    app.setFont(font)
    controller = install()
    assert controller.current == controller.fallback
    assert app.font().pixelSize() == 16 and app.font().weight() == QtGui.QFont.DemiBold
    hints.contrast = QtCore.Qt.ContrastPreference.HighContrast
    controller.refresh()
    assert app.font() == font
    hints.contrast = QtCore.Qt.ContrastPreference.NoPreference
    controller.refresh()
    assert app.font().pixelSize() == 16
    larger = QtGui.QFont(font)
    larger.setPointSizeF(24)
    app.setFont(larger)
    controller.set_mode("dark")
    controller.close()
    assert app.font() == larger


def test_close_cancels_pending_work_and_preserves_newer_app_styles(setup_theme):
    app, hints, install = setup_theme
    controller = install()
    assert install() is controller
    changes = []
    controller.changed.connect(changes.append)
    hints.scheme = QtCore.Qt.ColorScheme.Dark
    hints.colorSchemeChanged.emit(hints.scheme)
    app.setStyleSheet("QWidget { color: #123456; }")
    controller.close()
    controller.close()
    app.processEvents()
    assert changes == [] and app.styleSheet() == "QWidget { color: #123456; }"


@pytest.mark.parametrize("failure", ["missing", "missing_icon", "bad_schema", "bad_size", "empty", "oversized"])
def test_invalid_resources_leave_native_appearance_and_no_controller(setup_theme, tmp_path, failure):
    app, _hints, install = setup_theme
    root = tmp_path / "theme"
    shutil.copytree(Path(__file__).parents[1] / "saydraft/ui/theme", root)
    if failure == "missing":
        (root / "tokens.qss").unlink()
    elif failure == "missing_icon":
        (root / "check-dark.svg").unlink()
    elif failure == "bad_schema":
        (root / "metadata.json").write_text(json.dumps({"schema": True, "bodySizePx": 16}))
    elif failure == "bad_size":
        (root / "metadata.json").write_text(json.dumps({"schema": 1, "bodySizePx": 0}))
    elif failure == "empty":
        (root / "tokens-dark.qss").write_text("")
    else:
        (root / "tokens.qss").write_text("x" * 65537)
    before = app.styleSheet(), app.font()
    count = sum(isinstance(child, ThemeController) for child in app.children())
    assert install(root=root) is None
    assert (app.styleSheet(), app.font()) == before
    assert sum(isinstance(child, ThemeController) for child in app.children()) == count


def test_start_failure_rolls_back_font_and_styles(setup_theme, monkeypatch):
    app, _hints, install = setup_theme
    before = app.styleSheet(), QtGui.QFont(app.font())
    paths_before = QtCore.QDir.searchPaths("saydraftTheme")
    refresh = ThemeController.refresh
    def fail(controller):
        refresh(controller)
        raise RuntimeError("fixture")
    monkeypatch.setattr(ThemeController, "refresh", fail)
    assert install() is None
    assert (app.styleSheet(), app.font()) == before
    assert QtCore.QDir.searchPaths("saydraftTheme") == paths_before


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("value", [10, 50, 90])
@pytest.mark.parametrize("rtl,inverted", [(False, False), (True, False), (False, True)])
def test_progress_text_contrasts_with_both_fill_and_track(setup_theme, mode, value, rtl, inverted):
    from saydraft.ui.fonts import install_bundled_fonts, role_font
    from saydraft.ui.progress import ThemedProgressBar
    app, _hints, install = setup_theme
    install_bundled_fonts(app)
    app.setFont(role_font("body", point_size=12))
    install(mode=mode)
    bar = ThemedProgressBar()
    bar.setFixedSize(320, 36)
    bar.setLayoutDirection(QtCore.Qt.RightToLeft if rtl else QtCore.Qt.LeftToRight)
    bar.setInvertedAppearance(inverted)
    bar.setValue(value)
    bar.setTextVisible(False)
    bar.show()
    app.processEvents()
    background = bar.grab().toImage()
    bar.setTextVisible(True)
    app.processEvents()
    labelled = bar.grab().toImage()
    text = bar.palette().color(QtGui.QPalette.Text)
    selected = bar.palette().color(QtGui.QPalette.HighlightedText)
    changed = {text.rgba(): 0, selected.rgba(): 0}
    for y in range(bar.height()):
        for x in range(bar.width()):
            pixel = labelled.pixel(x, y)
            if pixel != background.pixel(x, y) and pixel in changed:
                changed[pixel] += 1
    if value <= 50:
        assert changed[text.rgba()] > 0
    if value >= 50:
        assert changed[selected.rgba()] > 0
    assert bar.text() == f"{value}%" and bar.value() == value
    bar.close()
    bar.deleteLater()


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("pixels", [16, 22])
def test_minimum_settings_size_keeps_controls_readable_and_reachable(setup_theme, tmp_path, monkeypatch, mode, pixels):
    from saydraft.ui.fonts import install_bundled_fonts, role_font
    from tests.test_settings_window import make_window
    app, _hints, install = setup_theme
    monkeypatch.setattr("saydraft.ui.settings_window.wispr_running", lambda: False)
    install_bundled_fonts(app)
    font = role_font("body")
    font.setPixelSize(pixels)
    app.setFont(font)
    install(mode=mode)
    window, path, _autostart = make_window(tmp_path)
    before = path.read_bytes()
    window.resize(760, 560)
    window.show()
    app.processEvents()
    scroll = window.tabs.widget(0)
    assert isinstance(scroll, QtWidgets.QScrollArea)
    assert window.speech_hotkey_edit.height() >= window.speech_hotkey_edit.sizeHint().height()
    assert scroll.verticalScrollBar().maximum() > 0
    scroll.ensureWidgetVisible(window.retain_audio_checkbox)
    app.processEvents()
    position = window.retain_audio_checkbox.mapTo(scroll.viewport(), QtCore.QPoint())
    assert position.y() >= 0 and position.y() + window.retain_audio_checkbox.height() <= scroll.viewport().height()
    assert window.apply_button.geometry().bottom() < window.height()
    assert path.read_bytes() == before
    window.close()
    window.deleteLater()
