import os,sys,json,threading,time,traceback
from pathlib import Path
qa=Path(__file__).resolve().parent
profile=qa/'metadata-profile'
for key,part in [('LOCALAPPDATA','local'),('APPDATA','roaming'),('USERPROFILE','home'),('TEMP','temp'),('TMP','temp')]:
 path=profile/part;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,'C:/Users/tanzir/Desktop/voice_tray')
from saydraft.privacy.netguard import NetworkGuard
NetworkGuard.install()
from PySide6 import QtCore,QtWidgets
app=QtWidgets.QApplication([])
from saydraft.context.uia_native import NativeUIAReader
from saydraft.context.uia_worker import BoundedUIA
import ctypes as ct
from ctypes import wintypes as wt
user=ct.WinDLL('user32');user.GetForegroundWindow.restype=wt.HWND
window=int(user.GetForegroundWindow() or 0)
report=dict(metadata_only=True,text_read=False,clipboard_accessed=False,audio_opened=False,input_injected=False,stages=[],attempts=[])
def forbidden(*args,**kwargs):
 report['attempts'].append('text read');raise AssertionError('metadata only')
for name in ('text_context','text_context_for_request','document_text','selection_range','selection_text','insertion_edges'):
 setattr(NativeUIAReader,name,forbidden)
ready=threading.Event()
def factory():
 try:
  reader=NativeUIAReader();report['initialized']=True
  for name in ('focused_element','belongs','password','fresh_password','control_type','runtime_id','same_focus'):
   original=getattr(reader,name)
   def traced(*args,name=name,original=original,**kwargs):
    started=time.monotonic()
    try:
     result=original(*args,**kwargs)
     record=dict(stage=name,ms=round((time.monotonic()-started)*1000,2),type=type(result).__name__)
     if name in ('belongs','password','fresh_password','same_focus','control_type'):record['value']=result
     if name=='runtime_id':record['length']=len(result)
     report['stages'].append(record);return result
    except Exception as error:
     report['stages'].append(dict(stage=name,error_type=type(error).__name__,hresult=getattr(error,'hresult',None)));raise
   setattr(reader,name,traced)
  return reader
 except Exception as error:
  report.update(initialized=False,error_type=type(error).__name__,hresult=getattr(error,'hresult',None),frames=[dict(file=Path(f.filename).name,function=f.name,line=f.lineno) for f in traceback.extract_tb(error.__traceback__)]);raise
 finally:ready.set()
owner=BoundedUIA(factory=factory,timeout=.5,capture_timeout=.5)
def run():
 ready.wait(15)
 started=time.monotonic();result=owner.query(window,include_text=False)
 report.update(status=result.status,identity_length=len(result.runtime_id),elapsed_ms=round((time.monotonic()-started)*1000,2),window_unchanged=int(user.GetForegroundWindow() or 0)==window)
 owner.close();report['closed']=owner.wait_closed(2)
 (qa/'bounded-metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,indent=2),flush=True)
 QtCore.QMetaObject.invokeMethod(app,'quit',QtCore.Qt.QueuedConnection)
thread=threading.Thread(target=run);thread.start()
QtCore.QTimer.singleShot(20000,app.quit)
app.exec();thread.join(3)
