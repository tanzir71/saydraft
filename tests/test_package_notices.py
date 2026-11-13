import hashlib
import json
from email.message import Message
from pathlib import Path

import pytest

from saydraft.third_party import verify_notices
from tools.package_notices import collect_notices, module_distributions, notice_kind


def notice_fixture(root):
    root.mkdir(parents=True)
    payload = b'Full upstream license, retained unchanged.'
    (root / 'LICENSE.txt').write_bytes(payload)
    index = {'schema_version': 1,
             'components': [{'name': 'fixture', 'version': '1.0', 'license_files': ['LICENSE.txt']}],
             'files': {'LICENSE.txt': {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
                                       'kind': 'license'}}}
    (root / 'index.json').write_text(json.dumps(index), encoding='utf-8')
    return index


def test_notice_verification_hashes_the_actual_shipped_text(tmp_path):
    notice_fixture(tmp_path / 'notices')
    result = verify_notices(tmp_path / 'notices')
    assert result['components'] == result['files'] == 1
    (tmp_path / 'notices/LICENSE.txt').write_bytes(b'replaced')
    with pytest.raises(ValueError, match='integrity'):
        verify_notices(tmp_path / 'notices')


@pytest.mark.parametrize('relative', ['../LICENSE', '/LICENSE', 'C:/LICENSE', 'sub\\LICENSE', 'sub/../LICENSE'])
def test_notice_index_cannot_read_outside_its_inventory(tmp_path, relative):
    index = notice_fixture(tmp_path / 'notices')
    index['files'][relative] = index['files'].pop('LICENSE.txt')
    (tmp_path / 'notices/index.json').write_text(json.dumps(index), encoding='utf-8')
    with pytest.raises(ValueError, match='Unsafe'):
        verify_notices(tmp_path / 'notices')


def test_metadata_or_a_notice_cannot_stand_in_for_a_full_license(tmp_path):
    index = notice_fixture(tmp_path / 'notices')
    index['files']['LICENSE.txt']['kind'] = 'metadata'
    (tmp_path / 'notices/index.json').write_text(json.dumps(index), encoding='utf-8')
    with pytest.raises(ValueError, match='full license'):
        verify_notices(tmp_path / 'notices')


def test_notice_index_requires_every_component_to_have_a_retained_license(tmp_path):
    index = notice_fixture(tmp_path / 'notices')
    index['components'].append({'name': 'missing', 'version': '1', 'license_files': ['absent']})
    (tmp_path / 'notices/index.json').write_text(json.dumps(index), encoding='utf-8')
    with pytest.raises(ValueError, match='full license'):
        verify_notices(tmp_path / 'notices')


def test_module_mapping_includes_split_native_distributions_and_optimized_code():
    rows = [('sherpa_onnx\\lib\\_sherpa_onnx.pyd', 'ignored', 'EXTENSION'),
            ('example.feature', 'ignored', 'PYMODULE-2'), ('json', 'ignored', 'PYMODULE')]
    result = module_distributions(rows, {'sherpa_onnx': ['sherpa_onnx', 'sherpa-onnx-core'], 'example': ['Example']})
    assert result == {'sherpa-onnx': {'sherpa_onnx'}, 'sherpa-onnx-core': {'sherpa_onnx'},
                      'example': {'example'}, 'pyinstaller': set()}
    with pytest.raises(ValueError, match='No distribution'):
        module_distributions([('unknown', 'ignored', 'PYMODULE')], {})


@pytest.mark.parametrize('path,kind', [('x.dist-info/licenses/LICENSE.MIT', 'license'),
    ('x.dist-info/licenses/AUTHORS.rst', 'notice'), ('library/ThirdPartyNotices.txt', 'notice'),
    ('library/COPYING', 'license'), ('packaging/licenses/_spdx.py', None),
    ('x.dist-info/licenses/AUTHORS.py', None), ('library.pyc', None)])
def test_only_notice_data_is_collected(path, kind):
    assert notice_kind(path) == kind


class Distribution:
    version = '1.0'

    def __init__(self, root, *, license=True):
        self.root = root
        self.files = [Path('LICENSE.txt')] if license else []
        self.metadata = Message()

    def locate_file(self, relative):
        return self.root / relative

    def read_text(self, name):
        return 'Name: Fixture\nVersion: 1.0\nLicense: MIT\n'


def collector_fixture(tmp_path, monkeypatch, *, license=True):
    wheel = tmp_path / 'wheel'
    wheel.mkdir()
    (wheel / 'LICENSE.txt').write_bytes(b'An unchanged full upstream license.')
    (tmp_path / 'installer').mkdir()
    (tmp_path / 'installer/notice-supplements.json').write_text('{"components": {}}')
    python = tmp_path / 'python'
    python.mkdir()
    (python / 'LICENSE.txt').write_bytes(b'Python runtime full license fixture')
    monkeypatch.setattr('tools.package_notices.sys.base_prefix', str(python))
    return Distribution(wheel, license=license)


def test_collector_keeps_full_bytes_and_bootloader_notice_without_code(tmp_path, monkeypatch):
    dist = collector_fixture(tmp_path, monkeypatch)
    rows = [('example.foo', 'unused', 'PYMODULE')]
    output = tmp_path / 'collected'
    toc = collect_notices(rows, output, tmp_path, distribution=lambda _: dist, package_map={'example': ['Example']})
    assert all(kind == 'DATA' and not Path(source).suffix == '.py' for _, source, kind in toc)
    index = json.loads((output / 'index.json').read_text())
    assert {c['name'] for c in index['components']} == {'example', 'pyinstaller', 'python'}
    assert (output / 'distributions/component-example/00000-LICENSE.txt').read_bytes() == (dist.root / 'LICENSE.txt').read_bytes()
    assert verify_notices(output)['components'] == 3


def test_collector_refuses_license_identifier_without_full_text(tmp_path, monkeypatch):
    dist = collector_fixture(tmp_path, monkeypatch, license=False)
    with pytest.raises(ValueError, match='Full upstream license missing'):
        collect_notices([], tmp_path / 'collected', tmp_path, distribution=lambda _: dist, package_map={})


def test_supplement_is_rejected_when_dependency_version_changes(tmp_path, monkeypatch):
    dist = collector_fixture(tmp_path, monkeypatch)
    manifest = {'components': {'pyinstaller': {'versions': ['other-version'], 'files': [], 'sources': []}}}
    (tmp_path / 'installer/notice-supplements.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Unreviewed notice supplement version'):
        collect_notices([], tmp_path / 'collected', tmp_path, distribution=lambda _: dist, package_map={})


def test_supplement_hash_is_checked_before_collection(tmp_path, monkeypatch):
    dist = collector_fixture(tmp_path, monkeypatch)
    payload = tmp_path / 'upstream.txt'
    payload.write_bytes(b'changed')
    manifest = {'components': {'pyinstaller': {'versions': ['1.0'], 'sources': [], 'files': [
        {'path': 'upstream.txt', 'destination': 'upstream.txt', 'kind': 'license', 'bytes': 7, 'sha256': '0' * 64}]}}}
    (tmp_path / 'installer/notice-supplements.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='integrity'):
        collect_notices([], tmp_path / 'collected', tmp_path, distribution=lambda _: dist, package_map={})


def test_qt_commercial_notice_alone_cannot_pass_the_open_source_package_gate(tmp_path, monkeypatch):
    dist = collector_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='Required native/upstream notice supplement missing: pyside6'):
        collect_notices([('PySide6.QtGui', 'unused', 'PYMODULE')], tmp_path / 'collected', tmp_path,
                        distribution=lambda _: dist, package_map={'PySide6': ['PySide6']})
