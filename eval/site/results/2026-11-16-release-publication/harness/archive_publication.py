import hashlib,json,shutil
from pathlib import Path
qa=Path(__file__).resolve().parent;repo=Path('C:/Users/tanzir/Desktop/voice_tray')
out=repo/'eval/site/results/2026-11-16-release-publication';out.mkdir(parents=True,exist_ok=True)
def copy(name,dest):
 target=out/dest;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(qa/name,target)
for name in ('release-notes.md','SHA256SUMS','BUILD_INFO.json','published-release.json','public-download-verification.json'):
 copy(name,'release/'+name)
release=json.loads((qa/'published-release.json').read_text('utf-8-sig'))
assert release['draft'] is False and release['prerelease'] is True
zip_asset=next(a for a in release['assets'] if a['name']=='Saydraft-0.1.0-win-x64.zip')
assert zip_asset['size']==157308167 and zip_asset['digest']=='sha256:b24ca638e91035c35029b67577b7d62859e22904618a9fa7e982a330ec40901f'
assert json.loads((qa/'live-pages-verification.json').read_text('utf-8'))['all_match'] is True
for name in ('pages-before.json','pages-after.json','pages-config.json','pages-publication.json','pages-publication.log','pages-publish-request.json','pages-build-status.json','live-pages-before.json','live-pages-verification.json'):
 copy(name,'publication/'+name)
for name in ('site-content-tests.log','site-content-tests-r2.log','site-build-r2.log','site-browser-tests.log','site-browser-final.log','site-home-final.log'):
 copy(name,'tests/'+name)
for name in ('verify_live.mjs','publish_static.ps1','archive_publication.py'):copy(name,'harness/'+name)
rows=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json']
(out/'manifest.json').write_text(json.dumps(dict(app_source='12bc27ffdb3ba388ea199e5e51661c968815c2fe',site_source='b41509817a9d402a42cae4c9097fba0617f3069e',pages_commit='2ce5c11b8412f00ef1795734368fd31b6a378983',files=rows),indent=2)+'\n',encoding='utf-8')
print('Archived',len(rows),'publication files')
