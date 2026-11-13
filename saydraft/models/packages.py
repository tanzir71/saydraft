"""Explicit pinned archive installation; publish only complete verified directories."""

from __future__ import annotations

import hashlib
import os
import stat
import tarfile
import threading
import uuid
import zipfile
from pathlib import Path

from .downloader import (
    _check_pause, _receipt, _remaining_bytes, _require_space, _write_json,
    download_model, installation_ready, verify_file,
)
from .manifest import validate_archive_model
from .storage_lock import storage_lock
from .installation import check_staging_files, publish_directory
from .layout import archive_cache_directory, require_local_paths, require_model_target

_install_lock = threading.Lock()


def _bundle_source(file, root):
    source = (root / file["bundled_source"]).resolve()
    if not source.is_relative_to((root / "assets" / "licenses").resolve()) or not verify_file(source, file):
        raise ValueError("Bundled model notice is missing or differs from its pinned checksum")
    return source


def _copy_verified(source, destination, file, pause, progress):
    digest, size = hashlib.sha256(), 0
    with destination.open("xb") as output:
        while True:
            _check_pause(pause)
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > file["size"]:
                raise ValueError("Archive payload exceeds its pinned size")
            digest.update(chunk)
            output.write(chunk)
            progress(len(chunk))
        output.flush()
        os.fsync(output.fileno())
    if size != file["size"] or digest.hexdigest() != file["sha256"]:
        raise ValueError("Archive payload SHA-256 or size mismatch")


def _extract(model, archive, stage, pause, progress):
    wanted = {file["member"]: file for file in model["files"] if "member" in file}
    seen = set()

    def consume(name, size, regular, open_member):
        file = wanted.get(name)
        if file is None:
            return  # No unlisted path or link is ever written.
        if name in seen or not regular or size != file["size"]:
            raise ValueError("Duplicate, linked or incorrectly sized archive payload")
        seen.add(name)
        with open_member() as source:
            _copy_verified(source, stage / file["path"], file, pause, progress)

    if model["archive"]["format"] == "tar.bz2":
        with tarfile.open(archive, mode="r|bz2") as package:
            for member in package:
                _check_pause(pause)
                consume(member.name, member.size, member.isfile(), lambda: package.extractfile(member))
    else:
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                _check_pause(pause)
                kind = stat.S_IFMT(member.external_attr >> 16)
                regular = not member.is_dir() and kind in (0, stat.S_IFREG) and not member.flag_bits & 1
                consume(member.filename, member.file_size, regular, lambda: package.open(member))
    if seen != set(wanted):
        raise ValueError("Archive is missing a declared payload")


def install_archive(model, target, *, cache_dir=None, bundled_root=None,
                    progress_callback=None, pause_event=None, opener=None):
    """User action only. Network resumes; interrupted staging and old versions are retained."""
    validate_archive_model(model)
    target = require_model_target(model, target, allow_legacy=True)
    parent = target.parent.resolve()
    target = parent / target.name
    if target.exists() and not target.is_dir():
        raise ValueError("Model destination contains a file; it has been preserved")
    root = Path(bundled_root) if bundled_root is not None else Path(__file__).resolve().parents[2]
    archive = model["archive"]
    archive_file = {key: archive[key] for key in ("path", "url", "size", "sha256")}
    archive_file["accept"] = "application/octet-stream"
    cache_model = {"revision": model["revision"], "download_hosts": model["download_hosts"], "files": [archive_file]}
    cache = Path(cache_dir) if cache_dir is not None else archive_cache_directory(model, target)
    require_local_paths(cache)
    with storage_lock, _install_lock:
        _check_pause(pause_event)
        if installation_ready(model, target, check_hashes=True):
            if progress_callback:
                progress_callback(100)
            return target
        notices = [(file, _bundle_source(file, root)) for file in model["files"] if "bundled_source" in file]
        check_staging_files(cache_model, cache)
        parent.mkdir(parents=True, exist_ok=True)
        cache.mkdir(parents=True, exist_ok=True)
        # A new staging directory needs the full payload even when an older
        # version or interrupted attempt remains on disk.
        unpacked = sum(file["size"] for file in model["files"])
        compressed = _remaining_bytes(cache_model, cache)
        if parent.anchor.casefold() == cache.resolve().anchor.casefold():
            _require_space(unpacked + compressed, parent)
        else:
            _require_space(unpacked, parent)
            _require_space(compressed, cache)
        download_model(cache_model, cache, opener=opener, pause_event=pause_event,
                       progress_callback=lambda value: progress_callback(value * 70 // 100) if progress_callback else None)
        _check_pause(pause_event)
        stage = parent / f".{uuid.uuid4().hex}.installing"
        stage.mkdir()
        completed = 0

        def progress(size):
            nonlocal completed
            completed += size
            if progress_callback:
                progress_callback(min(99, 70 + completed * 30 // unpacked))

        for file, source in notices:
            with source.open("rb") as handle:
                _copy_verified(handle, stage / file["path"], file, pause_event, progress)
        _extract(model, cache / archive["path"], stage, pause_event, progress)
        _check_pause(pause_event)
        _write_json(stage / ".verified.json", _receipt(model))
        publish_directory(stage, target)
        if progress_callback:
            progress_callback(100)
        return target
