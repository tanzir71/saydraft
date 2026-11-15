"""Live gallery wiring, separate from production workflow acceptance."""

from pathlib import Path

import pytest
from PySide6 import QtCore, QtWidgets

from saydraft.ui.fonts import install_bundled_fonts
from saydraft.ui.gallery import build_gallery
from saydraft.ui.gallery_catalog import CatalogPanel, Fixtures, SCENES, settle
from saydraft.ui.theme import install_theme


APP = None


@pytest.mark.gallery
def test_live_gallery_selector_uses_actual_widgets_and_refreshes_on_theme_change():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    install_bundled_fonts(APP)
    controller = install_theme(APP, mode="light")
    fixtures = Fixtures()
    root = fixtures.root
    window, tabs, _styles = build_gallery(controller, fixtures=fixtures)
    try:
        window.show()
        panel = window.findChild(CatalogPanel)
        assert panel is not None
        assert panel.choice.count() == len(SCENES)
        tabs.setCurrentWidget(panel)
        index = next(i for i, scene in enumerate(SCENES) if scene.key == "hub-home")
        panel.choice.setCurrentIndex(index)
        settle()
        light = panel.preview.pixmap().toImage()
        assert not light.isNull() and light.width() == 1080
        # The same stylesheet/palette event path also handles Follow Windows.
        controller.set_mode("dark")
        settle()
        dark = panel.preview.pixmap().toImage()
        assert not dark.isNull() and dark != light
        assert fixtures.hubs[False].windowTitle() == "Saydraft"
        for scene in ["bar-listening", "toast-added", "setup-style", "hub-notes"]:
            panel.choice.setCurrentIndex(next(i for i, item in enumerate(SCENES) if item.key == scene))
            settle()
            assert not panel.preview.pixmap().isNull(), scene
        assert all(widget.testAttribute(QtCore.Qt.WA_DontShowOnScreen) for widget in fixtures.widgets)
    finally:
        window.close()
        window.deleteLater()
        fixtures.close()
        controller.close()
        APP.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not Path(root).exists(), "Disposable fixture data must be retired"
