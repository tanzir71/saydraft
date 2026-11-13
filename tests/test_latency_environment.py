import copy
import hashlib
import importlib.metadata as metadata
from types import SimpleNamespace

import pytest

from tools import latency_environment as provenance
from tools.latency_matrix import validate_pair


def test_provenance_records_installed_versions_and_the_actual_interpreter(tmp_path, monkeypatch):
    executable = tmp_path / 'python.exe'
    executable.write_bytes(b'owned interpreter fixture')
    monkeypatch.setattr(provenance, 'sys', SimpleNamespace(executable=str(executable),
        implementation=SimpleNamespace(name='cpython', cache_tag='cpython-313')))

    def version(name):
        if name == 'onnxruntime':
            raise metadata.PackageNotFoundError(name)
        return '4.9.0' if name == 'ctranslate2' else 'fixture'

    monkeypatch.setattr(provenance.metadata, 'version', version)
    result = provenance.runtime_environment()
    assert result['packages']['ctranslate2'] == '4.9.0'
    assert result['packages']['onnxruntime'] is None
    assert result['interpreter_sha256'] == hashlib.sha256(executable.read_bytes()).hexdigest()
    assert str(tmp_path) not in str(result)


@pytest.mark.parametrize('change', ['missing', 'version', 'interpreter'])
def test_environment_drift_cannot_count_as_a_completed_measurement(change):
    environment = {'interpreter_sha256': 'original', 'packages': {'ctranslate2': '4.9.0'}}
    pair = {'complete': True, 'git_commit': 'source', 'audio_seconds': 3, 'repeat': 0,
            'asr_model': 'whisper-base', 'runtime_environment': copy.deepcopy(environment),
            'cases': [{}, {}]}
    if change == 'missing':
        pair.pop('runtime_environment')
    elif change == 'version':
        pair['runtime_environment']['packages']['ctranslate2'] = '4.8.1'
    else:
        pair['runtime_environment']['interpreter_sha256'] = 'different'
    with pytest.raises(ValueError, match='runtime environment differs'):
        validate_pair(pair, seconds=3, repeat=0, commit='source', model='whisper-base', environment=environment)


@pytest.mark.parametrize('tier,missing', [('lite', 'ctranslate2'), ('lite', 'faster-whisper'),
    ('standard', 'sherpa-onnx-core'), ('pro', 'onnxruntime')])
def test_missing_selected_engine_metadata_cannot_qualify(tier, missing):
    environment = {'packages': dict.fromkeys(provenance.PACKAGES, 'present')}
    provenance.require_runtime_versions(environment, tier)
    environment['packages'][missing] = None
    with pytest.raises(ValueError, match='dependency version is unavailable'):
        provenance.require_runtime_versions(environment, tier)
