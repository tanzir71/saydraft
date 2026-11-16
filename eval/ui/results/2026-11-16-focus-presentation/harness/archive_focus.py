import hashlib,json,shutil,xml.etree.ElementTree as ET
from pathlib import Path
qa=Path(__file__).resolve().parent;repo=Path('C:/Users/tanzir/Desktop/voice_tray')
out=repo/'eval/ui/results/2026-11-16-focus-presentation';out.mkdir(parents=True,exist_ok=True)
def copy(path,dest):
 target=out/dest;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(qa/path,target)
def guard(path):
 d=json.loads(path.read_text('utf-8'))
 assert d['blocked_attempts']==[]
 for key in ('real_audio_sdk_imported','owner_profile_used','owner_clipboard_used','owner_native_input_used','device_enumeration','microphone_used'):assert d[key] is False
for name in ('focus-theme-final','keyboard-integration'):
 guard(qa/(name+'.guard.json'))
 for suffix in ('.log','.xml','.guard.json','.guard.worker.json','.stub.json'):
  p=qa/(name+suffix)
  if p.exists():copy(p.name,'tests/'+p.name)
 assert json.loads((qa/(name+'.guard.worker.json')).read_text('utf-8'))['port_attempts']==[]
 assert json.loads((qa/(name+'.stub.json')).read_text('utf-8'))['unexpected_port_attempts']==[]
 for s in ET.parse(qa/(name+'.xml')).getroot().findall('testsuite'):assert int(s.get('failures',0))==int(s.get('errors',0))==0
for suffix in ('.log','.xml'):copy('gallery-tests'+suffix,'tests/gallery-tests'+suffix)
for i,p in enumerate(sorted((qa/'gallery-tests-temp').rglob('gallery.guard.json'))):
 guard(p);copy(p.relative_to(qa),f'tests/gallery-{i+1}-guard.json')
for p in sorted((qa/'focus-theme-final-temp').rglob('*.png')):copy(p.relative_to(qa),'screenshots/'+p.name)
for name in ('focus-theme','focus-theme-r2','focus-theme-r3'):
 for suffix in ('.log','.xml'):copy(name+suffix,'diagnostics/'+name+suffix)
for name in ('run_ui_tests.py','run_gallery_tests.py','verify_frozen.py','verify_artifact.py','archive_focus.py'):copy(name,'harness/'+name)
(out/'commands.json').write_text(json.dumps(dict(python='D:/Saydraft-Codex-QA-20261112-01a1cbc7/app-ui-v2-package-20261116-r1/venv/Scripts/python.exe',cwd=str(repo),tests=[['run_ui_tests.py','focus-theme-final','tests/test_theme.py','-x','-vv'],['run_ui_tests.py','keyboard-integration','tests/test_hub_accessibility.py','-k','keyboard or navigation or tab','-x','-vv'],['run_gallery_tests.py']],other=[['node','tools/generate_tokens.mjs','--check'],['python','-m','ruff','check','saydraft','tests']],source='b6322666fc1cee11c06492ab493d9e4d74b3511b'),indent=2)+'\n',encoding='utf-8')
build=qa.parent/'focus-presentation-package-20261116-r1'
if (qa/'artifact-verification.json').is_file():
 for name in ('build.log','artifact-verification.json','artifact-verification.log','frozen-verification.json','frozen-verification.log','frozen-verification.guard.json'):copy(name,'packaging/'+name)
 for name in ('bundle.json','preflight.json','runtime.json','requirements-frozen.txt'):
  dest=out/'packaging'/name;shutil.copyfile(build/'audit'/name,dest)
manifest=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json']
(out/'manifest.json').write_text(json.dumps(dict(source='b6322666fc1cee11c06492ab493d9e4d74b3511b',files=manifest),indent=2)+'\n',encoding='utf-8')
print('Archived',len(manifest),'evidence files')
