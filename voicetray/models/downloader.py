"""Explicit model downloads: pinned URLs, scoped hosts and verification before use."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from voicetray.privacy.netguard import NetworkGuard

_lock = threading.Lock()


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


def download_model(model: dict, target: Path, *, progress_callback=None, opener=None) -> Path:
    """Call only in response to an explicit download action. Never load a model."""
    total = sum(file["size"] for file in model["files"])
    completed = 0
    open_url = opener or build_opener(ProxyHandler({}), _PinnedRedirects(model["download_hosts"])).open
    NetworkGuard.install()
    with _lock, NetworkGuard.allow_downloads(model["download_hosts"]):
        target.mkdir(parents=True, exist_ok=True)
        marker = target / ".verified.json"
        if marker.exists() and not all(verify_file(target / file["path"], file) for file in model["files"]):
            _archive(marker)
        for file in model["files"]:
            destination = target / file["path"]
            if verify_file(destination, file):
                completed += file["size"]
                if progress_callback:
                    progress_callback(int(completed / total * 100))
                continue
            if destination.exists():
                _archive(destination)
            partial = destination.with_name(destination.name + ".part")
            if partial.exists():
                _archive(partial)  # Preserve interrupted attempts; resumable transfers follow in P3.1.
            with open_url(Request(file["url"], headers={"User-Agent": "Saydraft-model-downloader"}),
                          timeout=30) as response, partial.open("xb") as output:
                downloaded = 0
                while chunk := response.read(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > file["size"]:
                        raise ValueError("Model download exceeded its pinned size")
                    output.write(chunk)
                    if progress_callback:
                        progress_callback(int((completed + downloaded) / total * 100))
            if not verify_file(partial, file):
                _archive(partial)
                raise ValueError(f"SHA-256 or size mismatch for model file {file['path']}")
            partial.rename(destination)
            completed += file["size"]
        if not marker.exists():
            marker.write_text(json.dumps({"revision": model.get("revision"),
                                          "files": model["files"]}), encoding="utf-8")
    return target
