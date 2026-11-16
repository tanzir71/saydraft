"""Explicit owner approval: one focused-field metadata check, never text or input."""
import json,os,sys,threading,time
from pathlib import Path
qa=Path(__file__).resolve().parent
for env,part in [('LOCALAPPDATA','local'),('APPDATA','roaming'),('USERPROFILE','home'),('TEMP','temp'),('TMP','temp')]:
 folder=qa/'field-profile'/part;folder.mkdir(parents=True,exist_ok=True);os.environ[env]=str(folder)
sys.path.insert(0,'C:/Users/tanzir/Desktop/voice_tray')
from saydraft.context.uia_native import NativeUIAReader
from saydraft.context.foreground import NativeForegroundApi
from saydraft.context.focused_edit import read_focused_edit
attempts=[]
def forbidden(*args,**kwargs):attempts.append('text/content access');raise AssertionError('Metadata only')
for name in ('text_context','text_context_for_request','document_text','insertion_edges','selection_range','refresh_element'):
 setattr(NativeUIAReader,name,forbidden)
report=dict(metadata_only=True,text_read=False,clipboard_accessed=False,audio_opened=False,input_injected=False,attempts=attempts)
def run():
 reader=None;stage='initialize'
 try:
  reader=NativeUIAReader();api=NativeForegroundApi()
  window=api.foreground();pid=api.window_pid(window)
  report['app']=api.executable(pid)
  stage='focused_element';start=time.monotonic();element=reader.focused_element()
  report['focused_query_ms']=round((time.monotonic()-start)*1000,2)
  def record(name,action):
   start=time.monotonic()
   try:
    value=action();report[name]=dict(type=type(value).__name__,value=value if type(value) in (bool,int,str) else None,ms=round((time.monotonic()-start)*1000,2))
    return value
   except Exception as error:report[name]=dict(error_type=type(error).__name__,hresult=getattr(error,'hresult',None));return None
  record('belongs',lambda:reader.belongs(element,window))
  record('cached_password',lambda:reader.password(element))
  record('live_password',lambda:reader.fresh_password(element))
  record('keyboard_focus',lambda:reader.keyboard_focus(element))
  record('control_type',lambda:reader.control_type(element))
  runtime=record('identity_length',lambda:len(reader.runtime_id(element)))
  reader.focused_element=lambda:element
  report['policy_status']=read_focused_edit(reader,int(window),include_text=False,current=lambda:api.foreground()==window).status
  report['window_unchanged']=api.foreground()==window
 except Exception as error:report.update(stage=stage,error_type=type(error).__name__,hresult=getattr(error,'hresult',None))
 finally:
  if reader is not None:reader.close()
t=threading.Thread(target=run,daemon=True);t.start();t.join(15)
report['terminal']=not t.is_alive()
(qa/'field-metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['terminal'] and not attempts else 1)
