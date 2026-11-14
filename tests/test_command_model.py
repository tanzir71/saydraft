"""Admission uses saved evidence; setup is explicit and runtime is cache-only."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from saydraft.config import default_config, load_config
from saydraft.models.cleanup import cleanup_bundle
from saydraft.models.command import (CommandModelChoice, command_bundle, command_choice,
                                     download_command_model, installed_command_config)
from saydraft.models.manifest import bundled_license_path, get_model, load_manifest, supports_task


def test_command_pin_matches_measured_artifact_and_does_not_change_cleanup_defaults():
    manifest = load_manifest()
    model = get_model(manifest['command_model'])
    candidate = next(m for m in json.loads(Path('eval/cleanup/candidates.json').read_text())['models']
                     if m['id'] == model['id'])
    assert model['files'][:2] == candidate['files'] and model['revision'] == candidate['revision']
    assert model['tasks'] == ['command', 'translate'] and model['status'] == 'experimental_command'
    assert supports_task(model, 'command') and not supports_task(model, 'cleanup')
    assert manifest['cleanup_defaults'] == {'lite': None, 'standard': 'qwen35-08b-q4-k-m', 'pro': 'qwen35-2b-q4-k-m'}
    notice = model['files'][-1]
    raw = bundled_license_path(notice['bundled_source']).read_bytes()
    assert len(raw) == notice['size'] and hashlib.sha256(raw).hexdigest() == notice['sha256']
    with pytest.raises(ValueError, match='cleanup model'):
        cleanup_bundle(model['id'], 'cpu')


@pytest.mark.parametrize('tier,enabled,reason', [
    ('auto', False, 'disabled'), ('pro', False, 'disabled'), ('standard', True, 'needs_pro'),
    ('lite', True, 'needs_pro'), ('auto', True, 'needs_pro'), ('pro', True, 'ready')])
def test_default_off_and_pro_admission_never_resolves_installed_models(tier, enabled, reason):
    config = default_config()
    config['app']['tier'] = tier
    config['labs']['command_mode'] = enabled
    config['llm']['enabled'] = False  # Independent opt-ins.
    before = copy.deepcopy(config)
    choice = command_choice(config)
    assert choice.reason == reason and choice.backend == 'cpu' and config == before
    if reason != 'ready':
        assert installed_command_config(choice, resolver=lambda *a, **kw: pytest.fail('No model access')) is None


def test_measured_tier_and_explicit_backend_do_not_discover_devices_or_change_speech():
    config = default_config()
    config['labs']['command_mode'] = True
    report = {'assessment': {'tier': 'pro'}, 'vulkan': [{'name': 'saved public GPU fixture'}]}
    before = copy.deepcopy((config, report))
    assert command_choice(config, report).backend == 'vulkan'
    assert command_choice(config, report).reason == 'ready'
    config['command']['backend'] = 'cpu'
    assert command_choice(config, report).backend == 'cpu'
    config['command']['backend'] = 'auto'
    assert (config, report) == before


@pytest.mark.parametrize('missing', [None, 'model', 'runtime'])
def test_cache_only_resolution_verifies_both_pins_before_returning_a_native_config(tmp_path, missing):
    choice = CommandModelChoice(load_manifest()['command_model'], 'vulkan', 'ready')
    bundle = command_bundle('vulkan')
    calls = []
    def resolve(model_id, **kwargs):
        calls.append((model_id, kwargs))
        if model_id == bundle[0 if missing == 'model' else 1]['id'] and missing:
            return None
        return tmp_path / model_id
    cfg = installed_command_config(choice, resolver=resolve, threads=3)
    assert calls == [(m['id'], {'check_hashes': True}) for m in bundle]
    if missing:
        assert cfg is None
    else:
        assert cfg.model_path.name == bundle[0]['files'][0]['path']
        assert (cfg.backend, cfg.threads, cfg.context_size, cfg.startup_seconds) == ('vulkan', 3, 4096, 60)


def test_arbitrary_custom_cleanup_model_is_not_command_admission():
    choice = CommandModelChoice('custom-private-path', 'cpu', 'ready')
    assert installed_command_config(choice, resolver=lambda *a, **kw: pytest.fail('No resolution')) is None


def test_command_setup_only_forwards_an_explicit_request_and_captured_package(tmp_path, monkeypatch):
    calls, pause = [], object()
    def install(package, progress, **kwargs):
        calls.append((package, progress, kwargs))
        return tmp_path / 'verified.gguf'
    monkeypatch.setattr('saydraft.models.command.download_llm_bundle', install)
    assert not calls
    def progress(value):
        pass
    assert download_command_model('cpu', progress, models_dir=tmp_path, pause_event=pause) == tmp_path / 'verified.gguf'
    assert calls == [(command_bundle('cpu'), progress, {'models_dir': tmp_path, 'pause_event': pause})]


@pytest.mark.parametrize('mutation', [
    lambda m: m.update(command_model='qwen35-2b-q4-k-m'),
    lambda m: m.update(command_model={}),
    lambda m: m['cleanup_defaults'].update(pro=m['command_model']),
    lambda m: m['models'][-1].update(tasks=[]),
    lambda m: m['models'][-1].update(tasks=['command', 'command']),
    lambda m: m['models'][-1].update(tasks=['cloud']),
])
def test_invalid_task_defaults_are_rejected(tmp_path, mutation):
    data = copy.deepcopy(load_manifest())
    mutation(data)
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_manifest(path)


def test_command_settings_migrate_default_off_and_sanitize_backend(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'llm': {'enabled': True}, 'command': {'backend': 'remote'}}))
    cfg = load_config(config_path=path)
    assert cfg['llm']['enabled'] and cfg['labs']['command_mode'] is False and cfg['command']['backend'] == 'auto'
