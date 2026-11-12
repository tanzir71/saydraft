import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6 import QtGui


@pytest.mark.gallery
@pytest.mark.offline
@pytest.mark.parametrize("scale", [1, 2])
def test_fresh_gallery_renders_offline_without_clipping_and_matches_snapshots(tmp_path, scale):
    output = tmp_path / "gallery"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, "-m", "saydraft.ui.gallery", "--render", str(output), "--scale", str(scale)],
        env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["platform"] == "offscreen" and report["network_guard_enabled"]
    assert not report["active_application_read"] and not report["owner_clipboard_accessed"]
    assert {theme["name"] for theme in report["themes"]} == {"light", "dark"}
    for theme in report["themes"]:
        assert theme["body_pixels"] >= 16
        assert (theme["image_width"], theme["image_height"]) == (1000 * scale, 740 * scale)
        assert all(row["height"] >= row["required"] for row in theme["style_rows"])
        for name in theme["files"]:
            actual = QtGui.QImage(str(output / name))
            assert not actual.isNull()
            if scale == 1:
                expected = QtGui.QImage(str(Path(__file__).parent / "fixtures/gallery" / name))
                assert not expected.isNull() and actual.size() == expected.size(), name
                fmt = QtGui.QImage.Format_RGBA8888
                actual, expected = actual.convertToFormat(fmt), expected.convertToFormat(fmt)
                assert bytes(actual.constBits()) == bytes(expected.constBits()), name
