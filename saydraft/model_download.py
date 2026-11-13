"""Whisper model download helpers for source and packaged runs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models.downloader import check_bundle_space, download_model, installation_ready
from .models.manifest import get_model, model_bundle
from .models.storage_lock import storage_lock

ProgressCallback = Callable[[int], None]


def default_models_dir(models_dir: str | Path | None = None) -> Path:
    if models_dir is not None:
        return Path(models_dir)
    from .compat.migrate import profile_root

    return profile_root() / "Saydraft" / "models"


def model_relative_dir(model: dict) -> Path:
    if model["engine"] == "whisper":
        return Path("whisper") / model["model_size"]
    folder = {"vad": "vad", "lid": "lid", "llm": "llm", "runtime": "runtime", "preview": "preview"}.get(model.get("role"), "asr")
    if model.get("role") == "llm":
        return Path(folder) / model["id"] / model["revision"]
    return Path(folder) / model["id"]


def find_installed_model(model_id: str, *, check_hashes=False) -> Path | None:
    """Read old portable installations in place; new downloads use the user profile."""
    import sys

    model = get_model(model_id)
    roots = [default_models_dir(), Path(__file__).resolve().parents[1] / "models"]
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent / "models")
    for root in dict.fromkeys(roots):
        directory = root / model_relative_dir(model)
        if installation_ready(model, directory, check_hashes=check_hashes):
            return directory
    return None


def download_asr_model(model_id: str, progress_callback=None, *, models_dir=None,
                       pause_event=None) -> Path:
    """Explicit Settings/setup download; legacy Whisper size aliases remain accepted."""
    if model_id in ("base", "small", "medium", "large-v3-turbo"):
        model_id = f"whisper-{model_id}"
    model = get_model(model_id)
    if model.get("role", "asr") != "asr":
        raise ValueError("Choose a speech recognition model")
    package = model_bundle(model_id)
    targets = [(item, default_models_dir(models_dir) / model_relative_dir(item)) for item in package]
    with storage_lock:
        check_bundle_space(targets)
        total = sum(file["size"] for item in package for file in item["files"])
        completed = 0
        for item, target in targets:
            size = sum(file["size"] for file in item["files"])

            def progress(value):
                if progress_callback:
                    progress_callback(int((completed + size * value / 100) / total * 100))

            download_model(item, target, progress_callback=progress, pause_event=pause_event)
            completed += size
    return targets[0][1]


def download_whisper_model(
    model_size: str,
    progress_callback: ProgressCallback | None = None,
    *,
    models_dir: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> Path:
    model = get_model(f"whisper-{model_size}")
    target = default_models_dir(models_dir) / "whisper" / str(model_size)
    _emit_progress(progress_callback, 5)
    download_model(model, target, progress_callback=progress_callback)
    _emit_progress(progress_callback, 100)
    return target


def _emit_progress(callback: ProgressCallback | None, value: int) -> None:
    if callback is not None:
        callback(int(value))


def download_silero_vad_model(progress_callback: ProgressCallback | None = None, *, models_dir=None,
                              pause_event=None) -> Path:
    """Explicit Settings action; inference never calls this function."""
    model = get_model("silero-vad-v5")
    target = default_models_dir(models_dir) / "vad" / model["id"]
    return download_model(model, target, progress_callback=progress_callback, pause_event=pause_event)


def download_preview_model(progress_callback=None, *, models_dir=None, pause_event=None):
    """Explicit Labs download only; capture/recognition never installs preview weights."""
    from .asr.model_ids import PREVIEW_MODEL
    from .models.packages import install_archive

    model = get_model(PREVIEW_MODEL)
    target = default_models_dir(models_dir) / model_relative_dir(model)
    return install_archive(model, target, progress_callback=progress_callback, pause_event=pause_event)


def download_cleanup_runtime(backend, progress_callback=None, *, models_dir=None, pause_event=None):
    """Explicit AI cleanup setup action; service construction never downloads."""
    from .models.runtime_ids import runtime_model_id
    from .models.packages import install_archive

    model = get_model(runtime_model_id(backend))
    target = default_models_dir(models_dir) / model_relative_dir(model)
    return install_archive(model, target, progress_callback=progress_callback, pause_event=pause_event)
