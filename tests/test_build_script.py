import hashlib
import json
from pathlib import Path

import pytest

from tools.package_audit import audit_bundle


POLICY = json.loads(Path('installer/bundle-policy.json').read_text(encoding='utf-8'))


def frozen_fixture(tmp_path, *, modules=()):
    bundle = tmp_path / 'application'
    bundle.mkdir()
    (bundle / 'Saydraft.exe').write_bytes(b'owned frozen fixture')
    table = tmp_path / 'Analysis-00.toc'
    rows = [('saydraft.main', '/source/saydraft/main.py', 'PYMODULE'), *modules]
    table.write_text(repr((rows,)), encoding='utf-8')
    return bundle, table


@pytest.mark.parametrize('code', ['EXTENSION', 'PYMODULE', 'PYMODULE-1', 'PYMODULE-2'])
def test_bundle_audit_reads_the_module_table_even_when_packages_are_compressed(tmp_path, code):
    bundle, table = frozen_fixture(tmp_path, modules=[('pyarrow.lib', '/wheel/lib.pyd', code)])
    assert not list(bundle.rglob('*pyarrow*'))
    with pytest.raises(ValueError, match='forbidden module'):
        audit_bundle(bundle, table, POLICY)


@pytest.mark.parametrize('name', ['aiohttp.client', 'AIOHTTP.client', 'pytest', '_pytest.config', 'PyInstaller.loader', 'torch'])
def test_bundle_audit_refuses_development_and_unrelated_runtime_modules(tmp_path, name):
    bundle, table = frozen_fixture(tmp_path, modules=[(name, '/wheel/file.py', 'PYMODULE')])
    with pytest.raises(ValueError, match='forbidden module'):
        audit_bundle(bundle, table, POLICY)


@pytest.mark.parametrize('relative', ['model.gguf', 'model.bin', 'History.DB', '_internal/Config.JSON',
    '_internal/faster_whisper/assets/silero_vad.onnx', 'weights.safetensors'])
def test_bundle_audit_refuses_model_weights_and_user_data(tmp_path, relative):
    bundle, table = frozen_fixture(tmp_path)
    path = bundle / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'not distributable')
    with pytest.raises(ValueError):
        audit_bundle(bundle, table, POLICY)


def test_bundle_audit_retains_exact_file_hashes(tmp_path):
    bundle, table = frozen_fixture(tmp_path)
    report = audit_bundle(bundle, table, POLICY)
    assert report['inspected_modules'] == 1 and report['files'] == 1
    assert report['uncompressed_bytes'] == len(b'owned frozen fixture')
    assert report['file_sha256'] == {'Saydraft.exe': hashlib.sha256(b'owned frozen fixture').hexdigest()}


def test_empty_analysis_cannot_earn_a_bundle_audit(tmp_path):
    bundle, table = frozen_fixture(tmp_path)
    table.write_text('([],)', encoding='utf-8')
    with pytest.raises(ValueError, match='no inspected modules'):
        audit_bundle(bundle, table, POLICY)


def test_runtime_requirements_do_not_install_pytest_into_the_build_environment():
    requirements = Path('requirements.txt').read_text(encoding='utf-8').lower()
    development = Path('requirements-dev.txt').read_text(encoding='utf-8').lower()
    assert 'pytest' not in requirements and 'pytest==8.3.2' in development
    assert 'pyinstaller==6.22.3' in requirements
