import os,sys
from pathlib import Path
repo=Path('C:/Users/tanzir/Desktop/voice_tray');sys.path.insert(0,str(repo))
os.environ.update(QT_QPA_PLATFORM='offscreen',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONNOUSERSITE='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
qa=Path(__file__).resolve().parent;run=sys.argv[1]
from tools.public_file_guard import install
install(qa/(run+'.guard.json'))
sys.path.append('C:/Users/tanzir/AppData/Roaming/Python/Python313/site-packages')
if sys.argv[2]=='check':
 from tools.check_cleanup_evidence import main
 raise SystemExit(main(sys.argv[3:]))
import pytest
raise SystemExit(pytest.main(sys.argv[2:]+['-q','--tb=short','--basetemp='+str(qa/(run+'-temp')),'--junitxml='+str(qa/(run+'.xml'))]))
