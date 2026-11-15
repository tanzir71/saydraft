"""Capture real Qt Hub/Bar controls at 2x with isolated public fixtures and barred owner I/O."""
import argparse
from datetime import datetime
import ctypes
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import subprocess
import sys

repo = Path.cwd().resolve()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True, help='Fresh folder outside the source checkout for public fixtures')
output = parser.parse_args().output.resolve()
assert (repo / 'saydraft/__init__.py').is_file(), 'Run from the repository root'
assert not output.is_relative_to(repo), 'Keep generated profiles and captures outside the source checkout'
output.mkdir(exist_ok=False)
profile = output / 'profile'
for name in ['local', 'roaming', 'home', 'temp']: (profile / name).mkdir(parents=True)
os.environ.update(QT_QPA_PLATFORM='offscreen', QT_STYLE_OVERRIDE='Fusion', QT_SCALE_FACTOR='2',
    LOCALAPPDATA=str(profile / 'local'), APPDATA=str(profile / 'roaming'), USERPROFILE=str(profile / 'home'),
    TEMP=str(profile / 'temp'), TMP=str(profile / 'temp'))
sys.path.insert(0, str(repo))
blocked = []
class BarOwnerIO(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ['sounddevice', 'soundcard', 'pynput', 'pyperclip', 'win32clipboard'] or fullname in ['saydraft.app', 'saydraft.insert.clipboard_win']:
            blocked.append(fullname)
            raise AssertionError('Owner I/O module is barred: ' + fullname)
sys.meta_path.insert(0, BarOwnerIO())
def forbidden(*args, **kwargs):
    blocked.append('native/clipboard/device/action')
    raise AssertionError('Owner I/O is barred during offscreen product rendering')
ctypes.WinDLL = forbidden
from PySide6 import QtCore, QtGui, QtWidgets
QtWidgets.QApplication.clipboard = staticmethod(forbidden)
QtGui.QDesktopServices.openUrl = staticmethod(forbidden)
from saydraft.privacy.netguard import NetworkGuard
NetworkGuard.install()
from saydraft.config import default_config, save_config
from saydraft.history import DictationHistoryStore
from saydraft.ui.fonts import install_bundled_fonts
from saydraft.ui.theme import install_theme
from saydraft.ui.hub import HubWindow
import saydraft.ui.settings_page as settings_module
settings_module.wispr_running = lambda: False

class MemoryAutostart:
    def is_enabled(self): return False
    set_enabled = forbidden
class MemoryClipboard:
    copy = read = paste = forbidden

app = QtWidgets.QApplication([])
assert app.platformName() == 'offscreen'
assert len(install_bundled_fonts(app)) == 8
theme = install_theme(app, mode='light')
assert theme is not None
config = default_config()
config['dictation']['glossary_path'] = str(profile / 'glossary.json')
config['dictation']['app_profiles_path'] = str(profile / 'app_profiles.json')
save_config(config, config_path=profile / 'config.json')
store = DictationHistoryStore(profile / 'history.db', import_paths=())
hub = HubWindow(settings_options=dict(config_path=profile / 'config.json', snippets_path=profile / 'snippets.txt',
    autostart_manager=MemoryAutostart(), microphone_devices_provider=forbidden, microphone_start_callback=forbidden,
    firewall_status_provider=forbidden, model_inventory_provider=lambda: []),
    history_options=dict(store=store, clipboard=MemoryClipboard(), glossary_path=profile / 'glossary.json'),
    shortcut=lambda: 'Ctrl+Win', model=lambda: 'Parakeet v3', tier=lambda: 'pending')
hub.home_page.now = lambda: datetime(2026, 11, 15, 9)
hub.settings_page.styles_page.before.setPlainText('um please send the notes actually send the agenda on Tuesday.')
hub.settings_page.styles_page.refresh()
captures = []
for mode in ['light', 'dark']:
    theme.set_mode(mode)
    hub.resize(1080, 760)
    hub.show()
    for page in ['Home', 'Style', 'Dictionary', 'Snippets', 'Notes']:
        hub.show_page(page)
        app.processEvents()
        app.processEvents()
        image = hub.grab()
        name = f'saydraft-hub-{page.lower()}-{mode}-2x.png'
        assert image.width() == 2160 and image.height() == 1520
        assert image.save(str(output / name))
        captures.append({'file': name, 'logical_width': 1080, 'logical_height': 760, 'width': image.width(), 'height': image.height()})
hub.close()
hub.deleteLater()
app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
from saydraft.ui.pill import SaydraftPill
for mode in ['light', 'dark']:
    theme.set_mode(mode)
    for state in ['listening', 'preview', 'cleaning', 'command']:
        ticks = [100.]
        bar = SaydraftPill(clock=lambda: ticks[0], screen_geometry_provider=lambda: QtCore.QRect(0, 0, 1440, 900))
        bar.show_recording(command=state == 'command')
        bar.update_level(.09)
        ticks[0] += .06
        bar.advance_frame()
        if state == 'preview': bar.update_preview('Let us turn this thought into a clear draft.')
        if state == 'cleaning':
            bar.show_processing()
            ticks[0] += 1.75
            bar.advance_frame()
        app.processEvents()
        image = bar.render_image()
        name = f'saydraft-bar-{state}-{mode}-2x.png'
        assert image.width() == bar.width()*2 and image.height() == bar.height()*2
        assert image.save(str(output / name))
        captures.append({'file': name, 'logical_width': bar.width(), 'logical_height': bar.height(), 'width': image.width(), 'height': image.height()})
        bar.hide()
        bar.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
theme.close()
assert not blocked, blocked
for item in captures: item['sha256'] = hashlib.sha256((output / item['file']).read_bytes()).hexdigest()
report = {'app_source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'])),
    'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'platform': app.platformName(), 'scale': 2,
    'network_guard': NetworkGuard.is_installed(), 'owner_profile_used': False, 'owner_clipboard_used': False,
    'audio_devices_enumerated': False, 'audio_sdk_imported': False, 'microphone_used': False, 'active_application_read': False,
    'native_input_used': False, 'blocked_attempts': blocked, 'captures': captures}
(output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'images': len(captures), 'scale': 2, 'platform': app.platformName(), 'blocked_attempts': blocked, 'app_source': report['app_source']}))
