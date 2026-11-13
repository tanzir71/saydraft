"""Pinned-version write paths and read-only compatibility with earlier layouts."""

import re
from pathlib import Path

from .manifest import model_version, safe_filename


def model_relative_dir(model):
    identifier = model.get("id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9-]+", identifier):
        raise ValueError("Model IDs must be safe directory names")
    return Path(identifier) / model_version(model)


def legacy_model_relative_dir(model):
    if model.get("engine") == "whisper":
        if not safe_filename(model.get("model_size")):
            raise ValueError("Legacy Whisper sizes must be safe directory names")
        return Path("whisper") / model["model_size"]
    role = model.get("role", "asr")
    folder = role if role in ("vad", "lid", "llm", "runtime", "preview") else "asr"
    path = Path(folder) / model["id"]
    return path / model["revision"] if role == "llm" else path


def model_directories(root, model):
    return tuple(dict.fromkeys(Path(root) / path for path in
                               (model_relative_dir(model), legacy_model_relative_dir(model))))


def archive_cache_directory(model, target):
    target = Path(target)
    version = model_version(model)
    return target.parent / "_packages" / (version if target.name == version else model["id"])


def require_local_paths(*paths):
    """Check lexical destinations before resolving or moving any directory."""
    for supplied in paths:
        path = Path(supplied).absolute()
        if str(path).startswith("\\\\"):
            raise ValueError("Model installation requires local storage")
        for item in (path, *path.parents):
            if item.is_symlink() or item.is_junction():
                raise ValueError("Model installation cannot use linked paths")


def require_model_target(model, target, *, allow_legacy=False):
    target = Path(target).absolute()
    canonical = model_relative_dir(model)
    tails = [canonical]
    if allow_legacy:
        tails.extend((legacy_model_relative_dir(model), Path(model["id"])))
    if not any(Path(*target.parts[-len(tail.parts):]) == tail for tail in tails):
        raise ValueError("Model destination must name its catalog ID and pinned version")
    require_local_paths(target)
    if target.exists() and not target.is_dir():
        raise ValueError("Model destination contains a file; it has been preserved")
    return target
