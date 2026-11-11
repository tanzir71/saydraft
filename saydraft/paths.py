"""Editable support files live beside the user's configuration."""

from __future__ import annotations

import shutil
from pathlib import Path

from .compat.migrate import LEGACY_NAME, profile_root


def resolve_data_path(value: str | Path) -> Path:
    path = Path(value)
    base = profile_root() / "Saydraft"
    if path.is_absolute():
        try:
            relative = path.relative_to(profile_root() / LEGACY_NAME)
        except ValueError:
            return path
        copied = base / relative
        return copied if copied.exists() else path
    destination = (base / path).resolve()
    if not destination.is_relative_to(base.resolve()):
        raise ValueError("Relative data paths must stay inside the profile")
    if not destination.exists():
        bundled = Path(__file__).resolve().parents[1] / path
        if bundled.is_file() and path.parts[0] != "models":
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled, destination)
    return destination
