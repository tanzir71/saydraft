"""Whisper model download helpers for source and packaged runs."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models.downloader import download_model
from .models.manifest import get_model

ProgressCallback = Callable[[int], None]


def default_models_dir(models_dir: str | Path | None = None) -> Path:
    if models_dir is not None:
        return Path(models_dir)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "models"
    return Path(__file__).resolve().parents[1] / "models"


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


def download_silero_vad_model(progress_callback: ProgressCallback | None = None, *, models_dir=None) -> Path:
    """Explicit Settings action; inference never calls this function."""
    model = get_model("silero-vad-v5")
    target = default_models_dir(models_dir) / "vad" / model["id"]
    return download_model(model, target, progress_callback=progress_callback)
