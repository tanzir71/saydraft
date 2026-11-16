import json,hashlib,shutil
from pathlib import Path
qa=Path(__file__).resolve().parent;repo=Path('C:/Users/tanzir/Desktop/voice_tray')
out=repo/'eval/ui/results/2026-11-16-frozen-delivery';out.mkdir(parents=True,exist_ok=True)
def copy(path,dest):
 target=out/dest;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(qa/path,target)
for run in ('field-final','ui-final','bootstrap-final'):
 data=json.loads((qa/(run+'.guard.json')).read_text('utf-8'));assert data['blocked_attempts']==[]
 for key in ('real_audio_sdk_imported','owner_profile_used','owner_clipboard_used','owner_native_input_used','device_enumeration','microphone_used'):assert data[key] is False
 for suffix in ('.log','.xml','.guard.json','.guard.worker.json','.stub.json'):
  path=qa/(run+suffix)
  if path.exists():
   if suffix=='.guard.worker.json':assert json.loads(path.read_text('utf-8'))['port_attempts']==[]
   if suffix=='.stub.json':assert json.loads(path.read_text('utf-8'))['unexpected_port_attempts']==[]
   copy(path.name,'tests/'+path.name)
for name in ('probe_archived_uia_init.py','probe_bounded_metadata.py','archived-uia-initialization-before.json','archived-uia-initialization.json','bounded-metadata.json','frozen-field-metadata.json'):
 copy(name,'approved-metadata/'+name)
metadata=json.loads((qa/'frozen-field-metadata.json').read_text('utf-8'))
assert metadata['status']=='ok' and metadata['window_unchanged'] and metadata['metadata_only']
assert not any(metadata[k] for k in ('text_read','clipboard_accessed','audio_opened','input_injected'))
copy('brand-icons-final.png','screenshots/brand-icons.png');copy('brand-render-final.guard.json','screenshots/guard.json')
for name in ('run_context_tests.py','run_ui_tests.py','verify_frozen.py','verify_artifact.py','render_brand.py','archive_delivery.py'):copy(name,'harness/'+name)
for name in ('build.log','artifact-verification.json','artifact-verification.log','frozen-verification.json','frozen-verification.log','frozen-verification.guard.json'):copy(name,'packaging/'+name)
build=qa.parent/'delivery-brand-package-20261116-r1'
for name in ('bundle.json','preflight.json','runtime.json','requirements-frozen.txt'):shutil.copyfile(build/'audit'/name,out/'packaging'/name)
runtime=json.loads((build/'audit/runtime.json').read_text('utf-8'));assert runtime['complete'] and runtime['checks']['uia_initialization']
commands=dict(source='12bc27ffdb3ba388ea199e5e51661c968815c2fe',cwd=str(repo),python='D:/Saydraft-Codex-QA-20261112-01a1cbc7/app-ui-v2-package-20261116-r1/venv/Scripts/python.exe',tests=[['run_context_tests.py','field-final','tests/test_uia_startup.py','tests/test_uia_worker.py','tests/test_uia_context.py','tests/test_delivery_context_isolation.py','tests/test_focused_edit.py','tests/test_uia_delivery.py','tests/test_processing.py','tests/test_paste_last.py','-x'],['run_ui_tests.py','ui-final','tests/test_tray_ui.py','tests/test_uia_startup.py','tests/test_qt_app_shell.py','tests/test_package_scaffold.py','-k','not main_initializes_logging_config_and_qt_shell','-x'],['run_context_tests.py','bootstrap-final','tests/test_uia_startup.py','-x']],native=['probe_archived_uia_init.py','probe_bounded_metadata.py','Saydraft.exe --verify-field-metadata <fresh QA output.json>'],build=['tools/build.ps1','-Python','C:/Python313/python.exe','-OutputRoot',str(build),'-PipCache',str(qa.parent/'pip-cache'),'-SkipInstaller'])
(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf-8')
rows=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json']
(out/'manifest.json').write_text(json.dumps(dict(source=commands['source'],files=rows),indent=2)+'\n',encoding='utf-8')
print('Archived',len(rows),'files')
