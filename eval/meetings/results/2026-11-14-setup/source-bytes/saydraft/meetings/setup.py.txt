"""Pure licensed meeting package plan and explicit verified setup action."""

from dataclasses import dataclass

from saydraft.models.cleanup import transfer_bytes
from saydraft.models.command import command_bundle, meeting_choice
from saydraft.models.manifest import get_model, model_bundle, model_version
from saydraft.models.tiers import effective_tier
from .asr import speech_models
from .models import speaker_bundle


@dataclass(frozen=True)
class MeetingSetupPlan:
    model_ids: tuple[str, ...]
    versions: tuple[str, ...]
    backend: str
    reason: str

    def __post_init__(self):
        if (type(self.model_ids) is not tuple or not self.model_ids
                or any(type(item) is not str or not item for item in self.model_ids)
                or len(set(self.model_ids)) != len(self.model_ids)
                or type(self.versions) is not tuple or len(self.versions) != len(self.model_ids)
                or any(type(item) is not str or not item for item in self.versions)
                or self.backend not in ('cpu', 'vulkan') or self.reason not in ('ready', 'needs_pro')):
            raise ValueError('Invalid meeting model plan')

    def models(self):
        result = tuple(get_model(name) for name in self.model_ids)
        if tuple(model_version(model) for model in result) != self.versions:
            raise ValueError('Meeting models changed; review setup again')
        return result

    @property
    def download_bytes(self):
        return sum(transfer_bytes(model) for model in self.models())

    @property
    def space_bytes(self):
        return sum(transfer_bytes(model) + sum(item['size'] for item in model['files']) + 64 * 1024**2
                   for model in self.models())


@dataclass(frozen=True)
class MeetingSetupInspection:
    plan: MeetingSetupPlan
    installed: tuple[bool, ...]

    def __post_init__(self):
        if (type(self.plan) is not MeetingSetupPlan or type(self.installed) is not tuple
                or len(self.installed) != len(self.plan.model_ids) or any(type(value) is not bool for value in self.installed)):
            raise ValueError('Invalid meeting model inspection')

    @property
    def ready(self):
        return self.plan.reason == 'ready' and bool(self.installed) and all(self.installed)


def meeting_setup_plan(config, report=None):
    choice = meeting_choice(config, report)
    models = {}
    for identifier in (*speech_models(config), 'silero-vad-v5'):
        for model in model_bundle(identifier):
            models.setdefault(model['id'], model)
    for model in (*speaker_bundle(), *command_bundle(choice.backend)):
        models.setdefault(model['id'], model)
    return MeetingSetupPlan(tuple(models), tuple(model_version(model) for model in models.values()),
        choice.backend, 'ready' if effective_tier(config, report) == 'pro' else 'needs_pro')


def inspect_meeting_setup(config, *, report=None, resolver=None):
    if resolver is None:
        from saydraft.model_download import find_installed_model
        resolver = find_installed_model
    plan = meeting_setup_plan(config, report)
    installed = tuple(resolver(name, check_hashes=True) is not None for name in plan.model_ids)
    return MeetingSetupInspection(plan, installed)


def download_meeting_setup(plan, progress_callback=None, *, models_dir=None, pause_event=None):
    """Only the reviewed plan is transferred; enabling Labs never calls this."""
    from saydraft.model_download import default_models_dir
    from saydraft.models.downloader import _check_pause, check_bundle_space, installation_ready
    from saydraft.models.installation import installation_target, install_files, transfer_directory
    from saydraft.models.packages import install_archive
    from saydraft.models.storage_lock import storage_lock

    if type(plan) is not MeetingSetupPlan or plan.reason != 'ready':
        raise ValueError('Meeting setup requires a reviewed Pro model plan')
    package = plan.models()
    root, completed, total = default_models_dir(models_dir), 0, plan.download_bytes
    with storage_lock:
        _check_pause(pause_event)
        targets = [(model, installation_target(root, model)) for model in package]
        check_bundle_space([(model, transfer_directory(model, target)) for model, target in targets])
        for model, target in targets:
            _check_pause(pause_event)
            size = transfer_bytes(model)
            def progress(value):
                if progress_callback:
                    progress_callback(min(99, int((completed + size * value / 100) * 100 / total)))
            install = install_archive if 'archive' in model else install_files
            install(model, target, pause_event=pause_event, progress_callback=progress)
            if not installation_ready(model, target, check_hashes=True):
                raise ValueError('Meeting setup did not verify; choose Resume to retry')
            completed += size
        _check_pause(pause_event)
        if progress_callback:
            progress_callback(100)
    return {model['id']: target for model, target in targets}
