"""Copy the former profile without overwriting an existing Saydraft profile."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)
LEGACY_NAME = "VoiceTray"
LEGACY_MODULE = "voicetray"
MARKER_NAME = "MIGRATED_FROM_VOICETRAY.txt"
_DATA_NAMES = {"config.json", "history.db", "history.db-wal", "history.db-shm",
               "glossary.json", "snippets.txt", "app_profiles.json", "logs", "models"}


def profile_root(local_appdata: str | Path | None = None) -> Path:
    return Path(local_appdata or os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")


def legacy_instance_running(local_appdata: str | Path | None = None) -> bool:
    from saydraft.single_instance import _pid_is_running

    path = profile_root(local_appdata) / LEGACY_NAME / f"{LEGACY_MODULE}.lock"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pid = data.get("pid")
        return isinstance(pid, int) and _pid_is_running(pid)
    except (OSError, ValueError, AttributeError):
        return False


def migrate_profile(local_appdata: str | Path | None = None) -> bool:
    """Resume copies after interruption; source files are always opened read-only.

    A pre-existing destination without our intent marker is an independent profile
    and is never filled with old data. Existing destination files are never replaced.
    """
    base = profile_root(local_appdata)
    source = base / LEGACY_NAME
    target = base / "Saydraft"
    intent = base / "Saydraft.migration.json"
    marker = target / MARKER_NAME
    if not source.is_dir() or marker.exists():
        return False
    if target.exists() and any(target.iterdir()) and not intent.exists():
        return False
    if legacy_instance_running(local_appdata):
        raise RuntimeError("Close VoiceTray to avoid double hotkeys before migration")
    if not intent.exists():
        with intent.open("x", encoding="utf-8") as handle:
            json.dump({"source": str(source), "target": str(target)}, handle)
    elif json.loads(intent.read_text(encoding="utf-8")) != {"source": str(source), "target": str(target)}:
        raise ValueError("Migration intent does not match these profile directories")
    target.mkdir(parents=True, exist_ok=True)
    for name in sorted(_DATA_NAMES):
        entry = source / name
        if not entry.exists() or entry.is_symlink():
            continue
        files = sorted(entry.rglob("*")) if entry.is_dir() else [entry]
        for original in files:
            if not original.is_file() or original.is_symlink():
                continue
            relative = original.relative_to(source)
            if any((source.joinpath(*relative.parts[:index])).is_symlink()
                   for index in range(1, len(relative.parts))):
                continue
            destination = target / relative
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial = destination.with_name(destination.name + ".migration-" + uuid.uuid4().hex)
            shutil.copy2(original, partial)
            if destination.exists():
                archive = target / "_archive/migration"
                archive.mkdir(parents=True, exist_ok=True)
                partial.rename(archive / partial.name)
            else:
                partial.rename(destination)
    with marker.open("x", encoding="utf-8") as handle:
        handle.write("Copied from the VoiceTray profile. Original files were left untouched.\n")
    logger.info("Copied the legacy profile into Saydraft; original data preserved")
    return True


def migrate_autostart(manager) -> bool:
    """Replace only an exact app-managed old launch command, never arbitrary values."""
    if manager.platform != "win32":
        return False
    from saydraft.autostart import RUN_KEY, APP_RUN_VALUE

    registry = manager._registry()
    key = registry.CreateKey(registry.HKEY_CURRENT_USER, RUN_KEY)
    try:
        try:
            old_command, _kind = registry.QueryValueEx(key, LEGACY_NAME)
        except (OSError, KeyError):
            return False
        executable = Path(sys.executable)
        known = {f'"{executable.with_name("pythonw.exe")}" -m {LEGACY_MODULE}',
                 f'"{executable}" -m {LEGACY_MODULE}'}
        if getattr(sys, "frozen", False):
            known.add(f'"{executable.with_name(LEGACY_NAME + ".exe")}"')
        if not isinstance(old_command, str) or old_command.casefold() not in {v.casefold() for v in known}:
            logger.info("Preserved unrecognized legacy autostart command")
            return False
        try:
            registry.QueryValueEx(key, APP_RUN_VALUE)
        except (OSError, KeyError):
            registry.SetValueEx(key, APP_RUN_VALUE, 0, registry.REG_SZ, manager.command)
        registry.DeleteValue(key, LEGACY_NAME)
        logger.info("Migrated the app-managed legacy autostart value")
        return True
    finally:
        registry.CloseKey(key)
