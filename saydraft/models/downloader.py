"""Explicit model downloads: pinned URLs, scoped hosts and verification before use."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from saydraft.privacy.netguard import NetworkGuard

_lock = threading.Lock()


class DownloadPaused(Exception):
    """The explicit download stopped with resumable partial files preserved."""


def _check_pause(pause_event):
    if pause_event is not None and pause_event.is_set():
        raise DownloadPaused("Download paused. Choose Download to resume.")


def verify_file(path: Path, file: dict) -> bool:
    if not path.is_file() or path.stat().st_size != file["size"]:
        return False
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest() == file["sha256"]


def _archive(path: Path) -> None:
    archive = path.parent / "_archive"
    archive.mkdir(exist_ok=True)
    path.rename(archive / f"{path.name}-{uuid.uuid4().hex}")


class _PinnedRedirects(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = frozenset(hosts)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urlsplit(newurl)
        if (url.scheme != "https" or url.hostname not in self.hosts
                or url.port not in (None, 443) or url.username or url.password):
            raise ValueError("Model download redirected outside its pinned HTTPS hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def installation_ready(model: dict, target: Path, *, check_hashes=False) -> bool:
    """A completion marker belongs to this revision; optionally rehash before loading."""
    try:
        receipt = json.loads((target / ".verified.json").read_text(encoding="utf-8"))
        if receipt != _receipt(model):
            return False
        return all(verify_file(target / file["path"], file) if check_hashes else
                   (target / file["path"]).is_file() and
                   (target / file["path"]).stat().st_size == file["size"]
                   for file in model["files"])
    except (OSError, ValueError, TypeError):
        return False


def _receipt(model):
    return {"revision": model.get("revision"), "files": model["files"]}


def _write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


def _check_space(model, target):
    remaining = 0
    for file in model["files"]:
        destination = target / file["path"]
        if verify_file(destination, file):
            continue
        partial = destination.with_name(destination.name + ".part")
        metadata = destination.with_name(destination.name + ".part.json")
        try:
            known = json.loads(metadata.read_text(encoding="utf-8")) == file
            size = partial.stat().st_size if known else 0
            saved = size if 0 <= size <= file["size"] else 0
        except (OSError, ValueError):
            saved = 0
        remaining += file["size"] - saved
    _require_space(remaining, target)


def _require_space(remaining, target):
    free = shutil.disk_usage(target.resolve()).free
    required = remaining + 64 * 1024 * 1024 if remaining else 0
    if free < required:
        raise OSError(f"Not enough disk space: need {required / 1_000_000:.0f} MB, "
                      f"available {free / 1_000_000:.0f} MB. Partial files are kept; free space and resume.")


def _download_file(file, destination, open_url, progress, pause_event):
    partial = destination.with_name(destination.name + ".part")
    metadata = destination.with_name(destination.name + ".part.json")
    try:
        known = json.loads(metadata.read_text(encoding="utf-8")) == file
    except (OSError, ValueError):
        known = False
    if partial.exists() and (not known or partial.stat().st_size > file["size"]):
        _archive(partial)
    offset = partial.stat().st_size if partial.exists() else 0
    _write_json(metadata, file)
    if offset < file["size"]:
        headers = {"User-Agent": "Saydraft-model-downloader", "Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        with open_url(Request(file["url"], headers=headers), timeout=30) as response:
            status = getattr(response, "status", 200)
            if status == 206:
                value = response.headers.get("Content-Range", "")
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", value)
                if (not match or int(match[1]) != offset or int(match[3]) != file["size"]
                        or not offset <= int(match[2]) < file["size"]):
                    raise ValueError("Invalid model download resume response")
            elif status == 200:
                if offset:  # Servers may ignore Range. Retain the old attempt and start cleanly.
                    _require_space(file["size"], destination.parent)
                    _archive(partial)
                    offset = 0
            else:
                raise ValueError(f"Unexpected model download response: {status}")
            with partial.open("ab" if offset else "wb") as output:
                while True:
                    _check_pause(pause_event)
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    if offset + len(chunk) > file["size"]:
                        raise ValueError("Model download exceeded its pinned size")
                    output.write(chunk)
                    offset += len(chunk)
                    progress(offset)
    if offset < file["size"]:
        raise OSError("Model download interrupted; choose Download to resume")
    _check_pause(pause_event)
    if not verify_file(partial, file):
        _archive(partial)
        raise ValueError(f"SHA-256 or size mismatch for model file {file['path']}")
    partial.replace(destination)
    metadata.unlink(missing_ok=True)  # Our completed transfer's metadata, never owner data.


def download_model(model: dict, target: Path, *, progress_callback=None, opener=None,
                   pause_event=None) -> Path:
    """Explicit action only. Resume pinned files; publish only after complete SHA-256 checks."""
    total = sum(file["size"] for file in model["files"])
    completed = 0
    open_url = opener or build_opener(ProxyHandler({}), _PinnedRedirects(model["download_hosts"])).open
    NetworkGuard.install()
    with _lock, NetworkGuard.allow_downloads(model["download_hosts"]):
        _check_pause(pause_event)
        target.mkdir(parents=True, exist_ok=True)
        _check_space(model, target)
        marker = target / ".verified.json"
        if marker.exists() and not installation_ready(model, target, check_hashes=True):
            _archive(marker)
        for file in model["files"]:
            _check_pause(pause_event)
            destination = target / file["path"]
            if verify_file(destination, file):
                completed += file["size"]
                if progress_callback:
                    progress_callback(int(completed / total * 100))
                continue
            if destination.exists():
                _archive(destination)

            def progress(downloaded):
                if progress_callback:
                    progress_callback(int((completed + downloaded) / total * 100))

            _download_file(file, destination, open_url, progress, pause_event)
            completed += file["size"]
        _write_json(marker, _receipt(model))
    return target
