import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.gallery
@pytest.mark.parametrize("scale", [1, 2])
def test_public_bar_states_render_without_desktop_or_microphone_access(tmp_path, scale):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "bar"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "QT_QPA_PLATFORM": "offscreen"}
    guarded_render = '''
import ctypes, runpy, sys, types
from PySide6 import QtWidgets
attempts = []
def forbidden(*args, **kwargs):
    attempts.append(True)
    raise AssertionError("Bar fixture attempted desktop, clipboard or microphone access")
class ForbiddenDesktop:
    def __getattr__(self, name):
        return forbidden(name)
ctypes.windll = types.SimpleNamespace(user32=ForbiddenDesktop())
QtWidgets.QApplication.clipboard = staticmethod(forbidden)
sys.modules["sounddevice"] = types.SimpleNamespace(InputStream=forbidden, query_devices=forbidden)
sys.argv = ["saydraft.ui.bar_gallery", *sys.argv[1:]]
runpy.run_module("saydraft.ui.bar_gallery", run_name="__main__")
assert not attempts
'''
    result = subprocess.run([sys.executable, "-c", guarded_render, "--render", str(output),
        "--scale", str(scale)], cwd=root, env=env, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "report.json").read_text("utf-8"))
    assert report["platform"] == "offscreen" and report["network_guard_enabled"]
    assert not report["active_application_read"] and not report["owner_clipboard_accessed"]
    assert not report["microphone_opened"]
    from PySide6.QtGui import QImage
    for theme in report["themes"]:
        assert len(theme["states"]) == 12
        states = {row["state"]: row for row in theme["states"]}
        assert (states["idle"]["width"], states["idle"]["height"]) == (36, 8)
        assert (states["hover"]["width"], states["hover"]["height"]) == (160, 32)
        assert (states["listening"]["width"], states["listening"]["height"]) == (164, 36)
        assert states["hands-free"]["target"] == "stop"
        assert states["mic-error"]["target"] == states["model-error"]["target"] == "fix"
        assert states["listening"]["target"] is None and states["processing"]["target"] is None
        assert states["preview"]["height"] == 68
        for row in states.values():
            image = QImage(str(output / row["file"]))
            assert not image.isNull()
            assert image.width() == row["width"] * scale
            assert image.height() == row["height"] * scale
        if scale == 1:
            actual = QImage(str(output / theme["atlas"])).convertToFormat(QImage.Format_RGBA8888)
            expected = QImage(str(root / "tests/fixtures/bar" / theme["atlas"])).convertToFormat(QImage.Format_RGBA8888)
            assert not expected.isNull()
            assert actual.size() == expected.size()
            assert bytes(actual.constBits()) == bytes(expected.constBits())
