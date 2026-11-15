import os,sys,faulthandler
faulthandler.dump_traceback_later(45,repeat=False)
print("starting isolated UI tests", flush=True)
from pathlib import Path
repo=Path('C:/Users/tanzir/Desktop/voice_tray');sys.path.insert(0,str(repo))
os.environ.update(QT_QPA_PLATFORM='offscreen',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONNOUSERSITE='1',PYTHONIOENCODING='utf-8')
from tools.public_worker_guard import install
qa=Path(__file__).resolve().parent
run=sys.argv[1]
install(qa/(run+'.guard.json'))
sys.path.append('C:/Users/tanzir/AppData/Roaming/Python/Python313/site-packages')
import types,atexit,json
for finder in sys.meta_path:
    if type(finder).__name__ == 'OwnerIOGuard':
        original_find = finder.find_spec
        finder.find_spec = lambda fullname,path=None,target=None,original=original_find: None if fullname == 'saydraft.app' else original(fullname,path,target)
logs = types.ModuleType('saydraft.logging_config')
logs.log_file_path = lambda **kwargs: qa/'owned-fixture.log'
sys.modules['saydraft.logging_config'] = logs
stub = types.ModuleType('sounddevice')
attempts = []
def forbidden(*args,**kwargs):
    attempts.append('unconfigured fake audio port')
    raise AssertionError('Only explicitly configured fake audio ports are available')
for name in ('InputStream','query_devices','query_hostapis','WasapiSettings'):
    setattr(stub,name,forbidden)
sys.modules['sounddevice'] = stub
def retire_stub():
    intact = sys.modules.get('sounddevice') is stub
    if intact: del sys.modules['sounddevice']
    (qa/(run+'.stub.json')).write_text(json.dumps(dict(placeholder_only=True,placeholder_intact=intact,real_sdk_module_executed=False,placeholder_retired_before_base_guard=True,unexpected_port_attempts=attempts)),encoding='utf-8')
atexit.register(retire_stub)
import pytest
raise SystemExit(pytest.main(sys.argv[2:]+['-q','--tb=short','--basetemp='+str(qa/(run+'-temp')),'--junitxml='+str(qa/(run+'.xml'))]))
