"""Retain full wheel notices for the actual frozen module graph, plus pinned gaps.

This build-only collector copies data, never installs or imports dependencies.
Upstream supplemental catalogs can include notices for unused optional features;
their presence does not assert that those features are distributed.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
import re
import sys
from pathlib import Path, PurePosixPath

from saydraft.third_party import verify_notices

REQUIRED_SUPPLEMENTS = {'pyside6', 'pyside6-addons', 'pyside6-essentials', 'shiboken6',
                        'ctranslate2', 'tokenizers', 'sherpa-onnx-core', 'av'}


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def notice_kind(relative):
    """Match text notice names, not executable modules such as packaging.licenses."""
    path = PurePosixPath(str(relative).replace('\\', '/'))
    name = path.name.casefold()
    if path.suffix.casefold() in ('.py', '.pyc', '.pyd', '.dll', '.so'):
        return None
    if name.startswith(('license', 'licence', 'copying')):
        return 'license'
    if name.startswith(('copyright', 'notice', 'thirdpartynotice', 'third_party_notice', 'authors')):
        return 'notice'
    if '.dist-info/licenses/' in path.as_posix().casefold():
        return 'notice'
    return None


def module_distributions(rows, package_map=None):
    """Resolve Windows extension destinations and pure module names consistently."""
    package_map = metadata.packages_distributions() if package_map is None else package_map
    result = {}
    for name, _source, kind in rows:
        if kind not in ('PYMODULE', 'PYMODULE-1', 'PYMODULE-2', 'EXTENSION'):
            continue
        root = name.replace('\\', '/').split('/')[0].split('.')[0]
        if root in sys.stdlib_module_names or root in ('saydraft', '_pyi_rth_utils'):
            continue
        distributions = package_map.get(root)
        if not distributions:
            raise ValueError(f'No distribution owns frozen module: {root}')
        for distribution in distributions:
            result.setdefault(canonical(distribution), set()).add(root)
    # The executable contains PyInstaller's bootloader even though build-tool
    # Python modules must remain excluded from the application archive.
    result.setdefault('pyinstaller', set())
    return result


def collect_notices(rows, output, project, *, compiler=None, distribution=metadata.distribution, package_map=None):
    output, project = Path(output), Path(project)
    if output.exists():
        raise ValueError('Retain previous notice output and choose a fresh path')
    output.mkdir(parents=True)
    supplements = json.loads((project / 'installer/notice-supplements.json').read_text(encoding='utf-8'))
    files, components = {}, []

    def retain(payload, relative, kind):
        path = PurePosixPath(relative)
        if (path.is_absolute() or '\\' in relative or ':' in relative
                or any(p in ('', '.', '..') for p in relative.split('/'))):
            raise ValueError('Unsafe upstream notice filename')
        if not payload or len(payload) > 10_000_000:
            raise ValueError('Empty or oversized upstream notice')
        record = {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(), 'kind': kind}
        if relative in files:
            if files[relative] != record:
                raise ValueError('Conflicting upstream notices')
            return relative
        target = output.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        files[relative] = record
        return relative

    def supplemental(component, key):
        entry = supplements['components'][key]
        if component['version'] not in entry['versions']:
            raise ValueError(f'Unreviewed notice supplement version: {key} {component["version"]}')
        catalogs = [entry, *[supplements['catalogs'][name] for name in entry.get('catalogs', [])]]
        for item in [item for catalog in catalogs for item in catalog.get('files', [])]:
            source = project / item['path']
            if source.is_symlink() or not source.resolve().is_relative_to(project.resolve()):
                raise ValueError('Linked or escaped supplemental notice')
            payload = source.read_bytes()
            if len(payload) != item['bytes'] or hashlib.sha256(payload).hexdigest() != item['sha256']:
                raise ValueError('Supplemental notice integrity check failed')
            relative = retain(payload, 'supplements/' + item['destination'], item['kind'])
            component['license_files' if item['kind'] == 'license' else 'notice_files'].append(relative)
        component['sources'].extend(source for catalog in catalogs for source in catalog.get('sources', []))
        for binary in entry.get('binary_checks', []):
            owned = distribution(key).locate_file(binary['path'])
            if hashlib.sha256(Path(owned).read_bytes()).hexdigest() != binary['sha256']:
                raise ValueError('Unreviewed native dependency version')

    for name, modules in sorted(module_distributions(rows, package_map).items()):
        if name in REQUIRED_SUPPLEMENTS and name not in supplements['components']:
            raise ValueError(f'Required native/upstream notice supplement missing: {name}')
        dist = distribution(name)
        component = {'name': name, 'version': dist.version, 'modules': sorted(modules),
                     'license_files': [], 'notice_files': [], 'sources': []}
        for number, item in enumerate(dist.files or []):
            relative = str(item).replace('\\', '/')
            kind = notice_kind(relative)
            if not kind:
                continue
            # RECORD can legitimately refer outside site-packages for scripts;
            # notices may not do so, and must not be links.
            source = Path(dist.locate_file(item))
            base = Path(dist.locate_file('')).resolve()
            if (source.is_symlink() or source.is_junction() or not source.resolve().is_relative_to(base)
                    or not source.is_file()):
                raise ValueError(f'Unsafe upstream notice: {name}')
            # Store notices as plain data without real package or .dist-info
            # directories, including the bootloader's build-tool notice.
            retained = retain(source.read_bytes(), f'distributions/component-{name}/{number:05d}-{source.name}', kind)
            files[retained]['upstream_path'] = relative
            component['license_files' if kind == 'license' else 'notice_files'].append(retained)
        info = dist.read_text('METADATA')
        if not info:
            raise ValueError(f'Distribution metadata missing: {name}')
        component['metadata_file'] = retain(info.encode('utf-8'), f'distributions/component-{name}/METADATA.txt', 'metadata')
        component['sources'] = [*dist.metadata.get_all('Project-URL', []), *dist.metadata.get_all('Home-page', [])]
        if name in supplements['components']:
            supplemental(component, name)
        if not component['license_files']:
            raise ValueError(f'Full upstream license missing: {name} {dist.version}')
        components.append(component)

    runtime = Path(sys.base_prefix) / 'LICENSE.txt'
    license_path = retain(runtime.read_bytes(), 'python/LICENSE.txt', 'license')
    components.append({'name': 'python', 'version': sys.version.split()[0], 'license_files': [license_path],
                       'notice_files': [], 'sources': ['https://www.python.org/downloads/source/']})
    if compiler:
        compiler_license = Path(compiler).parent / 'license.txt'
        retained = retain(compiler_license.read_bytes(), 'inno-setup/license.txt', 'license')
        components.append({'name': 'inno-setup', 'version': 'installed-compiler-license',
                           'license_files': [retained], 'notice_files': [],
                           'sources': ['https://github.com/jrsoftware/issrc']})
    index = {'schema_version': 1, 'components': components, 'files': files,
             'scope': 'Full supplied distribution notices and version-pinned upstream supplements; not a legal opinion.'}
    (output / 'index.json').write_text(json.dumps(index, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    verify_notices(output)
    return [('third_party_licenses/' + p.relative_to(output).as_posix(), str(p), 'DATA')
            for p in sorted(output.rglob('*')) if p.is_file()]
