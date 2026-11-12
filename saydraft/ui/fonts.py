"""Verified bundled faces and script fallbacks; no runtime download path."""

import hashlib
import json
import logging
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2] / "assets/fonts"
ROLES = {"body": "Geist", "display": "Instrument Serif", "mono": "Geist Mono",
    "fallbacks": ["Noto Sans Bengali", "Noto Sans Arabic"]}
FAMILIES = {ROLES[role] for role in ("body", "display", "mono")} | set(ROLES["fallbacks"])
logger = logging.getLogger(__name__)


def load_manifest(root=ROOT):
    root = Path(root).resolve()
    with (root / "manifest.json").open("rb") as stream:
        raw = stream.read(128 * 1024 + 1)
    if len(raw) > 128 * 1024:
        raise ValueError("Font manifest exceeds bound")
    data = json.loads(raw)
    if (not isinstance(data, dict) or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1 or data.get("roles") != ROLES
            or data.get("repository") != "google/fonts" or not isinstance(data.get("revision"), str)
            or not re.fullmatch(r"[a-f0-9]{40}", data["revision"])):
        raise ValueError("Unsupported font manifest")
    files, seen = data.get("files"), set()
    if not isinstance(files, list) or not 1 <= len(files) <= 32:
        raise ValueError("Invalid font file set")
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("Invalid font entry")
        path = PurePosixPath(item["path"])
        if (len(path.parts) != 2 or path.is_absolute() or path.as_posix() != item["path"]
                or any(part in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.\[\],-]+", part) for part in path.parts)
                or item["path"] in seen or not (root / item["path"]).resolve().is_relative_to(root)
                or type(item.get("size")) is not int or not 0 < item["size"] <= 4 * 1024 * 1024
                or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])
                or item.get("kind") not in ("font", "license", "metadata")
                or not isinstance(item.get("family"), str) or item["family"] not in FAMILIES):
            raise ValueError("Invalid font entry")
        seen.add(item["path"])
    for family in FAMILIES:
        kinds = {item["kind"] for item in files if item.get("family") == family}
        if kinds != {"font", "license", "metadata"}:
            raise ValueError("Font family lacks its source or license")
    return data


def verify_font_assets(root=ROOT):
    root = Path(root).resolve()
    manifest = load_manifest(root)
    for item in manifest["files"]:
        path = root / item["path"]
        with path.open("rb") as stream:
            content = stream.read(item["size"] + 1)
        if len(content) != item["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError("Bundled font asset differs from its pinned bytes")
    return manifest


def role_font(role="body", *, point_size=None, italic=False, QtGui=None):
    if QtGui is None:
        from PySide6 import QtGui
    if role not in ("body", "display", "mono"):
        raise ValueError("Unknown font role")
    font = QtGui.QFont()
    font.setFamilies([ROLES[role], *ROLES["fallbacks"], "Segoe UI"])
    if point_size is not None:
        font.setPointSizeF(point_size)
    font.setItalic(italic)
    return font


def install_bundled_fonts(application, *, QtGui=None, root=ROOT):
    """Register once on the GUI thread; preserve size/weight and roll back failure."""
    cached = getattr(application, "_saydraft_font_ids", None)
    if cached is not None:
        return cached
    if QtGui is None:
        from PySide6 import QtGui
    ids = []
    previous = application.font()
    try:
        manifest = verify_font_assets(root)
        for item in manifest["files"]:
            if item["kind"] != "font":
                continue
            index = QtGui.QFontDatabase.addApplicationFont(str(Path(root) / item["path"]))
            if index < 0:
                raise ValueError("Bundled font registration failed")
            ids.append(index)
            if item["family"] not in QtGui.QFontDatabase.applicationFontFamilies(index):
                raise ValueError("Unexpected bundled font family")
        font = application.font()
        font.setFamilies([ROLES["body"], *ROLES["fallbacks"], "Segoe UI"])
        application.setFont(font)
        application._saydraft_font_ids = tuple(ids)
        return application._saydraft_font_ids
    except Exception:
        for index in reversed(ids):
            QtGui.QFontDatabase.removeApplicationFont(index)
        application.setFont(previous)
        logger.warning("Bundled fonts unavailable; using system fonts")
        return ()
