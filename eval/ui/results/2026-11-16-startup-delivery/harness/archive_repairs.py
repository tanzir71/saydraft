import hashlib,json,shutil,xml.etree.ElementTree as ET
from pathlib import Path
repo=Path('C:/Users/tanzir/Desktop/voice_tray');qa=Path(__file__).resolve().parent
out=repo/'eval/ui/results/2026-11-16-startup-delivery';out.mkdir(parents=True,exist_ok=True)
def copy(src,dest):
 src=qa/src;dest=out/dest;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
def base_guard(path):
 data=json.loads(path.read_text('utf-8'))
 assert data['blocked_attempts']==[],path
 assert all(data[k] is False for k in ('real_audio_sdk_imported','owner_profile_used','owner_clipboard_used','owner_native_input_used','device_enumeration','microphone_used')),path
runs={}
for name in ('context-final','insertion-r3','worker-r2','hub-r1','repair-final','setup-final-r3'):
 base_guard(qa/(name+'.guard.json'))
 for extra,key in (('.guard.worker.json','port_attempts'),('.stub.json','unexpected_port_attempts')):
  p=qa/(name+extra)
  if p.exists():
   assert json.loads(p.read_text('utf-8'))[key]==[],p
   copy(p.name,'tests/'+p.name)
 for suffix in ('.log','.xml','.guard.json'):copy(name+suffix,'tests/'+name+suffix)
 suites=ET.parse(qa/(name+'.xml')).getroot().findall('testsuite')
 assert all(int(s.get('failures',0))==int(s.get('errors',0))==0 for s in suites)
 runs[name]={key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
for name in ('run_ui_tests.py','run_context_tests.py','run_gallery_tests.py','render_repairs.py','update_snapshots.py','verify_frozen.py','verify_artifact.py','snapshot-changes.json'):
 copy(name,'harness/'+name)
for name in ('context-r1','worker-r1','insertion-r1','insertion-r2','setup-final','setup-final-r2'):
 for suffix in ('.log','.xml'):
  if (qa/(name+suffix)).is_file():copy(name+suffix,'diagnostics/'+name+suffix)
for folder in ('repair-renders-r3','repair-renders-r11'):
 for name in ('light-setup-ai.png','dark-setup-ai.png'):copy(folder+'/'+name,'diagnostics/'+folder+'/'+name)
for p in (qa/'repair-renders-accepted').glob('*.png'):copy(p.relative_to(qa),'screenshots/'+p.name)
copy('repair-renders-accepted/report.json','screenshots/report.json')
base_guard(qa/'repair-render-accepted.guard.json');copy('repair-render-accepted.guard.json','screenshots/guard.json')
for scale in (1,2):
 folder=f'gallery-accepted-{scale}x';base_guard(qa/(folder+'.guard.json'))
 copy(folder+'/report.json',f'gallery/{scale}x-report.json');copy(folder+'.guard.json',f'gallery/{scale}x-guard.json')
 for name in ('light-setup-models.png','dark-setup-models.png','light-hub-history.png','dark-hub-history.png','light-hub-settings-models.png','dark-hub-settings-models.png'):
  copy(folder+'/'+name,f'screenshots/{scale}x-'+name)
for name in ('initialize_uia_only.py','check_field_metadata.py','uia-initialization.json','field-metadata.json','field-metadata-saydraft.json','frozen-init/uia-initialization.json'):
 copy(name,'approved-metadata/'+name)
(out/'test-summary.json').write_text(json.dumps(runs,indent=2)+'\n',encoding='utf-8')
print(json.dumps(runs))
