"""Verify actual complete portable disk/ZIP bytes, without app imports."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--source', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
build = args.build.resolve()
audit = json.loads((build/'audit/bundle.json').read_text(encoding='utf-8-sig'))
assert audit['git_commit'] == args.source and audit['source_dirty'] is False
payload = build/'dist/Saydraft'

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def safe(name):
    path = PurePosixPath(name)
    assert name == path.as_posix() and not path.is_absolute()
    assert '..' not in path.parts and '\\' not in name and ':' not in name
    return path

disk = {}
for path in sorted(payload.rglob('*')):
    assert not path.is_symlink()
    if path.is_file():
        name = path.relative_to(payload).as_posix()
        safe(name)
        disk[name] = digest(path)
assert disk == audit['file_sha256'] and len(disk) == audit['files']
archives = sorted((build/'artifacts').glob('*.zip'))
assert len(archives) == 1
archive = archives[0]
artifact = audit['artifacts'][archive.name]
assert digest(archive) == artifact['sha256'] and archive.stat().st_size == artifact['bytes']
zipped = {}
with zipfile.ZipFile(archive) as source:
    all_names = [entry.filename for entry in source.infolist()]
    assert len(set(all_names)) == len(all_names)
    for entry in source.infolist():
        path = safe(entry.filename.rstrip('/'))
        assert path.parts[0] == 'Saydraft'
        if not entry.is_dir():
            name = '/'.join(path.parts[1:])
            assert name and name not in zipped
            with source.open(entry) as stream:
                zipped[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
assert zipped == disk
report = dict(source=args.source, artifact_name=archive.name, **artifact,
    files_verified=len(disk), uncompressed_bytes=sum(path.stat().st_size for path in payload.rglob('*') if path.is_file()),
    third_party_notices=audit['third_party_notices'], installer_built=False,
    signed=False, release_ready=False, module_code_executed=False,
    method='Read/hash every actual disk and ZIP payload; require complete exact audited sets, unique safe archive paths and artifact bytes/hash.')
args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(json.dumps(report, indent=2))
