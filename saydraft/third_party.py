"""Verify the packaged notice inventory without importing application services."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath


def verify_notices(root: Path) -> dict:
    """Check retained bytes and component coverage; this is not a legal opinion.

    Used only by explicit package verification, never as an application startup
    restriction on replacing dynamically linked third-party libraries.
    """
    root = Path(root)
    if root.is_symlink() or root.is_junction():
        raise ValueError('Linked notice directory')
    index_path = root / 'index.json'
    if index_path.is_symlink() or not index_path.is_file():
        raise ValueError('Notice index missing or linked')
    index = json.loads(index_path.read_text(encoding='utf-8'))
    if index.get('schema_version') != 1 or not index.get('components') or not index.get('files'):
        raise ValueError('Invalid notice inventory')
    files = index['files']
    for relative, record in files.items():
        path = PurePosixPath(relative)
        if (not relative or '\\' in relative or ':' in relative or path.is_absolute()
                or any(part in ('', '.', '..') for part in relative.split('/'))):
            raise ValueError('Unsafe notice path')
        target = root.joinpath(*path.parts)
        if (any(p.is_symlink() or p.is_junction() for p in [target, *target.parents[:len(path.parts) - 1]])
                or not target.resolve().is_relative_to(root.resolve()) or not target.is_file()):
            raise ValueError('Missing, linked or escaped notice file')
        payload = target.read_bytes()
        if (record.get('bytes') != len(payload) or not payload
                or record.get('sha256') != hashlib.sha256(payload).hexdigest()):
            raise ValueError('Notice integrity check failed')
    names = set()
    for component in index['components']:
        name = component.get('name')
        if not isinstance(name, str) or not name or name.casefold() in names or not component.get('version'):
            raise ValueError('Invalid notice component')
        names.add(name.casefold())
        licenses = component.get('license_files')
        if not licenses or any(p not in files or files[p].get('kind') != 'license' for p in licenses):
            raise ValueError('Component has no retained full license text')
        if any(p not in files for p in component.get('notice_files', [])):
            raise ValueError('Component notice missing')
    return {'components': len(names), 'files': len(files),
            'index_sha256': hashlib.sha256(index_path.read_bytes()).hexdigest()}
