"""Render small, legible multi-resolution Windows icons from vector geometry."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import struct
from PySide6 import QtCore, QtGui, QtWidgets

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 48, 64, 256)


def render(size, state, tokens):
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.scale(size / 32, size / 32)
    painter.setPen(QtGui.QPen(QtGui.QColor(tokens["fg"]), 1.25))
    painter.setBrush(
        QtGui.QColor(tokens["signal"] if state == "recording" else tokens["bg"])
    )
    painter.drawEllipse(QtCore.QRectF(1.5, 1.5, 29, 29))
    painter.setPen(
        QtGui.QPen(
            QtGui.QColor(tokens["fg"]), 2.5, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap
        )
    )
    if state == "processing":
        for x, height in ((10, 8), (16, 15), (22, 11)):
            painter.drawLine(
                QtCore.QPointF(x, 16 - height / 2), QtCore.QPointF(x, 16 + height / 2)
            )
    else:
        painter.setBrush(QtGui.QColor(tokens["fg"]))
        painter.drawRoundedRect(QtCore.QRectF(13, 7, 6, 12), 3, 3)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawArc(QtCore.QRectF(9, 10, 14, 14), 180 * 16, 180 * 16)
        painter.drawLine(QtCore.QPointF(16, 24), QtCore.QPointF(16, 27))
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
