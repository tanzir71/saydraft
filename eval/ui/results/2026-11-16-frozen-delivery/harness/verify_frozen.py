"""Read/hash frozen code and resources without executing application modules."""
import argparse,hashlib,importlib.util,json,subprocess,sys,types
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--build',type=Path,required=True)
p.add_argument('--source',required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.repo))
from tools.public_file_guard import install
install(a.output.with_suffix('.guard.json'))
spec=importlib.util.find_spec('PyInstaller')
package=types.ModuleType('PyInstaller');package.__path__=[str(Path(spec.origin).parent)];package.__spec__=spec
sys.modules['PyInstaller']=package
from PyInstaller.archive.readers import CArchiveReader
audit_path=a.build/'audit/bundle.json'
if not audit_path.exists():audit_path=a.build/'audit/preflight.json'
audit=json.loads(audit_path.read_text(encoding='utf-8-sig'))
assert audit['git_commit']==a.source and audit['source_dirty'] is False
exe=a.build/'dist/Saydraft/Saydraft.exe'
pyz=CArchiveReader(str(exe)).open_embedded_archive('PYZ.pyz')
def stable(v):
 if isinstance(v,types.CodeType):
  fields=['co_argcount','co_posonlyargcount','co_kwonlyargcount','co_nlocals','co_stacksize','co_flags','co_code','co_consts','co_names','co_varnames','co_freevars','co_cellvars','co_firstlineno','co_linetable','co_exceptiontable','co_name','co_qualname']
  return {k:stable(getattr(v,k)) for k in fields}
 if isinstance(v,bytes):return {'bytes':v.hex()}
 if isinstance(v,(tuple,list)):return [stable(i) for i in v]
 if isinstance(v,frozenset):return {'frozenset':sorted([stable(i) for i in v],key=repr)}
 if v is Ellipsis:return {'ellipsis':True}
 return v
def git(path):return subprocess.check_output(['git','show',a.source+':'+path],cwd=a.repo)
def sha(b):return hashlib.sha256(b).hexdigest()
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',a.source,'saydraft/ui'],cwd=a.repo,text=True).splitlines()
paths=[path for path in paths if path.endswith('.py')]
paths+=['saydraft/'+path+'.py' for path in ('app','config','core/worker','core/container','core/microphone','audio/devices','audio/diagnostics','audio/recorder','audio/meter','cleanup/llm/client','cleanup/llm/preparation','cleanup/llm/gate','dictation/types','dictation/llm_local')]
paths+=['saydraft/'+path+'.py' for path in ('context/foreground','asr/selection','asr/router','asr/sherpa_parakeet')]
paths+=['saydraft/'+path+'.py' for path in ('context/uia_native','context/uia_worker','context/uia_startup','package_check','main')]
rows=[];omitted=[]
for path in paths:
 name=path.removesuffix('.py').replace('/','.')
 if name.endswith('.__init__'):name=name.removesuffix('.__init__')
 if name not in pyz.toc:
  omitted.append(name);continue
 payload=git(path)
 expected=json.dumps(stable(compile(payload,path,'exec',dont_inherit=True,optimize=0)),sort_keys=True,separators=(',',':')).encode()
 actual=json.dumps(stable(pyz.extract(name)),sort_keys=True,separators=(',',':')).encode()
 assert expected==actual,name
 rows.append(dict(module=name,source_path=path,source_sha256=sha(payload),code_fingerprint_sha256=sha(actual)))
required={'saydraft.ui.'+s for s in ('kit','theme.controller','theme.style','hub','settings_page','settings_draft','grouped_settings','settings_presentation','home_page','history_page','notes_page','notes_presentation','personalization_presentation','language_tiles','model_choices','model_storage','setup_presentation','setup_content','onboarding','onboarding_practice','onboarding_shortcuts','bar_widget','bar_presentation','icons','fonts','dictionary_toast','tray')}
required.update('saydraft.'+s for s in ('app','config','core.worker','audio.devices','audio.recorder','audio.meter','core.microphone'))
required.update(('saydraft.ui.tray_menu','saydraft.ui.setup_cleanup','saydraft.context.foreground','saydraft.asr.selection','saydraft.asr.router','saydraft.asr.sherpa_parakeet'))
required.update(('saydraft.context.uia_native','saydraft.context.uia_worker','saydraft.context.uia_startup','saydraft.package_check','saydraft.main'))
assert required<={r['module'] for r in rows}
data=a.build/'dist/Saydraft/_internal'
manifest=json.loads((data/'assets/fonts/manifest.json').read_text(encoding='utf-8'))
font_paths={'manifest.json',*(r['path'] for r in manifest['files'])}
assert {p.relative_to(data/'assets/fonts').as_posix() for p in (data/'assets/fonts').rglob('*') if p.is_file()}==font_paths
for r in manifest['files']:
 b=(data/'assets/fonts'/r['path']).read_bytes();assert len(b)==r['size'] and sha(b)==r['sha256']
icons=sorted((data/'assets/icons').glob('*.svg'))
assert len(icons)==52
for path in icons:assert path.read_bytes().replace(b'\r\n',b'\n')==git('assets/icons/'+path.name).replace(b'\r\n',b'\n')
tray_assets=[]
for name in ('mic_idle.ico','mic_recording.ico','mic_processing.ico'):
 payload=(data/'assets/tray'/name).read_bytes()
 assert payload==git('assets/tray/'+name)
 assert int.from_bytes(payload[4:6],'little')==7
 tray_assets.append(dict(name=name,sha256=sha(payload),frames=7))
assert (data/'docs/HOTKEYS.md').read_bytes().replace(b'\r\n',b'\n')==git('docs/HOTKEYS.md').replace(b'\r\n',b'\n')
report=dict(source=a.source,bundle=str(exe),exe_sha256=sha(exe.read_bytes()),module_count=len(rows),modules=rows,non_runtime_ui_modules=omitted,font_files=len(font_paths),font_faces=sum(r['kind']=='font' for r in manifest['files']),svg_icons=len(icons),hotkey_help_verified=True,module_code_executed=False,owner_io_used=False,method='Compare structural code read from the embedded PYZ with compile(Git source, optimize=0), excluding only filenames; hash exact manifest-listed fonts and inspect every bundled SVG/help file.')
report['tray_assets']=tray_assets
theme_assets=[]
for name in ('tokens.qss','tokens-dark.qss'):
 payload=(data/'saydraft/ui/theme'/name).read_bytes()
 assert payload.replace(b'\r\n',b'\n')==git('saydraft/ui/theme/'+name).replace(b'\r\n',b'\n')
 theme_assets.append(dict(name=name,sha256=sha(payload)))
report['focus_theme_assets']=theme_assets
brand=(data/'assets/tray/saydraft-mark.svg').read_bytes()
assert brand.replace(b'\r\n',b'\n')==git('assets/tray/saydraft-mark.svg').replace(b'\r\n',b'\n')
report['brand_mark_sha256']=sha(brand)
a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('modules','non_runtime_ui_modules')},indent=2))
