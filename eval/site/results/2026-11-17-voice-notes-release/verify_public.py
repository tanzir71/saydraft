"""Unauthenticated read-only verification; streamed ZIP is never written twice."""
from pathlib import Path
import hashlib
import json
import re
import sys
import time
from urllib.request import Request, urlopen

qa = Path(__file__).parent
repo = Path('C:/Users/tanzir/Desktop/voice_tray')
build = Path('D:/Saydraft-Codex-QA-20261112-01a1cbc7/cleanup-note-package-20261117-r1')
tag = 'v0.1.1-preview.20261117'
source = 'dcfab880d1896f1fbdb32be7e34387c2b46b0ad5'
base = 'https://tanzir71.github.io/saydraft/'


def open_public(url):
    return urlopen(Request(url, headers={'User-Agent': 'Saydraft-public-verification',
        'Cache-Control': 'no-cache'}), timeout=45)


def read(url):
    with open_public(url) as response:
        return response.read()


if sys.argv[1] == 'release':
    info = json.loads(read('https://api.github.com/repos/tanzir71/saydraft/releases/tags/' + tag))
    assert info['prerelease'] is True and info['draft'] is False and info['target_commitish'] == source
    rows = []
    for name in ('Saydraft-0.1.1-win-x64.zip', 'SHA256SUMS', 'BUILD_INFO.json'):
        asset = next(a for a in info['assets'] if a['name'] == name)
        local = qa / name if name == 'BUILD_INFO.json' else build / 'artifacts' / name
        expected = hashlib.sha256(local.read_bytes()).hexdigest()
        sha, count = hashlib.sha256(), 0
        with open_public(asset['browser_download_url'] + '?verify=20261117') as response:
            assert response.status == 200
            while chunk := response.read(1024 * 1024):
                sha.update(chunk)
                count += len(chunk)
        assert count == local.stat().st_size == asset['size'] and sha.hexdigest() == expected
        rows.append(dict(name=name, bytes=count, sha256=expected, unauthenticated=True, status=200))
    receipt = dict(source=source, tag=tag, release_url=info['html_url'], assets=rows)
else:
    rows = []
    for page in ('', 'download/', 'changelog/', 'docs/notes/'):
        local = (repo / 'site/dist' / page / 'index.html').read_bytes().replace(b'\r\n', b'\n')
        last_error = None
        for attempt in range(24):
            try:
                remote = read(base + page + '?verify=20261117').replace(b'\r\n', b'\n')
                assert remote == local, 'Pages still serves earlier HTML'
                break
            except Exception as error:
                last_error = str(error)
                time.sleep(5)
        else:
            raise AssertionError(last_error)
        rows.append(dict(path=page, status=200, html_matches_local=True,
                         sha256=hashlib.sha256(remote).hexdigest()))
    html = (repo / 'site/dist/index.html').read_text(encoding='utf-8')
    assets = sorted(set(re.findall(r'(?:href|src)="(/saydraft/_astro/[^"?]+\.(?:css|woff2))"', html)))[:3]
    assert assets
    for asset in assets:
        raw = read('https://tanzir71.github.io' + asset)
        local = repo / 'site/dist' / asset.removeprefix('/saydraft/')
        assert raw == local.read_bytes()
        rows.append(dict(path=asset, status=200, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    receipt = dict(tag=tag, base=base, checks=rows, custom_workflow_dispatched=False)
out = qa / ('public-' + sys.argv[1] + '.json')
out.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt))
