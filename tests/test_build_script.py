import hashlib
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.package_audit import audit_bundle


POLICY = json.loads(Path('installer/bundle-policy.json').read_text(encoding='utf-8'))


def frozen_fixture(tmp_path, *, modules=()):
    bundle = tmp_path / 'application'
    bundle.mkdir()
    (bundle / 'Saydraft.exe').write_bytes(b'owned frozen fixture')
    notices = bundle / '_internal/third_party_licenses'
    notices.mkdir(parents=True)
    payload = b'Unchanged full license text fixture'
    (notices / 'LICENSE.txt').write_bytes(payload)
    (notices / 'index.json').write_text(json.dumps({'schema_version': 1,
        'components': [{'name': 'fixture', 'version': '1', 'license_files': ['LICENSE.txt']}],
        'files': {'LICENSE.txt': {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
                                  'kind': 'license'}}}), encoding='utf-8')
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
    assert report['inspected_modules'] == 1 and report['files'] == 3
    assert report['third_party_notices']['components'] == 1
    assert report['file_sha256']['Saydraft.exe'] == hashlib.sha256(b'owned frozen fixture').hexdigest()


def test_bundle_audit_requires_the_shipped_notice_inventory(tmp_path):
    bundle, table = frozen_fixture(tmp_path)
    (bundle / '_internal/third_party_licenses/index.json').unlink()
    with pytest.raises(ValueError, match='Notice index missing'):
        audit_bundle(bundle, table, POLICY)


def test_notice_inventory_must_cover_the_actual_compressed_module_graph(tmp_path):
    bundle, table = frozen_fixture(tmp_path, modules=[('uncovered.module', '/source/module.py', 'PYMODULE')])
    with pytest.raises(ValueError, match='Frozen module notice coverage missing'):
        audit_bundle(bundle, table, POLICY)


@pytest.mark.parametrize('name', ['Qt6Quick.dll', 'qpdf.dll', 'Qt6VirtualKeyboard.dll'])
def test_unused_native_plugin_dependencies_are_not_shipped(tmp_path, name):
    bundle, table = frozen_fixture(tmp_path)
    (bundle / name).write_bytes(b'owned native-library fixture')
    with pytest.raises(ValueError, match='unused native'):
        audit_bundle(bundle, table, POLICY)


def test_qt_hook_keeps_required_image_plugins_without_optional_native_dependencies(monkeypatch):
    plugins = [(str(Path('plugins') / name), 'PySide6/plugins')
               for name in ('qsvg.dll', 'qjpeg.dll', 'qpdf.dll', 'qtvirtualkeyboardplugin.dll')]
    monkeypatch.setitem(sys.modules, 'PyInstaller.utils.hooks.qt',
                        SimpleNamespace(add_qt6_dependencies=lambda _: (['PySide6.QtCore'], plugins, [])))
    result = runpy.run_path('installer/hooks/hook-PySide6.QtGui.py')
    assert {Path(source).name for source, _ in result['binaries']} == {'qsvg.dll', 'qjpeg.dll'}
    assert result['hiddenimports'] == ['PySide6.QtCore']


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
