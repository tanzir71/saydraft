"""Measured cleanup choices and explicit verified model/runtime installation."""

import threading

from .manifest import get_model, load_manifest
from .runtime_ids import runtime_model_id

_install_lock = threading.Lock()


def cleanup_bundle(model_id, backend):
    model = get_model(model_id)
    if model.get("role") != "llm":
        raise ValueError("Choose a catalogued AI cleanup model")
    return [model, get_model(runtime_model_id(backend))]


def transfer_bytes(model):
    return model["archive"]["size"] if "archive" in model else sum(
        file["size"] for file in model["files"] if "url" in file)


def recommend_cleanup(report):
    """A recommendation never enables cleanup or starts a download."""
    tier = (report or {}).get("assessment", {}).get("tier", "pending")
    model_id = load_manifest()["cleanup_defaults"].get(tier)
    return {"tier": tier, "model_id": model_id,
            "backend": "vulkan" if model_id and report.get("vulkan") else "cpu"}


def download_cleanup_model(model_id, backend, progress_callback=None, *, models_dir=None, pause_event=None):
    from saydraft.model_download import default_models_dir, model_relative_dir
    from .downloader import _archive, _check_pause, check_bundle_space, download_model, installation_ready
    from .packages import install_archive

    model, runtime = cleanup_bundle(model_id, backend)
    root = default_models_dir(models_dir).resolve()
    target = root / model_relative_dir(model)
    stage = target.with_name(target.name + ".download")
    runtime_target = root / model_relative_dir(runtime)
    def check_destinations():
        if any(not path.resolve().is_relative_to(root) for path in
               (target, stage, runtime_target, target.parent / "_archive")):
            raise ValueError("Cleanup installation leaves the model storage folder")
    check_destinations()
    total = transfer_bytes(model) + transfer_bytes(runtime)
    def progress(completed, size, value):
        if progress_callback:
            progress_callback(int((completed + size * value / 100) / total * 100))
    with _install_lock:
        _check_pause(pause_event)
        check_bundle_space([(model, stage if not installation_ready(model, target, check_hashes=True) else target),
                            (runtime, runtime_target)])
        if not installation_ready(model, target, check_hashes=True):
            download_model(model, stage, pause_event=pause_event,
                progress_callback=lambda value: progress(0, transfer_bytes(model), value))
            _check_pause(pause_event)
            if not installation_ready(model, stage, check_hashes=True):
                raise ValueError("Cleanup model installation did not pass verification")
            check_destinations()
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                _archive(target)  # Retain changed files; never delete an older version.
            stage.rename(target)
        install_archive(runtime, runtime_target, pause_event=pause_event,
            progress_callback=lambda value: progress(transfer_bytes(model), transfer_bytes(runtime), value))
        _check_pause(pause_event)
        if not (installation_ready(model, target, check_hashes=True)
                and installation_ready(runtime, runtime_target, check_hashes=True)):
            raise ValueError("Cleanup model and runtime must both be verified")
        if progress_callback:
            progress_callback(100)
        return target / next(file["path"] for file in model["files"] if file["path"].endswith(".gguf"))
