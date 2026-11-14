"""Command admission and explicit model setup; never invoked by language routing."""

from dataclasses import dataclass

from .cleanup import download_llm_bundle
from .manifest import get_model, load_manifest
from .runtime_ids import runtime_model_id
from .tiers import effective_tier


@dataclass(frozen=True)
class CommandModelChoice:
    model_id: str
    backend: str
    reason: str


def command_choice(config, report=None):
    """Decision from config/report/catalog only; no installed-file or device scan."""
    return _choice(config, report, 'command_mode')


def translation_choice(config, report=None):
    return _choice(config, report, 'translate_mode')


def _choice(config, report, flag):
    model_id = load_manifest()["command_model"]
    selected = config.get("command", {}).get("backend", "auto")
    backend = selected if selected in ("cpu", "vulkan") else "vulkan" if (report or {}).get("vulkan") else "cpu"
    reason = ("disabled" if config.get("labs", {}).get(flag) is not True else
              "needs_pro" if effective_tier(config, report) != "pro" else "ready")
    return CommandModelChoice(model_id, backend, reason)


def command_bundle(backend):
    return [get_model(load_manifest()["command_model"]), get_model(runtime_model_id(backend))]


def download_command_model(backend, progress_callback=None, *, models_dir=None, pause_event=None):
    """Explicit licensed setup only. Enabling Labs never calls this function."""
    return download_llm_bundle(command_bundle(backend), progress_callback,
                               models_dir=models_dir, pause_event=pause_event)


def installed_command_config(choice, *, resolver=None, threads=4):
    """Worker-only full cache verification, before starting an instruction capture."""
    from saydraft.model_download import find_installed_model
    from saydraft.cleanup.llm.sidecar import SidecarConfig

    if (not isinstance(choice, CommandModelChoice) or choice.reason != "ready"
            or choice.model_id != load_manifest()["command_model"]):
        return None
    model, runtime = command_bundle(choice.backend)
    resolve = resolver or find_installed_model
    directory = resolve(model["id"], check_hashes=True)
    runtime_directory = resolve(runtime["id"], check_hashes=True)
    if directory is None or runtime_directory is None:
        return None
    weight = next(file["path"] for file in model["files"] if file["path"].endswith(".gguf"))
    return SidecarConfig((directory / weight).resolve(), backend=choice.backend, threads=threads,
                         context_size=4096, startup_seconds=60, max_restarts=0)
