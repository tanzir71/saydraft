from dataclasses import replace
import threading

import pytest

from saydraft.asr.router import ALL_LANGUAGES
from saydraft.config import default_config
from saydraft.meetings.setup import (MeetingSetupInspection, MeetingSetupPlan, download_meeting_setup,
    inspect_meeting_setup, meeting_setup_plan)
from saydraft.models.manifest import get_model, model_version


def pro_config():
    config = default_config()
    config['app']['tier'] = 'pro'
    config['command']['backend'] = 'cpu'
    return config


def test_plan_reviews_dependencies_licenses_sizes_and_auto_multilingual_without_enabling_labs():
    config = pro_config()
    plan = meeting_setup_plan(config)
    assert not config['labs']['notetaker'] and plan.reason == 'ready'
    assert ALL_LANGUAGES in plan.model_ids and len(plan.model_ids) == len(set(plan.model_ids))
    assert plan.download_bytes > 1e9 and plan.space_bytes > plan.download_bytes
    assert 'silero-vad-v5' in plan.model_ids
    assert all(model['license'] and model['license_url'] and model['source'] for model in plan.models())
    config['stt']['pinned_languages'] = ['en']
    assert ALL_LANGUAGES not in meeting_setup_plan(config).model_ids
    config['stt']['pinned_languages'] = ['bn', 'ar']
    assert ALL_LANGUAGES in meeting_setup_plan(config).model_ids
    config['app']['tier'] = 'standard'
    assert meeting_setup_plan(config).reason == 'needs_pro'


def test_inspection_hash_checks_every_dependency_and_missing_one_blocks_start():
    calls = []
    def resolve(name, **options):
        calls.append((name, options))
        return None if name == ALL_LANGUAGES else 'fixture-directory'
    result = inspect_meeting_setup(pro_config(), resolver=resolve)
    assert not result.ready and tuple(name for name, options in calls) == result.plan.model_ids
    assert all(options == {'check_hashes': True} for name, options in calls)
    assert inspect_meeting_setup(pro_config(), resolver=lambda *args, **options: 'verified').ready


def small_plan():
    ids = ('silero-vad-v5', 'llama-cpp-b12110-cpu-x64')
    return MeetingSetupPlan(ids, tuple(model_version(get_model(name)) for name in ids), 'cpu', 'ready')


def test_explicit_download_uses_reviewed_versions_space_pause_and_both_installers(tmp_path, monkeypatch):
    from saydraft.models import downloader, installation, packages
    calls, progress = [], []
    plan = small_plan()
    monkeypatch.setattr(installation, 'installation_target', lambda root, model: root / model['id'])
    monkeypatch.setattr(installation, 'transfer_directory', lambda model, path: path)
    monkeypatch.setattr(downloader, 'check_bundle_space', lambda targets: calls.append(('space', targets)))
    monkeypatch.setattr(downloader, 'installation_ready', lambda model, path, **options:
        calls.append(('verify', model['id'], options)) or True)
    def install(kind):
        def run(model, path, **options):
            calls.append((kind, model['id'], path, options['pause_event']))
            options['progress_callback'](0)
            options['progress_callback'](100)
        return run
    monkeypatch.setattr(installation, 'install_files', install('files'))
    monkeypatch.setattr(packages, 'install_archive', install('archive'))
    pause = threading.Event()
    result = download_meeting_setup(plan, progress.append, models_dir=tmp_path, pause_event=pause)
    assert list(result) == list(plan.model_ids) and calls[0][0] == 'space'
    assert [call[0] for call in calls] == ['space', 'files', 'verify', 'archive', 'verify']
    assert all(call[2] == {'check_hashes': True} for call in calls if call[0] == 'verify')
    assert progress == sorted(progress) and progress[-1] == 100 and all(value < 100 for value in progress[:-1])
    pause.set()
    from saydraft.models.downloader import DownloadPaused
    with pytest.raises(DownloadPaused):
        download_meeting_setup(plan, models_dir=tmp_path, pause_event=pause)
    assert len(calls) == 5


def test_changed_or_unapproved_plan_cannot_start_a_transfer(tmp_path):
    plan = small_plan()
    with pytest.raises(ValueError, match='changed'):
        download_meeting_setup(replace(plan, versions=('changed', *plan.versions[1:])), models_dir=tmp_path)
    with pytest.raises(ValueError, match='reviewed Pro'):
        download_meeting_setup(replace(plan, reason='needs_pro'), models_dir=tmp_path)
    with pytest.raises(ValueError):
        MeetingSetupPlan((), (), 'cpu', 'ready')
    with pytest.raises(ValueError):
        MeetingSetupInspection(plan, (True,))
    with pytest.raises(ValueError):
        MeetingSetupInspection(plan, (True, 1))
