"""Audit actual PyInstaller tables and shipped files, then retain hashed artifacts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def forbidden_module(name, forbidden):
    name = name.casefold()
    return any(name == prefix.casefold() or name.startswith(prefix.casefold() + '.') for prefix in forbidden)


def audit_bundle(bundle, analysis, policy):
    # Inspect Analysis' actual module tables, not just visible .py file names:
    # most pure modules live inside the compressed PYZ archive after freezing.
    table = ast.literal_eval(analysis.read_text(encoding='utf-8'))
    modules = set()

    def walk(value):
        if isinstance(value, (list, tuple)):
            if (len(value) == 3 and isinstance(value[0], str) and isinstance(value[2], str)
                    and value[2] in ('PYMODULE', 'PYMODULE-1', 'PYMODULE-2', 'EXTENSION')):
                modules.add(value[0])
            for child in value:
                walk(child)

    walk(table)
    if not modules or any(forbidden_module(name, policy['forbidden_modules']) for name in modules):
        raise ValueError('Analysis contains a forbidden module or no inspected modules')
    if bundle.is_symlink() or bundle.is_junction():
        raise ValueError('Bundle root is linked')
    files = []
    for directory, folders, names in os.walk(bundle, followlinks=False):
        for name in [*folders, *names]:
            path = Path(directory) / name
            if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(bundle.resolve()):
                raise ValueError('Bundle contains linked or escaped paths')
        files.extend(Path(directory) / name for name in names)
    files.sort()
    if not files or not (bundle / 'Saydraft.exe').is_file():
        raise ValueError('Frozen application missing')
    for path in files:
        if path.is_symlink() or path.suffix.lower() in policy['forbidden_suffixes']:
            raise ValueError('Bundle contains weights, user data or linked files')
        relative = path.relative_to(bundle).as_posix().casefold()
        if any(part.casefold() in ('config.json', 'history.db', 'glossary.json', 'snippets.txt') for part in path.parts):
            raise ValueError('Bundle contains user configuration')
        if any(relative.startswith(prefix.casefold() + '/') or '/' + prefix.casefold() + '/' in relative
               for prefix in policy['forbidden_modules']):
            raise ValueError('Bundle contains a forbidden package directory')
        if any(part.casefold().startswith(prefix.casefold() + '-') and part.casefold().endswith('.dist-info')
               for part in path.parts for prefix in policy['forbidden_modules']):
            raise ValueError('Bundle contains forbidden distribution metadata')
    return {'inspected_modules': len(modules), 'files': len(files),
        'uncompressed_bytes': sum(p.stat().st_size for p in files),
        'file_sha256': {p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'analysis', 'artifacts', 'runtime-report', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--allow-missing-installer', action='store_true')
    parser.add_argument('--preflight', action='store_true', help='audit before compiling an installer; publish no artifacts')
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('audit output exists; retain it and choose a fresh path')
    policy = json.loads((ROOT / 'installer/bundle-policy.json').read_text(encoding='utf-8'))
    runtime = json.loads(args.runtime_report.read_text(encoding='utf-8'))
    if not runtime.get('complete') or not runtime.get('frozen'):
        raise ValueError('Frozen runtime verification did not pass')
    report = audit_bundle(args.bundle, args.analysis, policy)
    report.update(git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        runtime_report_sha256=hashlib.sha256(args.runtime_report.read_bytes()).hexdigest(),
        policy_sha256=hashlib.sha256((ROOT / 'installer/bundle-policy.json').read_bytes()).hexdigest())
    if args.preflight:
        report['preflight_only'] = True
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
        print(json.dumps({'preflight_only': True, 'files': report['files']}))
        return 0
    installers = sorted(args.artifacts.glob('Saydraft-*-Setup.exe'))
    if (not args.allow_missing_installer and len(installers) != 1 or len(installers) > 1
            or any(p.stat().st_size > policy['maximum_installer_bytes'] for p in installers)):
        raise ValueError('Expected one installer within the 250 MB limit')
    version = runtime['version']
    if installers and installers[0].name != f'Saydraft-{version}-Setup.exe':
        raise ValueError('Installer version does not match the verified runtime')
    archive = args.artifacts / f'Saydraft-{version}-win-x64.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
        for path in sorted(p for p in args.bundle.rglob('*') if p.is_file()):
            stream.write(path, 'Saydraft/' + path.relative_to(args.bundle).as_posix())
    report['artifacts'] = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                           for p in [*installers, archive]}
    report['installer_size_gate'] = len(installers) == 1
    report['packaging_gate'] = report['installer_size_gate'] and not report['source_dirty']
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    with (args.artifacts / 'SHA256SUMS').open('x', encoding='utf-8') as stream:
        stream.writelines(f'{value["sha256"]}  {name}\n' for name, value in sorted(report['artifacts'].items()))
    print(json.dumps({key: report[key] for key in ('files', 'uncompressed_bytes', 'installer_size_gate', 'packaging_gate')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
