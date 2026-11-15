"""Public runtime provenance for owned replay measurements; no device imports."""

from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import platform
import sys
from pathlib import Path

PACKAGES = ('numpy', 'soundfile', 'webrtcvad-wheels', 'faster-whisper', 'ctranslate2',
            'sherpa-onnx', 'sherpa-onnx-core', 'onnxruntime')


def require_runtime_versions(environment, tier):
    required = {'numpy', 'soundfile', 'webrtcvad-wheels'}
    required.update({'faster-whisper', 'ctranslate2'} if tier == 'lite'
                    else {'sherpa-onnx', 'sherpa-onnx-core', 'onnxruntime'})
    if any(not environment.get('packages', {}).get(name) for name in required):
        raise ValueError('Required replay dependency version is unavailable')


def runtime_environment():
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {'python': platform.python_version(), 'implementation': sys.implementation.name,
            'cache_tag': sys.implementation.cache_tag, 'architecture': platform.machine(),
            'interpreter_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            'packages': packages}
