"""Render public Bar fixtures offscreen, without inspecting another application."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess


def render(output: Path, scale: int = 1):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_STYLE_OVERRIDE"] = "Fusion"
    os.environ["QT_SCALE_FACTOR"] = str(scale)
    from PySide6 import QtCore, QtGui, QtWidgets
    from saydraft.privacy.netguard import NetworkGuard
    from .fonts import install_bundled_fonts
    from .theme import install_theme
    from .pill import SaydraftPill

    NetworkGuard.install()
    output.mkdir(parents=True, exist_ok=False)
    app = QtWidgets.QApplication([])
    assert app.platformName() == "offscreen"
    assert len(install_bundled_fonts(app)) == 8
    theme = install_theme(app, mode="light")
    assert theme is not None
    states = ("idle", "hover", "preparing", "listening", "hands-free", "preview", "processing",
              "cleaning", "not-inserted", "not-saved", "mic-error", "model-error", "command")
    report = {"platform": app.platformName(), "scale": scale,
        "network_guard_enabled": bool(NetworkGuard._originals), "active_application_read": False,
        "owner_clipboard_accessed": False, "microphone_opened": False, "themes": []}
    for mode, background, foreground in (("light", "#F5F2E9", "#141414"), ("dark", "#111111", "#F5F2E9")):
        theme.set_mode(mode)
        atlas = QtGui.QImage(920 * scale, (40 + len(states) * 85) * scale, QtGui.QImage.Format_ARGB32_Premultiplied)
        atlas.setDevicePixelRatio(scale)
        atlas.fill(QtGui.QColor(background))
        painter = QtGui.QPainter(atlas)
        font = QtGui.QFont("Geist")
        font.setPixelSize(16)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(foreground))
        rows = []
        for index, state in enumerate(states):
            ticks = [100.]
            bar = SaydraftPill(clock=lambda: ticks[0],
                screen_geometry_provider=lambda: QtCore.QRect(-1600, -200, 1600, 1000))
            if state in ("idle", "hover"):
                bar.show_idle()
                if state == "hover":
                    bar.set_hovered(True)
            elif state == "preparing":
                bar.show_preparing()
            else:
                bar.show_recording(hands_free=state == "hands-free", command=state == "command")
                bar.update_level(.09)
                ticks[0] += .060
                bar.advance_frame()
                if state == "preview":
                    bar.update_preview("This is an illustrative public preview, with the most recent sixty characters.")
                elif state in ("processing", "cleaning"):
                    bar.show_processing()
                    ticks[0] += 1.75 if state == "cleaning" else .5
                    bar.advance_frame()
                elif state in ("not-inserted", "not-saved"):
                    bar.show_not_inserted("focus_changed" if state == "not-inserted" else "history_unavailable",
                        saved=state == "not-inserted")
                elif state in ("mic-error", "model-error"):
                    bar.show_error("No microphone" if state == "mic-error" else "Speech model unavailable")
            app.processEvents()
            image = bar.render_image()
            filename = f"{mode}-{state}.png"
            assert image.save(str(output / filename))
            y = 28 + index * 85
            painter.drawText(QtCore.QRect(24, y, 166, 68), QtCore.Qt.AlignVCenter, state.replace("-", " ").capitalize())
            painter.drawImage(QtCore.QPoint(200, y + (68 - bar.height()) // 2), image)
            rows.append({"state": state, "file": filename, "width": bar.width(), "height": bar.height(),
                "device_width": image.width(), "device_height": image.height(),
                "target": bar.target.kind if bar.target.isVisible() else None})
            bar.hide()
            bar.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        painter.end()
        name = f"{mode}-bar.png"
        assert atlas.save(str(output / name))
        report["themes"].append({"name": mode, "atlas": name, "states": rows})
    theme.close()
    report["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    report["source_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", type=Path, required=True, help="Write public fixture images to a new directory")
    parser.add_argument("--scale", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    render(args.render, args.scale)


if __name__ == "__main__":
    main()
