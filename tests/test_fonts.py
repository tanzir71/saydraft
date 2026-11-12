import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

from saydraft.ui import fonts


def test_bundled_source_and_all_original_notices_match_pinned_bytes():
    manifest = fonts.verify_font_assets()
    assert len(manifest["files"]) == 18
    assert sum(item["kind"] == "font" for item in manifest["files"]) == 8
    for item in manifest["files"]:
        content = (fonts.ROOT / item["path"]).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        assert blob == item["git_blob"]
        if item["kind"] == "license":
            assert b"Copyright" in content and b"SIL OPEN FONT LICENSE" in content


@pytest.mark.parametrize("mutate", [
    lambda data: data.update(schema_version=2),
    lambda data: data.update(schema_version=True),
    lambda data: data["files"][0].update(path="../outside.ttf"),
    lambda data: data["files"][0].update(path="C:/outside.ttf"),
    lambda data: data["files"][0].update(size=True),
    lambda data: data["files"][0].update(size=5 * 1024 * 1024),
    lambda data: data["files"][0].update(sha256="not a digest"),
    lambda data: data["files"].append(copy.deepcopy(data["files"][0])),
    lambda data: data.update(files=[row for row in data["files"] if row["kind"] != "license"]),
])
def test_invalid_font_manifest_is_refused_before_registration(tmp_path, mutate):
    manifest = fonts.load_manifest()
    mutate(manifest)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        fonts.load_manifest(tmp_path)


def test_changed_font_or_missing_license_is_refused(tmp_path):
    root = tmp_path / "fonts"
    shutil.copytree(fonts.ROOT, root)
    manifest = fonts.load_manifest(root)
    path = root / manifest["files"][0]["path"]
    content = path.read_bytes()
    path.write_bytes(b"bad" + content[3:])
    with pytest.raises(ValueError):
        fonts.verify_font_assets(root)
    path.write_bytes(content)
    license_path = root / next(item["path"] for item in manifest["files"] if item["kind"] == "license")
    license_path.unlink()
    with pytest.raises(OSError):
        fonts.verify_font_assets(root)


@pytest.mark.parametrize("wrong_family", [False, True])
def test_partial_qt_registration_rolls_back_and_preserves_app_font(wrong_family):
    events = []
    class Database:
        @staticmethod
        def addApplicationFont(path):
            index = len(events)
            events.append(("add", Path(path).name))
            return index if index == 0 else -1
        @staticmethod
        def applicationFontFamilies(index):
            return ["Different family"] if wrong_family else ["Geist"]
        @staticmethod
        def removeApplicationFont(index):
            events.append(("remove", index))
    original = object()
    restored = []
    app = NS(font=lambda: original, setFont=restored.append)
    assert fonts.install_bundled_fonts(app, QtGui=NS(QFontDatabase=Database)) == ()
    assert restored == [original] and events[-1] == ("remove", 0)
    assert not hasattr(app, "_saydraft_font_ids")


def test_fresh_process_uses_only_bundled_faces_for_roles_and_scripts(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    output = tmp_path / "font-proof"
    completed = subprocess.run([sys.executable, "-m", "tools.probe_fonts", "--output", str(output)],
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["font_count"] == 8 and report["size_preserved"] and report["weight_preserved"]
    assert report["italic_and_monospace"]
    assert all(row["missing_glyphs"] == 0 and row["families"] == [row["expected_family"]] for row in report["scripts"])
    assert not report["active_application_read"] and not report["owner_clipboard_accessed"]
