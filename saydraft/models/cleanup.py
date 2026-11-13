"""Measured cleanup choices and explicit verified model/runtime installation."""

import threading

from .manifest import get_model, load_manifest
from .runtime_ids import runtime_model_id
from .storage_lock import storage_lock

_install_lock = threading.Lock()


def cleanup_bundle(model_id, backend):
    model = get_model(model_id)
    if model.get("role") != "llm":
        raise ValueError("Choose a catalogued AI cleanup model")
    return [model, get_model(runtime_model_id(backend))]


def transfer_bytes(model):
    return model["archive"]["size"] if "archive" in model else sum(
        file["size"] for file in model["files"] if "url" in file)


def recommend_cleanup(report, config=None):
    """A recommendation never enables cleanup or starts a download."""
    from .tiers import effective_tier
    tier = effective_tier(config or {}, report)
    model_id = load_manifest()["cleanup_defaults"].get(tier)
    return {"tier": tier, "model_id": model_id,
            "backend": "vulkan" if model_id and (report or {}).get("vulkan") else "cpu"}


def download_cleanup_model(model_id, backend, progress_callback=None, *, models_dir=None, pause_event=None):
    from saydraft.model_download import default_models_dir
    from .downloader import _check_pause, check_bundle_space, installation_ready
    from .installation import installation_target, install_files, transfer_directory
    from .packages import install_archive

    model, runtime = cleanup_bundle(model_id, backend)
    root = default_models_dir(models_dir)
    total = transfer_bytes(model) + transfer_bytes(runtime)
    def progress(completed, size, value):
        if progress_callback:
            progress_callback(int((completed + size * value / 100) / total * 100))
    with storage_lock, _install_lock:
        _check_pause(pause_event)
        target = installation_target(root, model)
        runtime_target = installation_target(root, runtime)
        check_bundle_space([(model, transfer_directory(model, target)),
                            (runtime, runtime_target)])
        install_files(model, target, pause_event=pause_event,
            progress_callback=lambda value: progress(0, transfer_bytes(model), value))
        install_archive(runtime, runtime_target, pause_event=pause_event,
            progress_callback=lambda value: progress(transfer_bytes(model), transfer_bytes(runtime), value))
        _check_pause(pause_event)
        if not (installation_ready(model, target, check_hashes=True)
                and installation_ready(runtime, runtime_target, check_hashes=True)):
            raise ValueError("Cleanup model and runtime must both be verified")
        if progress_callback:
            progress_callback(100)
        return target / next(file["path"] for file in model["files"] if file["path"].endswith(".gguf"))
