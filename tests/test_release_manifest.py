import copy
import hashlib
import json

import pytest

from tools.release_manifest import main, release_notes, validate_release

COMMIT = 'a' * 40


def release_fixture(tmp_path):
    audit, artifacts = tmp_path / 'audit', tmp_path / 'artifacts'
    audit.mkdir()
    artifacts.mkdir()
    notices = {'components': 2, 'files': 3, 'index_sha256': 'b' * 64}
    bundle = {'git_commit': COMMIT, 'packaging_gate': True, 'source_dirty': False,
              'third_party_notices': notices, 'artifacts': {}}
    for name in ['Saydraft-0.1.0-Setup.exe', 'Saydraft-0.1.0-win-x64.zip']:
        payload = ('owned artifact fixture: ' + name).encode()
        (artifacts / name).write_bytes(payload)
        bundle['artifacts'][name] = {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
    (artifacts / 'SHA256SUMS').write_text(''.join(f'{value["sha256"]}  {name}\n'
        for name, value in sorted(bundle['artifacts'].items())), encoding='utf-8')
    runtime = {'version': '0.1.0', 'complete': True, 'frozen': True, 'third_party_notices': notices,
               'checks': dict.fromkeys(['resources', 'third_party_notices', 'native_imports', 'tray_images',
                                       'python_network_guard', 'forbidden_modules_absent'], True)}
    smoke = dict.fromkeys(['complete', 'default_keeps_data', 'explicit_removes_data',
                          'autostart_default_off', 'autostart_opt_in', 'startup_removed',
                          'junction_target_preserved'], True)
    reports = {'bundle.json': bundle, 'runtime.json': runtime,
               'installed-runtime.json': copy.deepcopy(runtime), 'installer-smoke.json': smoke}
    for name, data in reports.items():
        (audit / name).write_text(json.dumps(data), encoding='utf-8')
    return reports


@pytest.mark.parametrize('tag', ['v0.1.0', 'v0.1.0-dry-run.20261114', 'v0.1.0-rc.1'])
def test_verified_version_tag_can_only_produce_an_unsigned_draft(tmp_path, tag):
    release_fixture(tmp_path)
    result = validate_release(tmp_path, tag, COMMIT)
    assert result['draft'] is True and result['signed'] is False
    assert result['tag'] == tag
    assert 'unsigned verification draft' in release_notes(result)
    assert 'optional All languages model' in release_notes(result)


@pytest.mark.parametrize('tag', ['v0.2.0', 'main', 'v0.1.0-../../escape', 'v0.1.0-$(whoami)'])
def test_tag_must_identify_the_actual_packaged_version(tmp_path, tag):
    release_fixture(tmp_path)
    with pytest.raises(ValueError, match='Tag must match'):
        validate_release(tmp_path, tag, COMMIT)


def test_changed_installer_bytes_cannot_be_attached_to_a_draft(tmp_path):
    release_fixture(tmp_path)
    (tmp_path / 'artifacts/Saydraft-0.1.0-Setup.exe').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash or size'):
        validate_release(tmp_path, 'v0.1.0', COMMIT)


def test_checksums_must_describe_the_exact_files_being_attached(tmp_path):
    release_fixture(tmp_path)
    (tmp_path / 'artifacts/SHA256SUMS').write_text('stale')
    with pytest.raises(ValueError, match='SHA256SUMS'):
        validate_release(tmp_path, 'v0.1.0', COMMIT)


@pytest.mark.parametrize('name,key,value', [
    ('bundle.json', 'source_dirty', True), ('bundle.json', 'git_commit', 'c' * 40),
    ('bundle.json', 'packaging_gate', False), ('runtime.json', 'complete', False),
    ('installed-runtime.json', 'version', '0.0.0'), ('installer-smoke.json', 'junction_target_preserved', False),
    ('bundle.json', 'third_party_notices', None),
])
def test_incomplete_or_mismatched_proof_prevents_release_creation(tmp_path, name, key, value):
    reports = release_fixture(tmp_path)
    reports[name][key] = value
    (tmp_path / 'audit' / name).write_text(json.dumps(reports[name]), encoding='utf-8')
    with pytest.raises(ValueError):
        validate_release(tmp_path, 'v0.1.0', COMMIT)


def test_cli_writes_exact_reviewable_notes_and_manifest_without_publishing(tmp_path):
    release_fixture(tmp_path)
    notes, manifest = tmp_path / 'notes.md', tmp_path / 'release.json'
    assert main(['--build-root', str(tmp_path), '--tag', 'v0.1.0-dry-run.20261114', '--commit', COMMIT,
                 '--notes', str(notes), '--manifest', str(manifest)]) == 0
    result = json.loads(manifest.read_text())
    assert notes.read_text(encoding='utf-8') == release_notes(result)
    with pytest.raises(SystemExit):
        main(['--build-root', str(tmp_path), '--tag', 'v0.1.0', '--commit', COMMIT,
              '--notes', str(notes), '--manifest', str(manifest)])
