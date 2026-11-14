"""Explicit frozen-resource verification without starting dictation services."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import socket
import sys
from pathlib import Path


def verify_runtime():
    from . import __version__
    from .privacy.netguard import NetworkBlockedError, NetworkGuard
    from .privacy.telemetry import configure_process_privacy, disable_python_onnx_telemetry, disable_sherpa_telemetry

    result = {"version": __version__, "frozen": bool(getattr(sys, "frozen", False)),
        "microphone_used": False, "audio_devices_enumerated": False, "input_injected": False,
        "owner_clipboard_accessed": False, "active_application_read": False,
        "asr_performed": False, "native_firewall_verified": False, "checks": {}, "complete": False}
    NetworkGuard.install()
    configure_process_privacy()
    try:
        root = Path(__file__).resolve().parents[1]
        from .models.manifest import load_manifest
        from .ui.fonts import verify_font_assets
        from .ui.tray import default_tray_assets
        from .dictionary.frequency import common_words
        from .cleanup.llm.prompts import PromptHints, build_messages

        load_manifest()
        verify_font_assets()
        if not common_words('en') or not build_messages('Ready', hints=PromptHints(post_rules=True)):
            raise ValueError('Bundled dictionary or cleanup resources are unavailable')
        for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'bundle-policy.json', 'assets/audio/benchmark.wav'):
            if not (root / name).is_file():
                raise ValueError('Bundled resource missing')
        result['checks']['resources'] = True
        from .third_party import verify_notices

        result['third_party_notices'] = verify_notices(root / 'third_party_licenses')
        result['checks']['third_party_notices'] = True
        for name in ('numpy', 'soundfile', 'ctranslate2', 'faster_whisper', 'sherpa_onnx',
                     'webrtcvad', 'comtypes.client', 'PySide6.QtWidgets', 'PySide6.QtSvg', 'PySide6.QtMultimedia'):
            result['stage'] = 'import:' + name
            importlib.import_module(name)
        disable_python_onnx_telemetry()
        disable_sherpa_telemetry(importlib.import_module('sherpa_onnx'))
        # Importing sounddevice initializes PortAudio. Check its frozen module and
        # library presence without importing it or asking PortAudio about devices.
        if importlib.util.find_spec('sounddevice') is None or not any(root.rglob('*portaudio*.dll')):
            raise ValueError('Capture runtime missing')
        result['checks']['native_imports'] = True
        # SoundCard's CFFI declarations are read at import. Verify the frozen
        # module and header without initializing COM or querying audio endpoints.
        if (importlib.util.find_spec('soundcard') is None
                or not (root / 'soundcard/mediafoundation.py.h').is_file()):
            raise ValueError('Meeting capture CFFI resources missing')
        result['checks']['meeting_capture_resources'] = True
        from .stt.whisper_engine import WhisperEngineConfig

        if WhisperEngineConfig().vad_filter:
            raise ValueError('App requires an undeclared built-in Whisper VAD model')
        result['stage'] = 'tray_images'
        from PySide6 import QtGui

        assets = default_tray_assets()
        if any(QtGui.QImage(str(path)).isNull() for path in assets.as_dict().values()):
            raise ValueError('Frozen tray image cannot load')
        result['checks']['tray_images'] = True
        try:
            socket.create_connection(('203.0.113.1', 443), timeout=.01)
        except NetworkBlockedError:
            result['checks']['python_network_guard'] = True
        else:
            raise ValueError('Python network guard unavailable')
        policy = json.loads((root / 'bundle-policy.json').read_text(encoding='utf-8'))
        if any(name.casefold() == prefix.casefold() or name.casefold().startswith(prefix.casefold() + '.') for name in sys.modules
               for prefix in policy['forbidden_modules']):
            raise ValueError('Forbidden runtime module loaded')
        result['checks']['forbidden_modules_absent'] = True
        if 'sounddevice' in sys.modules:
            result['audio_devices_enumerated'] = None
            raise ValueError('Audio runtime initialized during package verification')
        result['complete'] = result['frozen'] and all(result['checks'].values())
        result['stage'] = 'complete'
    except Exception as exc:
        result['error_type'] = type(exc).__name__
    finally:
        NetworkGuard.uninstall()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path, help='new metadata report filename')
    parser.add_argument('--firewall-smoke', type=Path, help='disposable CI only: pinned local Whisper base fixture')
    args = parser.parse_args(argv)
    if args.report.exists():
        parser.error('report exists; choose a fresh filename')
    if args.firewall_smoke:
        from .privacy.firewall_verification import frozen_smoke
        result = frozen_smoke(args.firewall_smoke, args.report.parent)
    else:
        result = verify_runtime()
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
