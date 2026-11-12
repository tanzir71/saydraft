"""Render bundled font specimens offscreen without Windows-font dependencies."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtGui, QtWidgets
from saydraft.ui.fonts import ROOT, install_bundled_fonts, role_font


def probe(output):
    output.mkdir(parents=True, exist_ok=False)
    application = QtWidgets.QApplication([])
    original = application.font()
    selected = application.font()
    selected.setPointSizeF(13.5)
    selected.setWeight(QtGui.QFont.DemiBold)
    application.setFont(selected)
    ids = install_bundled_fonts(application)
    assert len(ids) == 8 and application.font().pointSizeF() == 13.5
    assert application.font().weight() == QtGui.QFont.DemiBold
    assert install_bundled_fonts(application) == ids
    restored = application.font()
    restored.setPointSizeF(original.pointSizeF())
    restored.setWeight(original.weight())
    application.setFont(restored)
    report = {"font_count": len(ids), "size_preserved": True, "weight_preserved": True, "scripts": [],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "manifest_sha256": hashlib.sha256((ROOT / "manifest.json").read_bytes()).hexdigest(),
        "active_application_read": False, "owner_clipboard_accessed": False}
    sheet = QtWidgets.QWidget()
    sheet.setStyleSheet("QWidget { background: #F5F2E9; color: #141414; }")
    layout = QtWidgets.QVBoxLayout(sheet)
    for role, text, family in (("display", "Saydraft", "Instrument Serif"),
            ("body", "Your voice, written clearly.", "Geist"), ("mono", "const text = 'Saydraft';", "Geist Mono"),
            ("body", "বাংলা ভাষা", "Noto Sans Bengali"), ("body", "বাংলা যুক্তাক্ষর", "Noto Sans Bengali"),
            ("body", "العربية", "Noto Sans Arabic"), ("body", "العَرَبِيَّة", "Noto Sans Arabic")):
        font = role_font(role, point_size=30 if role == "display" else 18)
        shaped = QtGui.QTextLayout(text, font)
        shaped.beginLayout()
        shaped.createLine().setLineWidth(600)
        shaped.endLayout()
        runs = shaped.glyphRuns()
        families = sorted({run.rawFont().familyName() for run in runs})
        assert family in families and all(glyph > 0 for run in runs for glyph in run.glyphIndexes())
        report["scripts"].append({"role": role, "expected_family": family, "families": families, "missing_glyphs": 0})
        label = QtWidgets.QLabel(text)
        label.setFont(font)
        layout.addWidget(label)
    for role in ("body", "display", "mono"):
        assert QtGui.QFontInfo(role_font(role, point_size=18, italic=True)).italic()
    mono = QtGui.QFontMetricsF(role_font("mono", point_size=16))
    assert abs(mono.horizontalAdvance("iii") - mono.horizontalAdvance("WWW")) < .01
    report["italic_and_monospace"] = True
    sheet.resize(700, 520)
    assert sheet.grab().save(str(output / "specimens.png"))
    sheet.close()
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(probe(parser.parse_args().output)))


if __name__ == "__main__":
    main()
