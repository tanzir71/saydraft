from pathlib import Path
import hashlib
import io
import json
import subprocess
import tarfile

repo = Path('C:/Users/tanzir/Desktop/voice_tray')
roots = ['eval/cleanup/results/2026-11-17-cleanup-repair',
         'eval/ui/results/2026-11-17-voice-notes',
         'eval/ui/results/2026-11-17-voice-notes-portable']


def git(path):
    return subprocess.check_output(['git', 'show', 'HEAD:' + path], cwd=repo)


def check(raw, record):
    assert len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['sha256'], record['path']


count = 0
for root in roots:
    manifest = json.loads(git(root + '/manifest.json'))
    if 'archive' in manifest:
        raw = git(root + '/' + manifest['archive'])
        assert hashlib.sha256(raw).hexdigest() == manifest['archive_sha256']
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
            assert len(archive.getmembers()) == len(manifest['records'])
            for record in manifest['records']:
                member = archive.getmember(record['path'])
                assert member.isfile()
                check(archive.extractfile(member).read(), record)
                count += 1
    else:
        for record in manifest['records']:
            check(git(root + '/' + record['path']), record)
            count += 1
    for record in manifest.get('supplemental', []):
        check(git(root + '/' + record['path']), record)
        count += 1
result = dict(git_blob_records_verified=count, roots=roots, passed=True)
(Path(__file__).parent / 'records-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
