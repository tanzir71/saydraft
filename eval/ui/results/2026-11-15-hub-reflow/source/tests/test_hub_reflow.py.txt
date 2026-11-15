import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from saydraft.ui.reflow import WrapCheckBox, WrapPushButton
from tests.test_hub_accessibility import PAGES, SECTIONS, accessible_name, owned_hub as owned_hub


def walk_visible_controls(subject):
    hub, app = subject.hub, subject.app
    hub.navigation.setFocus()
    app.processEvents()
    for _ in range(160):
        widget = app.focusWidget()
        assert widget is not None and accessible_name(widget).strip()
        parent = widget.parentWidget()
        while parent is not None and parent is not hub:
            if isinstance(parent, QtWidgets.QAbstractScrollArea):
                viewport = parent.viewport()
                rect = QtCore.QRect(widget.mapTo(viewport, QtCore.QPoint()), widget.size())
                assert rect.intersects(viewport.rect()), (accessible_name(widget), type(parent).__name__, rect)
                if widget.width() <= viewport.width():
                    assert 0 <= rect.x() and rect.right() < viewport.width(), (accessible_name(widget), rect, viewport.size())
            parent = parent.parentWidget()
        QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Tab)
        app.processEvents()
        if app.focusWidget() is hub.navigation:
            return
    pytest.fail("Tab did not return to navigation")


@pytest.mark.parametrize("mode", ["light", "dark", "high-contrast"])
@pytest.mark.parametrize("px", [16, 32])
@pytest.mark.parametrize("width", [880, 1080])
def test_every_hub_view_reflows_and_scrolls_to_keyboard_focus(owned_hub, mode, px, width):
    subject, hub = owned_hub, owned_hub.hub
    subject.theme(mode, px)
    hub.resize(width, 600 if width == 880 else 720)
    for name, section in [(name, None) for name in PAGES] + [("Settings", section) for section in SECTIONS]:
        hub.show_page(name, tab=section)
        subject.settle()
        subject.app.processEvents()
        assert hub.width() == width
        assert QtGui.QFontInfo(hub.navigation.font()).pixelSize() == px
        for scroll in hub.findChildren(QtWidgets.QScrollArea):
            if scroll.isVisibleTo(hub):
                assert scroll.horizontalScrollBar().maximum() == 0, (name, section, scroll.accessibleName())
        for widget in hub.findChildren(QtWidgets.QAbstractButton):
            if isinstance(widget, (WrapCheckBox, WrapPushButton)) and widget.isVisibleTo(hub):
                assert QtGui.QFontInfo(widget.font()).pixelSize() == px, widget.text()
                assert widget.height() >= widget.heightForWidth(widget.width()), (widget.text(), widget.size())
        walk_visible_controls(subject)


def test_history_stacks_at_large_text_and_returns_to_two_panes(owned_hub):
    subject, hub = owned_hub, owned_hub.hub
    hub.show_page("History")
    for px, orientation in [(16, QtCore.Qt.Horizontal), (32, QtCore.Qt.Vertical), (16, QtCore.Qt.Horizontal)]:
        subject.theme("light", px)
        subject.app.processEvents()
        assert hub.history_page.body.orientation() == orientation
    assert hub.history_page.list_widget.minimumSizeHint().width() < hub.history_view.viewport().width()


def test_style_matrix_keeps_full_choices_and_last_row_above_its_scrollbar(owned_hub):
    subject, hub = owned_hub, owned_hub.hub
    subject.theme("dark", 32)
    hub.show_page("Style")
    subject.app.processEvents()
    page = hub.settings_page.styles_page
    matrix = page.matrix
    for column, mapping in [(1, page.tones), (2, page.levels)]:
        assert matrix.columnWidth(column) >= max(combo.sizeHint().width() for combo in mapping.values())
    assert matrix.horizontalScrollBar().maximum() > 0
    assert matrix.viewport().height() >= sum(matrix.rowHeight(row) for row in range(matrix.rowCount()))
    walk_visible_controls(subject)


@pytest.mark.parametrize("mode", ["light", "dark", "high-contrast"])
@pytest.mark.parametrize("px", [16, 32])
def test_long_setup_warning_and_save_fit_without_hiding_settings(owned_hub, mode, px):
    subject, hub = owned_hub, owned_hub.hub
    subject.theme(mode, px)
    hub.show_page("Settings", tab="Microphone")
    hub.settings_page.status_label.setText(
        "An enhancement file changed. Open Microphone to review setup, then download it again or turn enhancement off before saving.")
    for _ in range(6):
        subject.app.processEvents()
    label = hub.settings_page.status_label
    assert label.height() >= label.heightForWidth(label.width())
    assert hub.save_button.mapTo(hub, QtCore.QPoint(0, hub.save_button.height())).y() <= hub.height()
    assert hub.settings_page.tabs.currentWidget().viewport().height() > 0
