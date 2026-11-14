"""Explicit, licensed meeting speaker-model setup; inference never downloads."""

from saydraft.models.manifest import model_bundle

SEGMENTATION_MODEL = 'pyannote-segmentation-3-0'
EMBEDDING_MODEL = '3dspeaker-eres2net-base'


def speaker_bundle():
    return model_bundle(SEGMENTATION_MODEL)


def download_speaker_models(progress_callback=None, *, models_dir=None, pause_event=None):
    """Worker-only action after the user reviews both licenses and download size."""
    from saydraft.model_download import default_models_dir
    from saydraft.models.cleanup import transfer_bytes
    from saydraft.models.downloader import _check_pause, check_bundle_space, installation_ready
    from saydraft.models.installation import installation_target, install_files, transfer_directory
    from saydraft.models.storage_lock import storage_lock

    package = speaker_bundle()
    total = sum(transfer_bytes(model) for model in package)
    with storage_lock:
        _check_pause(pause_event)
        root = default_models_dir(models_dir)
        targets = [(model, installation_target(root, model)) for model in package]
        check_bundle_space([(model, transfer_directory(model, target)) for model, target in targets])
        completed = 0
        for model, target in targets:
            size = transfer_bytes(model)
            def progress(value):
                if progress_callback:
                    progress_callback(int((completed + size * value / 100) / total * 100))
            install_files(model, target, pause_event=pause_event, progress_callback=progress)
            _check_pause(pause_event)
            if not installation_ready(model, target, check_hashes=True):
                raise ValueError('Meeting speaker model did not pass verification')
            completed += size
        if progress_callback:
            progress_callback(100)
        return {model['id']: target for model, target in targets}
