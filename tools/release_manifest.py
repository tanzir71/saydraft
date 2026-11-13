"""Validate a clean unsigned package before creating a draft GitHub release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def validate_release(root: Path, tag: str, commit: str):
    root = Path(root)

    def report(name):
        return json.loads((root / 'audit' / name).read_text(encoding='utf-8-sig'))

    bundle, runtime, installed, smoke = [report(name) for name in (
        'bundle.json', 'runtime.json', 'installed-runtime.json', 'installer-smoke.json')]
    version = runtime.get('version', '')
    if (not re.fullmatch(r'\d+\.\d+\.\d+', version)
            or not re.fullmatch('v' + re.escape(version) + r'(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?', tag)):
        raise ValueError('Tag must match the packaged version, optionally with a prerelease suffix')
    if (not re.fullmatch('[0-9a-f]{40}', commit) or bundle.get('git_commit') != commit
            or bundle.get('source_dirty') is not False or bundle.get('packaging_gate') is not True):
        raise ValueError('Release requires the exact clean, accepted source commit')
    notices = bundle.get('third_party_notices')
    if (not isinstance(notices, dict) or type(notices.get('components')) is not int or notices['components'] <= 0
            or type(notices.get('files')) is not int or notices['files'] <= 0
            or not re.fullmatch('[0-9a-f]{64}', notices.get('index_sha256', ''))):
        raise ValueError('Verified notice inventory is missing')
    for result in (runtime, installed):
        if (result.get('complete') is not True or result.get('frozen') is not True
                or result.get('version') != version
                or any(result.get('checks', {}).get(name) is not True for name in (
                    'resources', 'third_party_notices', 'native_imports', 'tray_images',
                    'python_network_guard', 'forbidden_modules_absent'))
                or result.get('third_party_notices') != bundle.get('third_party_notices')):
            raise ValueError('Frozen verification or notice inventory did not pass')
    if (smoke.get('complete') is not True or any(smoke.get(name) is not True for name in (
            'default_keeps_data', 'explicit_removes_data', 'autostart_default_off',
            'autostart_opt_in', 'startup_removed', 'junction_target_preserved'))):
        raise ValueError('Installer lifecycle acceptance did not pass')
    artifacts = bundle.get('artifacts', {})
    expected = {f'Saydraft-{version}-Setup.exe', f'Saydraft-{version}-win-x64.zip'}
    if set(artifacts) != expected:
        raise ValueError('Release requires exactly the verified installer and portable ZIP')
    directory = root / 'artifacts'
    if root.is_symlink() or root.is_junction() or directory.is_symlink() or directory.is_junction():
        raise ValueError('Release artifact directory is linked')
    for name, record in artifacts.items():
        path = directory / name
        if path.is_symlink() or path.is_junction() or not path.is_file():
            raise ValueError('Release artifact is missing or linked')
        payload = path.read_bytes()
        if len(payload) != record.get('bytes') or hashlib.sha256(payload).hexdigest() != record.get('sha256'):
            raise ValueError('Release artifact hash or size differs from the package audit')
        if name.endswith('-Setup.exe') and len(payload) > 250_000_000:
            raise ValueError('Installer exceeds 250 MB')
    sums = ''.join(f'{record["sha256"]}  {name}\n' for name, record in sorted(artifacts.items()))
    if (directory / 'SHA256SUMS').read_text(encoding='utf-8') != sums:
        raise ValueError('SHA256SUMS does not match the verified release artifacts')
    return {'schema': 1, 'tag': tag, 'version': version, 'commit': commit, 'draft': True,
            'signed': False, 'artifacts': artifacts, 'third_party_notices': bundle['third_party_notices']}


def release_notes(manifest):
    installer = next(value for name, value in manifest['artifacts'].items() if name.endswith('-Setup.exe'))
    return (f'Saydraft {manifest["version"]} — unsigned verification draft\n\n'
            f'Source commit: `{manifest["commit"]}`.\n\n'
            f'Windows x64 per-user installer: {installer["bytes"] / 1_000_000:.1f} MB. '
            'The portable ZIP and SHA256SUMS are attached.\n\n'
            'The clean build passed frozen resource/notice verification and the disposable '
            'install/uninstall lifecycle. Default uninstall keeps user data; autostart is opt-in.\n\n'
            'Model weights are downloaded separately after setup shows their sizes and licenses. '
            'Bengali and Arabic share the optional All languages model.\n\n'
            'This draft is unsigned. Signing, corresponding-source delivery for publication, '
            'owner accuracy and physical Windows acceptance remain separate release checks.\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-root', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--notes', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.notes.exists() or args.manifest.exists():
        parser.error('Retain existing release notes/manifest and choose fresh paths')
    manifest = validate_release(args.build_root, args.tag, args.commit)
    with args.manifest.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    with args.notes.open('x', encoding='utf-8') as stream:
        stream.write(release_notes(manifest))
    print(json.dumps({'validated': True, 'draft': True, 'tag': args.tag}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
