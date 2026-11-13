"""Explicit staged file installation and atomic directory publication."""

import uuid
from pathlib import Path

from .downloader import _check_pause, check_bundle_space, installation_ready, verify_file
from .layout import model_directories, model_relative_dir, require_local_paths, require_model_target
from .manifest import safe_filename
from .storage_lock import storage_lock


def installation_target(root, model):
    """Reuse a complete current pin in place; never migrate existing directories."""
    root = Path(root).absolute()
    require_local_paths(root)
    for directory in model_directories(root, model):
        require_local_paths(directory)
        if installation_ready(model, directory, check_hashes=True):
            return directory
    return root / model_relative_dir(model)


def staging_directory(target):
    target = Path(target)
    return target.with_name(target.name + ".download")


def transfer_directory(model, target):
    return target if installation_ready(model, target, check_hashes=True) else staging_directory(target)


def check_staging_files(model, directory):
    if not model.get("files"):
        raise ValueError("Model installation requires declared payload files")
    paths = [directory / ".verified.json", directory / ".verified.json.tmp", directory / "_archive"]
    for file in model["files"]:
        if not safe_filename(file["path"]):
            raise ValueError("Model payloads must have safe file names")
        path = directory / file["path"]
        controls = [path.with_name(path.name + suffix) for suffix in (".part", ".part.json", ".part.json.tmp")]
        paths.extend((path, *controls))
        require_local_paths(path, *controls)
        for control in controls:
            if control.is_file() and control.stat().st_nlink != 1:
                raise ValueError("Resumable model files cannot be hard linked")
        if path.is_file() and path.stat().st_nlink != 1 and not verify_file(path, file):
            raise ValueError("Changed hard-linked model files have been preserved")
    require_local_paths(directory, *paths)
    for control in paths[:2]:
        if control.is_file() and control.stat().st_nlink != 1:
            raise ValueError("Model receipts cannot be hard linked while installing")


def publish_directory(stage, target):
    """Only sibling directories move; rollback keeps the previous version on failure."""
    stage, target = Path(stage).absolute(), Path(target).absolute()
    archive_root = target.parent / "_archive"
    if stage == target or stage.parent != target.parent:
        raise ValueError("Model publication must stay inside its version folder")
    require_local_paths(stage, target, archive_root)
    if not stage.is_dir() or target.exists() and not target.is_dir():
        raise ValueError("Model publication requires directories; existing files were preserved")
    previous = None
    if target.exists():
        archive_root.mkdir(exist_ok=True)
        previous = archive_root / f"{target.name}-{uuid.uuid4().hex}"
        require_local_paths(previous)
        target.rename(previous)
    try:
        stage.rename(target)
    except OSError:
        if previous is not None and not target.exists():
            previous.rename(target)
        raise
    return target


def install_files(model, target, *, progress_callback=None, pause_event=None, opener=None,
                  file_progress_callback=None):
    """New payloads stay resumable in staging until every file and receipt verifies."""
    from .downloader import download_model
    with storage_lock:
        _check_pause(pause_event)
        target = require_model_target(model, target, allow_legacy=True)
        if installation_ready(model, target, check_hashes=True):
            if file_progress_callback is not None:
                from .progress import FileProgress
                for file in model["files"]:
                    file_progress_callback(FileProgress(model["id"], file["path"], file["size"], file["size"], "verified"))
            if progress_callback:
                progress_callback(100)
            return target
        # A legacy installation can be reused; new file downloads use ID/version.
        require_model_target(model, target)
        stage = staging_directory(target)
        check_staging_files(model, stage)
        check_bundle_space([(model, stage)])
        options = {"opener": opener} if opener is not None else {}
        if file_progress_callback is not None:
            options["file_progress_callback"] = file_progress_callback
        download_model(model, stage, pause_event=pause_event, **options,
            progress_callback=lambda value: progress_callback(min(99, value)) if progress_callback else None)
        _check_pause(pause_event)
        check_staging_files(model, stage)
        if not installation_ready(model, stage, check_hashes=True):
            raise ValueError("Model installation did not pass SHA-256 verification")
        publish_directory(stage, target)
        if progress_callback:
            progress_callback(100)
        return target
