"""Developer component gallery with public fixtures and offscreen theme exports."""

import argparse
import json
import os
from pathlib import Path
import subprocess


def build_gallery(controller):
    from PySide6 import QtCore, QtWidgets
    from saydraft.config import default_config
    from saydraft.dictation.glossary import Glossary
    from .dictionary_toast import DictionaryToast
    from .styles_page import StylesPage
    from .progress import ThemedProgressBar

    window = QtWidgets.QWidget()
    window.setWindowTitle("Saydraft component gallery")
    layout = QtWidgets.QVBoxLayout(window)
    layout.setContentsMargins(24, 24, 24, 24)
    top = QtWidgets.QHBoxLayout()
    title = QtWidgets.QLabel("A place for your words.")
    title.setProperty("role", "display")
    top.addWidget(title, 1)
    theme = QtWidgets.QComboBox()
    theme.setAccessibleName("Gallery appearance")
    for label, value in (("Follow Windows", "system"), ("Light", "light"), ("Dark", "dark")):
        theme.addItem(label, value)
    theme.setCurrentIndex(theme.findData(controller.mode))
    theme.currentIndexChanged.connect(lambda _index: controller.set_mode(theme.currentData()))
    top.addWidget(theme)
    layout.addLayout(top)
    note = QtWidgets.QLabel("Public fixtures only · no microphone, clipboard, model downloads or saved data")
    note.setProperty("role", "muted")
    note.setWordWrap(True)
    layout.addWidget(note)
    tabs = QtWidgets.QTabWidget()
    layout.addWidget(tabs, 1)
    controls = QtWidgets.QWidget()
    form = QtWidgets.QFormLayout(controls)
    form.setSpacing(14)
    edit = QtWidgets.QLineEdit("Your voice, written clearly.")
    edit.setAccessibleName("Text example")
    form.addRow("&Text", edit)
    choice = QtWidgets.QComboBox()
    choice.addItems(["Parakeet", "All languages"])
    choice.setAccessibleName("Model example")
    form.addRow("&Model", choice)
    level = QtWidgets.QSpinBox()
    level.setRange(1, 4)
    level.setValue(3)
    level.setAccessibleName("Cleanup intensity example")
    form.addRow("&Intensity", level)
    progress = ThemedProgressBar()
    progress.setValue(60)
    progress.setAccessibleName("Download progress example")
    form.addRow("Progress", progress)
    options = QtWidgets.QHBoxLayout()
    options.addWidget(QtWidgets.QCheckBox("Keep audio (off by default)"))
    checked = QtWidgets.QCheckBox("Checked example")
    checked.setChecked(True)
    options.addWidget(checked)
    radio = QtWidgets.QRadioButton("Rules-only cleanup")
    radio.setChecked(True)
    options.addWidget(radio)
    form.addRow(options)
    buttons = QtWidgets.QHBoxLayout()
    for text, primary, enabled in (("Primary", True, True), ("Secondary", False, True), ("Unavailable", False, False)):
        button = QtWidgets.QPushButton(text)
        button.setProperty("primary", primary)
        button.setEnabled(enabled)
        buttons.addWidget(button)
    form.addRow(buttons)
    scripts = QtWidgets.QLabel("English · বাংলা যুক্তাক্ষর · العَرَبِيَّة")
    scripts.setTextFormat(QtCore.Qt.PlainText)
    scripts.setWordWrap(True)
    form.addRow("Scripts", scripts)
    toast = DictionaryToast()
    toast.setWindowFlags(QtCore.Qt.Widget)
    toast.setParent(controls)
    toast.message.setText("Add ‘Kubernetes’ to Dictionary?")
    toast.action.setText("Add")
    form.addRow(toast)
    tabs.addTab(controls, "Controls and toast")
    config = default_config()
    styles = StylesPage(config, config_provider=lambda: config, glossary_provider=Glossary)
    styles.refresh()
    tabs.addTab(styles, "Style")
    window.resize(1000, 740)
    return window, tabs, styles


def render(output, scale=1):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_STYLE_OVERRIDE"] = "Fusion"
    os.environ["QT_SCALE_FACTOR"] = str(scale)
    from PySide6 import QtGui, QtWidgets
    from .fonts import install_bundled_fonts
    from .theme import install_theme
    from saydraft.privacy.netguard import NetworkGuard

    output.mkdir(parents=True, exist_ok=False)
    app = QtWidgets.QApplication([])
    assert app.platformName() == "offscreen"
    assert len(install_bundled_fonts(app)) == 8
    controller = install_theme(app, mode="light")
    assert controller is not None
    report = {"platform": app.platformName(), "scale": scale,
        "network_guard_enabled": bool(NetworkGuard._originals), "active_application_read": False,
        "owner_clipboard_accessed": False, "themes": []}
    for mode in ("light", "dark"):
        controller.set_mode(mode)
        window, tabs, styles = build_gallery(controller)
        window.show()
        app.processEvents()
        files = []
        for index, name in ((0, "controls"), (1, "style")):
            tabs.setCurrentIndex(index)
            app.processEvents()
            path = output / f"{mode}-{name}.png"
            shot = window.grab()
            assert shot.save(str(path))
            files.append(path.name)
        report["themes"].append({"name": controller.current, "files": files,
            "image_width": shot.width(), "image_height": shot.height(),
            "body_pixels": QtGui.QFontInfo(window.font()).pixelSize(),
            "style_rows": [{"row": row, "height": styles.matrix.rowHeight(row),
                "required": styles.tones[group].sizeHint().height()} for row, group in enumerate(styles.tones)]})
        window.close()
        window.deleteLater()
        app.processEvents()
    controller.close()
    report["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    report["source_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", type=Path, help="Export both themes offscreen to a new directory")
    parser.add_argument("--scale", type=int, choices=(1, 2), default=1, help="Offscreen export density")
    args = parser.parse_args()
    from saydraft.privacy.netguard import NetworkGuard
    NetworkGuard.install()
    if args.render:
        render(args.render, args.scale)
        return
    from PySide6 import QtWidgets
    from .fonts import install_bundled_fonts
    from .theme import install_theme
    app = QtWidgets.QApplication([])
    install_bundled_fonts(app)
    controller = install_theme(app)
    if controller is None:
        raise SystemExit("Theme resources unavailable")
    window, _tabs, _styles = build_gallery(controller)
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
