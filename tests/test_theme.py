import json
import gc
from pathlib import Path
import shutil

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.ui.theme import install_theme
from saydraft.ui.theme.controller import ThemeController

APP = None


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("kind", ["button", "tool", "segment", "toggle", "navigation"])
def test_clicks_hide_focus_ring_and_keyboard_navigation_restores_it(setup_theme, mode, kind, tmp_path):
    from PySide6 import QtTest
    from saydraft.ui.kit import Toggle
    from saydraft.ui.hub import HubNavigation, NavigationDelegate
    from saydraft.ui.theme.style import focus_visible

    app, _hints, install = setup_theme
    from saydraft.ui.fonts import install_bundled_fonts
    install_bundled_fonts(app)
    install(mode=mode)
    window = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(window)
    entry = QtWidgets.QLineEdit("Keyboard entry point")
    layout.addWidget(entry)
    if kind == "navigation":
        control = HubNavigation()
        control.setObjectName("hubNavigation")
        control.setItemDelegate(NavigationDelegate(control))
        item = QtWidgets.QListWidgetItem("Home")
        item.setData(QtCore.Qt.UserRole, "home")
        control.addItem(item)
        control.setCurrentRow(0)
    elif kind == "toggle":
        control = Toggle("Enable option")
    elif kind == "segment":
        control = QtWidgets.QRadioButton("Cleaned")
        control.setProperty("segment", True)
    elif kind == "tool":
        control = QtWidgets.QToolButton()
        control.setText("Open")
        control.setFocusPolicy(QtCore.Qt.StrongFocus)
    else:
        control = QtWidgets.QPushButton("Continue")
    layout.addWidget(control)
    window.resize(360, 180)
    window.show()
    window.activateWindow()
    for _ in range(5):
        app.processEvents()
    try:
        receiver = control.viewport() if kind == "navigation" else control
        point = control.visualItemRect(item).center() if kind == "navigation" else control.rect().center()
        clicks = []
        if kind != "navigation":
            control.clicked.connect(lambda *_: clicks.append(True))
        QtTest.QTest.mouseClick(receiver, QtCore.Qt.LeftButton, pos=point)
        QtTest.QTest.mouseMove(entry)
        app.processEvents()
        assert control.hasFocus(), "Mouse focus itself remains available to assistive technology"
        assert not focus_visible(control)
        assert control.property("keyboardFocus") is False
        if kind == "navigation":
            assert control.currentItem() is item
        else:
            assert clicks == [True]
        mouse = control.grab().toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
        assert mouse.save(str(tmp_path / f"{mode}-{kind}-mouse.png"))

        entry.setFocus(QtCore.Qt.MouseFocusReason)
        QtTest.QTest.keyClick(entry, QtCore.Qt.Key_Tab)
        app.processEvents()
        assert control.hasFocus() and focus_visible(control)
        keyboard = control.grab().toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
        assert keyboard.save(str(tmp_path / f"{mode}-{kind}-keyboard.png"))
        assert bytes(mouse.constBits()) != bytes(keyboard.constBits()), "Keyboard focus must remain visible"

        # Clicking a control that already has keyboard focus must remove the
        # ring too; this path does not receive another FocusIn event.
        QtTest.QTest.mouseClick(receiver, QtCore.Qt.LeftButton, pos=point)
        app.processEvents()
        assert control.hasFocus() and not focus_visible(control)
        if kind not in ("navigation", "segment"):
            QtTest.QTest.keyClick(control, QtCore.Qt.Key_Space)
            app.processEvents()
            assert focus_visible(control) and clicks == [True, True, True]
    finally:
        window.close()
        window.deleteLater()


def test_live_application_font_reaches_existing_themed_controls(setup_theme):
    app, _hints, install = setup_theme
    from saydraft.ui.fonts import install_bundled_fonts
    from saydraft.ui.reflow import WrapCheckBox, WrapPushButton
    install_bundled_fonts(app)
    controls = [QtWidgets.QCheckBox("Native"), WrapCheckBox("Wrapped"),
                QtWidgets.QPushButton("Native"), WrapPushButton("Wrapped"), QtWidgets.QListWidget()]
    controller = install(mode="light")
    try:
        for px in [16, 32, 16]:
            font = QtGui.QFont(app.font())
            font.setPixelSize(px)
            app.setFont(font)
            app.processEvents()
            assert all(QtGui.QFontInfo(widget.font()).pixelSize() == (round(px * 13 / 14) if isinstance(widget, QtWidgets.QPushButton) else px) for widget in controls)
        controller.set_mode("dark")
        app.processEvents()
        assert all(QtGui.QFontInfo(widget.font()).pixelSize() == (15 if isinstance(widget, QtWidgets.QPushButton) else 16) for widget in controls)
    finally:
        for widget in controls:
            widget.close()
            widget.deleteLater()


@pytest.mark.parametrize("initial", [False, True])
def test_theme_owns_only_its_style_propagation_attribute(setup_theme, initial):
    _app, _hints, install = setup_theme
    attribute = QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles
    original = QtCore.QCoreApplication.testAttribute(attribute)
    QtCore.QCoreApplication.setAttribute(attribute, initial)
    try:
        controller = install(mode="light")
        assert QtCore.QCoreApplication.testAttribute(attribute)
        assert controller.owns_style_propagation is (not initial)
        controller.close()
        assert QtCore.QCoreApplication.testAttribute(attribute) is initial
    finally:
        QtCore.QCoreApplication.setAttribute(attribute, original)


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
    # Retire widgets from earlier UI tests before repolishing the whole app.
    # Closed test windows can otherwise survive in Python/Qt signal cycles.
    gc.collect()
    APP.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
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
    assert "#121211" in app.styleSheet()
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
    assert app.font().pixelSize() == 14 and app.font().weight() == QtGui.QFont.DemiBold
    hints.contrast = QtCore.Qt.ContrastPreference.HighContrast
    controller.refresh()
    assert app.font() == font
    hints.contrast = QtCore.Qt.ContrastPreference.NoPreference
    controller.refresh()
    assert app.font().pixelSize() == 14
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
def test_progress_caption_stays_outside_the_track_and_readable(setup_theme, mode, value, rtl, inverted):
    from saydraft.ui.fonts import install_bundled_fonts
    from saydraft.ui.progress import ThemedProgressBar
    from saydraft.ui.theme.style import color
    app, _hints, install = setup_theme
    install_bundled_fonts(app)
    font=app.font()
    font.setPixelSize(14)
    app.setFont(font)
    install(mode=mode)
    container=QtWidgets.QWidget()
    layout=QtWidgets.QVBoxLayout(container)
    bar=ThemedProgressBar()
    layout.addWidget(bar)
    layout.addWidget(bar.caption)
    bar.setLayoutDirection(QtCore.Qt.RightToLeft if rtl else QtCore.Qt.LeftToRight)
    bar.setInvertedAppearance(inverted)
    bar.setValue(value)
    container.resize(320,80)
    container.show()
    app.processEvents()
    assert not bar.isTextVisible() and bar.height() <= 6
    assert bar.caption.isVisible() and bar.caption.text() == f"{value}%"
    assert bar.caption.geometry().top() > bar.geometry().bottom()
    assert bar.value() == value
    def luminance(ink):
        channels=[channel/255 for channel in (ink.red(),ink.green(),ink.blue())]
        linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in channels]
        return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
    foreground=luminance(color(bar.caption,"inkMuted"))
    background=luminance(color(container,"bg"))
    assert (max(foreground,background)+.05)/(min(foreground,background)+.05) >= 4.5
    bar.setRange(0,0)
    assert bar.caption.text() == "Preparing…"
    bar.hide()
    app.processEvents()
    assert not bar.caption.isVisible()
    container.close()
    container.deleteLater()


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("pixels", [16, 22])
def test_minimum_settings_size_keeps_controls_readable_and_reachable(setup_theme, tmp_path, monkeypatch, mode, pixels):
    from saydraft.ui.fonts import install_bundled_fonts, role_font
    from tests.test_settings_window import make_window
    app, _hints, install = setup_theme
    monkeypatch.setattr("saydraft.ui.settings_page.wispr_running", lambda: False)
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
    window.show_tab("Shortcuts")
    app.processEvents()
    scroll = window.tabs.currentWidget()
    assert isinstance(scroll, QtWidgets.QScrollArea)
    assert window.speech_hotkey_edit.height() >= window.speech_hotkey_edit.sizeHint().height()
    assert window.size() == QtCore.QSize(760, 560)
    scroll.ensureWidgetVisible(window.tap_lock_spin)
    app.processEvents()
    position = window.tap_lock_spin.mapTo(scroll.viewport(), QtCore.QPoint())
    assert position.y() >= 0 and position.y() + window.tap_lock_spin.height() <= scroll.viewport().height()
    assert window.apply_button.geometry().bottom() < window.height()
    assert path.read_bytes() == before
    window.close()
    window.deleteLater()


def test_large_explicit_pixel_font_survives_an_unavailable_family(setup_theme):
    app,_hints,install=setup_theme
    font=QtGui.QFont("Unavailable Saydraft test family")
    font.setPixelSize(32)
    app.setFont(font)
    install(mode="light")
    assert app.font().pixelSize() == 32
