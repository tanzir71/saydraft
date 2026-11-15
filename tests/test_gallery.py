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
        env=env, capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["platform"] == "offscreen" and report["network_guard_enabled"]
    assert not report["active_application_read"] and not report["owner_clipboard_accessed"]
    assert {theme["name"] for theme in report["themes"]} == {"light", "dark"}
    for theme in report["themes"]:
        assert theme["body_pixels"] >= 14
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
    snapshots = json.loads((Path(__file__).parent / "fixtures/gallery/catalog.json").read_text("utf-8"))
    expected = snapshots["scales"][str(scale)]
    actual = {row["file"]: row["pixel_sha256"] for row in report["scenes"]}
    assert actual.keys() == expected.keys(), "Gallery state inventory changed; review its snapshots explicitly"
    assert actual == expected, [name for name in actual if actual[name] != expected[name]]
    assert {row["family"] for row in report["scenes"]} == {"bar", "toast", "hub", "setup"}
    from saydraft.ui.bar_widget import PillState
    assert {row["native_state"] for row in report["scenes"] if row["family"] == "bar"} == {state.value for state in PillState}
    for row in report["scenes"]:
        assert row["dpr"] == scale
        assert row["width"] > 0 and row["height"] > 0
        assert not QtGui.QImage(str(output / row["file"])).isNull()
    guard = json.loads(output.with_name("gallery.guard.json").read_text("utf-8"))
    assert guard["blocked_attempts"] == []
    for key in ("real_audio_sdk_imported", "owner_profile_used", "owner_clipboard_used",
                "owner_native_input_used", "device_enumeration", "microphone_used"):
        assert guard[key] is False, key
