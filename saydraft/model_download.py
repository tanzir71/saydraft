"""Whisper model download helpers for source and packaged runs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models.downloader import download_model, installation_ready
from .models.manifest import get_model

ProgressCallback = Callable[[int], None]


def default_models_dir(models_dir: str | Path | None = None) -> Path:
    if models_dir is not None:
        return Path(models_dir)
    from .compat.migrate import profile_root

    return profile_root() / "Saydraft" / "models"


def model_relative_dir(model: dict) -> Path:
    if model["engine"] == "whisper":
        return Path("whisper") / model["model_size"]
    return Path("vad" if model.get("role") == "vad" else "asr") / model["id"]


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
    target = default_models_dir(models_dir) / model_relative_dir(model)
    return download_model(model, target, progress_callback=progress_callback, pause_event=pause_event)


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
