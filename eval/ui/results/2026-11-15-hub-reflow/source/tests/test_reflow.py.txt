import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from saydraft.ui.reflow import AdaptiveRow, WrapCheckBox, WrapPushButton, wrapped_text
from saydraft.ui.fonts import install_bundled_fonts, role_font

APP = None


@pytest.fixture
def app():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    original = QtGui.QFont(APP.font())
    install_bundled_fonts(APP)
    font = role_font("body")
    font.setPixelSize(32)
    APP.setFont(font)
    yield APP
    APP.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    APP.setFont(original)


def test_wrap_preserves_unicode_clusters_and_original_hard_breaks(app):
    text = "Choose বাংলা العربية 👩🏽‍💻 中文 automatically\nSecond line"
    output = wrapped_text(text, app.font(), 160)
    assert output.count("\n") > 1
    assert output.replace("\n", "").replace(" ", "") == text.replace("\n", "").replace(" ", "")
    assert "👩🏽‍💻" in output and "\ufffd" not in output


@pytest.mark.parametrize("kind", [WrapCheckBox, WrapPushButton])
def test_native_wrapped_button_keeps_label_name_keyboard_and_height(app, kind):
    window = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(window)
    text = "Download or enable this experimental speech enhancement"
    button = kind(text)
    layout.addWidget(button)
    layout.addStretch()
    window.resize(230, 400)
    window.show()
    app.processEvents()
    assert button.text() == text
    assert button.accessibleName() == text
    assert QtGui.QAccessible.queryAccessibleInterface(button).text(QtGui.QAccessible.Name) == text
    assert button.height() >= button.heightForWidth(button.width())
    assert '\n' in QtWidgets.QAbstractButton.text(button)
    if kind is WrapCheckBox:
        button.setFocus()
        QtTest.QTest.keyClick(button, QtCore.Qt.Key_Space)
        assert button.isChecked()
    else:
        clicked = []
        button.clicked.connect(lambda: clicked.append(True))
        button.setFocus()
        QtTest.QTest.keyClick(button, QtCore.Qt.Key_Space)
        assert clicked == [True]
    button.setAccessibleName("Specific action")
    button.setText("A shorter action")
    app.processEvents()
    assert button.text() == "A shorter action" and button.accessibleName() == "Specific action"
    window.close()
    window.deleteLater()


def test_row_stacks_and_restores_without_changing_widget_order(app):
    window = QtWidgets.QWidget()
    root = QtWidgets.QVBoxLayout(window)
    row = AdaptiveRow()
    buttons = [WrapPushButton(text) for text in ["Refresh inputs", "Test microphone"]]
    for button in buttons:
        row.addWidget(button)
    root.addLayout(row)
    root.addStretch()
    window.resize(340, 300)
    window.show()
    app.processEvents()
    assert row.direction() == QtWidgets.QBoxLayout.TopToBottom
    assert buttons[0].geometry().bottom() < buttons[1].geometry().top()
    window.resize(1000, 300)
    app.processEvents()
    assert row.direction() == QtWidgets.QBoxLayout.LeftToRight
    assert buttons[0].geometry().right() < buttons[1].geometry().left()
    window.close()
    window.deleteLater()
