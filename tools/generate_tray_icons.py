"""Render small, legible multi-resolution Windows icons from vector geometry."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import struct
from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 48, 64, 256)


def render(size, state, tokens):
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.scale(size / 32, size / 32)
    painter.setPen(QtCore.Qt.NoPen)
    inset = 1
    ink = tokens["signal"]
    if state == "recording":
        painter.setBrush(QtGui.QColor(tokens["signal"]))
        painter.drawEllipse(QtCore.QRectF(1, 1, 30, 30))
        ink, inset = tokens["fg"], 4
    elif state == "processing":
        painter.setBrush(QtGui.QColor(tokens["bg"]))
        painter.drawRoundedRect(QtCore.QRectF(1, 1, 30, 30), 7, 7)
        inset = 4
    source = (ROOT / "assets/tray/saydraft-mark.svg").read_bytes()
    renderer = QtSvg.QSvgRenderer(source.replace(b"#FF5B3A", ink.encode("ascii")))
    assert renderer.isValid()
    renderer.render(painter, QtCore.QRectF(inset, inset, 32 - 2 * inset, 32 - 2 * inset))
    painter.end()
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(buffer.data())


def generate():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app.platformName() == "offscreen"
    tokens = json.loads((ROOT / "design/app-tokens.json").read_text(encoding="utf-8"))[
        "bar"
    ]
    for state in ("idle", "recording", "processing"):
        payloads = [render(size, state, tokens) for size in SIZES]
        offset = 6 + 16 * len(SIZES)
        entries = []
        for size, payload in zip(SIZES, payloads):
            entries.append(
                struct.pack(
                    "<BBBBHHII",
                    size % 256,
                    size % 256,
                    0,
                    0,
                    1,
                    32,
                    len(payload),
                    offset,
                )
            )
            offset += len(payload)
        (ROOT / "assets/tray" / f"mic_{state}.ico").write_bytes(
            struct.pack("<HHH", 0, 1, len(SIZES))
            + b"".join(entries)
            + b"".join(payloads)
        )


if __name__ == "__main__":
    generate()
