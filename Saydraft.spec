# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

project = Path(SPECPATH)
datas = collect_data_files('ctranslate2') + [
    (str(project / 'saydraft/models/manifest.json'), 'saydraft/models'),
    (str(project / 'assets'), 'assets'),
    (str(project / 'LICENSE'), '.'),
    (str(project / 'THIRD_PARTY_NOTICES.md'), '.'),
]
a = Analysis(
    [str(project / 'speech_to_text_app.py')],
    pathex=[str(project)],
    binaries=collect_dynamic_libs('ctranslate2'),
    datas=datas,
    hiddenimports=['PySide6.QtSvg'] + collect_submodules('faster_whisper'),
    excludes=['webrtcvad', 'torch', 'transformers', 'sklearn', 'scipy', 'pandas',
              'django', 'PIL', 'pygame', 'yt_dlp'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='Saydraft', debug=False,
    strip=False, upx=True, console=False, icon=str(project / 'assets/tray/mic_idle.ico'),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name='Saydraft')
