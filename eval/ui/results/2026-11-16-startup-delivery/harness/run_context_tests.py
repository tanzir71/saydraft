import os,sys,json,atexit
from pathlib import Path
repo=Path('C:/Users/tanzir/Desktop/voice_tray');sys.path.insert(0,str(repo))
os.environ.update(QT_QPA_PLATFORM='offscreen',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONNOUSERSITE='1',PYTHONIOENCODING='utf-8')
qa=Path(__file__).resolve().parent;run=sys.argv[1]
from tools.public_file_guard import install
install(qa/(run+'.guard.json'))
for finder in sys.meta_path:
 if type(finder).__name__=='OwnerIOGuard':
  original=finder.find_spec
  finder.find_spec=lambda fullname,path=None,target=None,original=original:None if fullname in ('saydraft.context.foreground','saydraft.context.uia_native','saydraft.insert.clipboard_win') else original(fullname,path,target)
sys.path.append('C:/Users/tanzir/AppData/Roaming/Python/Python313/site-packages')
import pytest
raise SystemExit(pytest.main(sys.argv[2:]+['-q','--tb=short','--basetemp='+str(qa/(run+'-temp')),'--junitxml='+str(qa/(run+'.xml'))]))
