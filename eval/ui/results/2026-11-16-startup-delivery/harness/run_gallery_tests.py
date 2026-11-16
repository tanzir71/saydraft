import os,sys
from pathlib import Path
repo=Path('C:/Users/tanzir/Desktop/voice_tray');sys.path.insert(0,str(repo))
os.environ.update(QT_QPA_PLATFORM='offscreen',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONNOUSERSITE='1')
sys.path.append('C:/Users/tanzir/AppData/Roaming/Python/Python313/site-packages')
import pytest
qa=Path(__file__).resolve().parent
raise SystemExit(pytest.main(['tests/test_gallery.py','-q','--tb=short','--basetemp='+str(qa/'gallery-tests-temp'),'--junitxml='+str(qa/'gallery-tests.xml')]))
