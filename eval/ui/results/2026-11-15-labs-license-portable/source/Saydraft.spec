# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import json
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

project = Path(SPECPATH)
sys.path.insert(0, str(project))
from tools.package_notices import collect_notices
policy = json.loads((project / 'installer/bundle-policy.json').read_text(encoding='utf-8'))
datas = collect_data_files('ctranslate2') + collect_data_files('saydraft.cleanup.llm.prompts') + collect_data_files('saydraft.ui.theme') + collect_data_files('saydraft.ui.sound_assets') + [
    (str(project / 'saydraft/models/manifest.json'), 'saydraft/models'),
    *[(str(project / 'assets' / name), 'assets/' + name) for name in policy['asset_directories']],
    (str(project / 'installer/bundle-policy.json'), '.'),
    (str(project / 'LICENSE'), '.'),
    (str(project / 'THIRD_PARTY_NOTICES.md'), '.'),
]
a = Analysis(
    [str(project / 'installer/entry.py')],
    pathex=[str(project)],
    binaries=collect_dynamic_libs('ctranslate2') + collect_dynamic_libs('sherpa_onnx'),
    datas=datas,
    hiddenimports=['PySide6.QtSvg', '_webrtcvad'] + collect_submodules('faster_whisper') + collect_submodules('sherpa_onnx'),
    excludes=policy['excluded_modules'],
    hookspath=[str(project / 'installer/hooks')],
    noarchive=False,
    optimize=0,
)
# The app uses its pinned, explicitly installed VAD bundle. Do not silently ship
# faster-whisper's additional model through a package-data collection hook.
a.datas = [item for item in a.datas if not item[0].lower().endswith('.onnx')]
a.datas += collect_notices([*a.pure, *a.binaries], os.environ['SAYDRAFT_NOTICE_OUTPUT'], project,
                          compiler=os.environ.get('SAYDRAFT_INNO_COMPILER'))
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='Saydraft', debug=False,
    strip=False, upx=False, console=False, icon=str(project / 'assets/tray/mic_idle.ico'),
    version=os.environ.get('SAYDRAFT_VERSION_FILE'),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Saydraft')
