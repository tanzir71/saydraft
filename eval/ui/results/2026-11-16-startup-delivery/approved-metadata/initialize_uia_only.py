"""Owner-authorized initialization only; never request an element or foreground."""
import json,os,sys,threading,traceback
from pathlib import Path
qa=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent
qa.mkdir(parents=True,exist_ok=True)
profile=qa/'init-profile'
for env,part in [('LOCALAPPDATA','local'),('APPDATA','roaming'),('USERPROFILE','home'),('TEMP','temp'),('TMP','temp')]:
 folder=profile/part;folder.mkdir(parents=True,exist_ok=True);os.environ[env]=str(folder)
if not getattr(sys,'frozen',False):sys.path.insert(0,'C:/Users/tanzir/Desktop/voice_tray')
from saydraft.context.uia_native import NativeUIAReader
attempts=[]
def forbidden(*args,**kwargs):
 attempts.append('element/content/native-input access');raise AssertionError('Initialization only')
for name in ('focused_element','belongs','same_focus','password','fresh_password','text_context','text_context_for_request','runtime_id','keyboard_focus','refresh_element','document_text','insertion_edges'):
 setattr(NativeUIAReader,name,forbidden)
report=dict(initialization_only=True,foreground_read=False,field_content_read=False,audio_opened=False,clipboard_accessed=False,input_injected=False,attempts=attempts)
def run():
 reader=None
 try:
  reader=NativeUIAReader();report['initialized']=True
 except Exception as error:
  trace=traceback.extract_tb(error.__traceback__)
  report.update(initialized=False,error_type=type(error).__name__,hresult=getattr(error,'hresult',None),frames=[dict(file=Path(f.filename).name,function=f.name,line=f.lineno) for f in trace])
 finally:
  if reader is not None:reader.close();report['closed']=True
t=threading.Thread(target=run,daemon=True);t.start();t.join(20)
report['terminal']=not t.is_alive()
(qa/'uia-initialization.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(0 if report.get('initialized') and report['terminal'] and not attempts else 1)
