"""Retain GUI plugins without the unused PDF and virtual-keyboard runtimes."""

from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
# Filter optional plugins before PyInstaller scans their DLL dependencies.
# Removing only Qt6Pdf/Quick after analysis would leave broken plugin files.
binaries = [(source, target) for source, target in binaries
            if Path(source).name.lower() not in ('qpdf.dll', 'qtvirtualkeyboardplugin.dll')]
