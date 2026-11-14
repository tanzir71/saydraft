"""Read-only inventory and explicitly confirmed, file-scoped model removal.

Inventory uses receipts and file sizes. Removal additionally hashes every declared
payload, checks the confirmation snapshot again, and never recursively deletes.
Unknown files, download caches and unrecognized old versions are retained.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from .downloader import verify_file
from .manifest import load_manifest, safe_filename
from .storage_lock import storage_lock


@dataclass(frozen=True)
class StorageRoot:
    path: Path
    label: str
    managed: bool = False


@dataclass(frozen=True)
class StoredFile:
    name: str
    stamp: tuple
    sha256: str | None = None


@dataclass(frozen=True)
class StoredModel:
    root: StorageRoot
    path: Path
    model_id: str
    label: str
    revision: str
    status: str
    files: tuple[StoredFile, ...]
    directory_id: tuple
    root_id: tuple

    @property
    def size(self):
        return sum(file.stamp[2] for file in self.files)


@dataclass(frozen=True)
class RootUsage:
    root: StorageRoot
    total: int
    other: int
    free: int | None
    skipped: int = 0


@dataclass(frozen=True)
class Inventory:
    models: tuple[StoredModel, ...]
    roots: tuple[RootUsage, ...]


@dataclass(frozen=True)
class RemovalResult:
    removed: int
    bytes_removed: int
    errors: tuple[str, ...] = ()


def storage_roots():
    from saydraft.model_download import default_models_dir
    roots = [StorageRoot(default_models_dir(), "App storage", True),
             StorageRoot(Path(__file__).resolve().parents[2] / "models", "Portable storage")]
    if getattr(sys, "frozen", False):
        roots.append(StorageRoot(Path(sys.executable).absolute().parent / "models", "Portable storage"))
    unique = {}
    for root in roots:
        unique.setdefault(os.path.normcase(os.path.abspath(root.path)), root)
    return tuple(unique.values())


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _identity(path):
    info = path.stat(follow_symlinks=False)
    return (info.st_dev, info.st_ino)


def _safe(root, path):
    root, path = Path(os.path.abspath(root)), Path(os.path.abspath(path))
    if str(root).startswith("\\\\") or not path.is_relative_to(root):
        return False
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return False
    return True


def _regular(root, path):
    if not _safe(root, path):
        return False
    try:
        info = path.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    except OSError:
        return False


def _json(path):
    if path.stat().st_size > 256 * 1024:
        raise ValueError("Oversized model receipt")
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_receipt(receipt):
    if (not isinstance(receipt, dict) or not isinstance(receipt.get("revision"), str)
            or not 1 <= len(receipt["revision"]) <= 160
            or any(ord(char) < 32 for char in receipt["revision"])):
        return False
    files = receipt.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= 256:
        return False
    names = set()
    for file in files:
        if (not isinstance(file, dict) or not safe_filename(file.get("path"))
                or file["path"].casefold() in names or type(file.get("size")) is not int
                or file["size"] <= 0 or not isinstance(file.get("sha256"), str)
                or re.fullmatch(r"[a-f0-9]{64}", file["sha256"]) is None):
            return False
        names.add(file["path"].casefold())
    return True


def _scan(root):
    found, skipped = {}, 0
    if not _safe(root, root):
        return found, 1
    pending = [root]
    while pending:
        folder = pending.pop()
        try:
            with os.scandir(folder) as children:
                for child in children:
                    path = Path(child.path)
                    # Windows DirEntry.stat caches zero device/inode fields;
                    # removal snapshots need the real file identity from lstat.
                    info = path.lstat()
                    if not _safe(root, path):
                        skipped += 1
                    elif stat.S_ISDIR(info.st_mode):
                        pending.append(path)
                    elif stat.S_ISREG(info.st_mode):
                        found[path] = info
        except FileNotFoundError:
            continue
        except OSError:
            skipped += 1
    return found, skipped


def _entry(root, target, model, found):
    receipt_path = target / ".verified.json"
    receipt = None
    try:
        if _regular(root.path, receipt_path):
            candidate = _json(receipt_path)
            if _valid_receipt(candidate):
                receipt = candidate
    except (OSError, ValueError, UnicodeError):
        pass
    declared = receipt["files"] if receipt else model["files"]
    files = []
    complete = receipt is not None
    if receipt is not None and receipt_path in found:
        files.append(StoredFile(receipt_path.name, _stamp(found[receipt_path])))
    for file in declared:
        path = target / file["path"]
        info = found.get(path)
        if info is not None and _regular(root.path, path):
            files.append(StoredFile(path.name, _stamp(info), file["sha256"]))
        if info is None or info.st_size != file["size"] or not _regular(root.path, path):
            complete = False
        partial, metadata = path.with_name(path.name + ".part"), path.with_name(path.name + ".part.json")
        if all(item in found and _regular(root.path, item) for item in (partial, metadata)):
            try:
                if _json(metadata) == file:
                    files.extend(StoredFile(item.name, _stamp(found[item])) for item in (partial, metadata))
            except (OSError, ValueError, UnicodeError):
                pass
    revision = receipt["revision"] if receipt else model["revision"]
    matches_catalog = receipt == {"revision": model["revision"], "files": model["files"]}
    status = ("Installed (receipt and sizes)" if complete and matches_catalog else
              "Retained receipt (sizes match)" if complete else "Partial or unverified")
    if revision != model["revision"] or model.get("_retained", False):
        status = "Retained version · " + status
    return StoredModel(root, target, model["id"], model.get("label", model["id"]), revision, status,
                       tuple(files), _identity(target), _identity(root.path))


def inventory(roots=None, models=None):
    from .layout import model_directories
    entries, usages = [], []
    models = load_manifest()["models"] if models is None else models
    for supplied in storage_roots() if roots is None else roots:
        root = StorageRoot(Path(os.path.abspath(supplied.path)), supplied.label, supplied.managed)
        found, skipped = _scan(root.path)
        receipts = {}
        for path in found:
            if path.name != ".verified.json" or not _regular(root.path, path):
                continue
            try:
                receipt = _json(path)
                if _valid_receipt(receipt):
                    receipts[path.parent] = receipt
            except (OSError, ValueError, UnicodeError):
                pass
        candidates = {}
        for model in models:
            locations = model_directories(root.path, model)
            canonical, legacy = locations[0], locations[-1]
            candidates[canonical] = candidates[legacy] = model
            version_parents = {canonical.parent}
            if model.get("role") == "llm":
                version_parents.add(legacy.parent)
            for folder, receipt in receipts.items():
                versioned = folder.parent in version_parents and folder.name == receipt["revision"]
                archived = (folder.parent in {parent / "_archive" for parent in version_parents}
                            or folder.parent == legacy.parent / "_archive" and folder.name.startswith(legacy.name + "-"))
                if versioned or archived:
                    candidates.setdefault(folder, dict(model, _retained=True))
        known = set()
        for target, model in sorted(candidates.items(), key=lambda item: str(item[0])):
            if not _safe(root.path, target) or not target.is_dir():
                continue
            try:
                entry = _entry(root, target, model, found)
            except OSError:
                skipped += 1
                continue
            entries.append(entry)
            known.update(target / file.name for file in entry.files)
        total = sum(info.st_size for info in found.values())
        free = None
        try:
            parent = root.path
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            if _safe(parent, parent):
                free = shutil.disk_usage(parent).free
        except OSError:
            pass
        usages.append(RootUsage(root, total, sum(info.st_size for path, info in found.items() if path not in known), free, skipped))
    return Inventory(tuple(entries), tuple(usages))


def protected_paths(config, active_models=()):
    """Current configured and warm models; historical versions remain independently removable."""
    from saydraft.asr.model_ids import LANGUAGE_ID_MODEL, PREVIEW_MODEL
    from saydraft.asr.router import choose_route
    from saydraft.asr.selection import configured_model_id
    from .layout import model_directories
    from saydraft.paths import resolve_data_path
    from .manifest import model_bundle
    from .runtime_ids import runtime_model_id

    identifiers = set(active_models) | {configured_model_id(config), "silero-vad-v5"}
    recording = config.get('recording', {})
    if recording.get('whisper_mode') is True and recording.get('whisper_enhancement', True) is True:
        from saydraft.audio.gtcrn import MODEL_ID
        identifiers.add(MODEL_ID)
    stt = config.get("stt", {})
    if stt.get("routing_enabled"):
        identifiers.update((LANGUAGE_ID_MODEL, choose_route(stt.get("pinned_languages", ()),
                           english_max=stt.get("english_max", False)).model_id))
        identifiers.update(row["model_id"] for row in stt.get("app_model_overrides", []))
    if config.get("labs", {}).get("live_preview"):
        identifiers.add(PREVIEW_MODEL)
    identifiers.add(runtime_model_id(config.get("llm", {}).get("backend", "cpu")))
    paths = []
    for identifier in identifiers:
        try:
            for model in model_bundle(identifier):
                paths.extend(path for root in storage_roots() for path in model_directories(root.path, model))
        except ValueError:
            continue
    llm_path = config.get("llm", {}).get("model_path")
    if llm_path:
        paths.append(resolve_data_path(llm_path))
    if stt.get("engine") == "whisper" and stt.get("model_size") not in ("base", "small", "medium", "large-v3-turbo"):
        paths.append(Path(stt.get("model_size", ".")))
    # A custom path may alias managed weights through a link. Protect both names.
    return tuple(dict.fromkeys(path for supplied in paths
                 for path in (Path(os.path.abspath(supplied)), Path(supplied).resolve())))


def removal_reason(entry, protected=()):
    if not entry.root.managed:
        return "Portable storage is read-only here."
    if not entry.files:
        return "No recognized model files to remove. Unknown files are preserved."
    if any(path == entry.path or path.is_relative_to(entry.path) or entry.path.is_relative_to(path)
           for path in map(Path, protected)):
        return "Configured or loaded by the app. Choose another model and Save, or restart to release cached models."
    return ""


def remove_model(entry, *, protected=(), roots=None):
    """Call only after the exact entry was confirmed. A changed snapshot must be reviewed again."""
    reason = removal_reason(entry, protected)
    if reason:
        raise ValueError(reason)
    permitted = storage_roots() if roots is None else roots
    if not any(root.managed and Path(os.path.abspath(root.path)) == entry.root.path for root in permitted):
        raise ValueError("Removal is limited to the app's managed model storage.")
    if not storage_lock.acquire(blocking=False):
        raise ValueError("Model setup is active. Finish or pause downloads, then refresh.")
    try:
        root, target = entry.root.path, entry.path
        if (not _safe(root, target) or target == root or _identity(root) != entry.root_id
                or _identity(target) != entry.directory_id):
            raise ValueError("Model storage changed. Refresh and review removal again.")
        def unchanged(file):
            path = target / file.name
            return (_regular(root, path) and _identity(target) == entry.directory_id
                    and _identity(root) == entry.root_id and _stamp(path.lstat()) == file.stamp)
        for file in entry.files:
            if not safe_filename(file.name) and file.name != ".verified.json":
                raise ValueError("Unrecognized model file name")
            if not unchanged(file):
                raise ValueError("Model files changed. Refresh and review removal again.")
            if file.sha256 and not verify_file(target / file.name, {"size": file.stamp[2], "sha256": file.sha256}):
                raise ValueError("A model checksum differs. Its files have been preserved.")
        # Invalidate the completion marker first; a partial removal cannot look installed.
        ordered = sorted(entry.files, key=lambda file: file.name != ".verified.json")
        removed, size, errors = 0, 0, []
        for file in ordered:
            try:
                if not unchanged(file):
                    raise ValueError("Model files changed during removal")
                (target / file.name).unlink()
                removed += 1
                size += file.stamp[2]
            except (OSError, ValueError) as error:
                errors.append(f"{file.name}: {error}")
                break
        try:
            target.rmdir()  # Only an empty directory; unknown files always survive.
        except OSError:
            pass
        return RemovalResult(removed, size, tuple(errors))
    finally:
        storage_lock.release()
