import sys,os,json,threading,traceback,importlib.abc,importlib.util
from pathlib import Path
qa=Path(__file__).resolve().parent
for env,part in [('LOCALAPPDATA','local'),('APPDATA','roaming'),('USERPROFILE','home'),('TEMP','temp'),('TMP','temp')]:
 path=qa/'archive-profile'/part;path.mkdir(parents=True,exist_ok=True);os.environ[env]=str(path)
from PyInstaller.archive.readers import CArchiveReader
exe=qa.parent/'focus-presentation-package-20261116-r1/dist/Saydraft/Saydraft.exe'
pyz=CArchiveReader(str(exe)).open_embedded_archive('PYZ.pyz')
class Archived(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def find_spec(self,fullname,path=None,target=None):
  if not fullname.startswith('comtypes'):return None
  if fullname not in pyz.toc:raise ModuleNotFoundError(fullname)
  return importlib.util.spec_from_loader(fullname,self,is_package=pyz.toc[fullname][0] in (1,3))
 def create_module(self,spec):return None
 def exec_module(self,module):
  name=module.__name__;module.__file__=str(qa/'archive-runtime'/Path(*name.split('.')).with_suffix('.py'))
  if module.__spec__.submodule_search_locations is not None:module.__path__=[str(qa/'archive-runtime'/Path(*name.split('.')))]
  exec(pyz.extract(name),module.__dict__)
sys.meta_path.insert(0,Archived());sys.frozen=True;sys._MEIPASS=str(exe.parent/'_internal')
sys.path.insert(0,'C:/Users/tanzir/Desktop/voice_tray')
report=dict(initialization_only=True,archived_modules=True,gen_in_archive='comtypes.gen' in pyz.toc,text_read=False,audio_opened=False,clipboard_accessed=False,input_injected=False)
try:
 from saydraft.context.uia_native import NativeUIAReader
 def run():
  reader=None
  try:reader=NativeUIAReader();report['initialized']=True
  except Exception as error:report.update(initialized=False,error_type=type(error).__name__,hresult=getattr(error,'hresult',None),frames=[dict(file=Path(f.filename).name,function=f.name,line=f.lineno) for f in traceback.extract_tb(error.__traceback__)])
  finally:
   if reader is not None:reader.close();report['closed']=True
 thread=threading.Thread(target=run);thread.start();thread.join(15);report['terminal']=not thread.is_alive()
except Exception as error:
 report.update(initialized=False,error_type=type(error).__name__,hresult=getattr(error,'hresult',None),frames=[dict(file=Path(f.filename).name,function=f.name,line=f.lineno) for f in traceback.extract_tb(error.__traceback__)])
(qa/'archived-uia-initialization.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
