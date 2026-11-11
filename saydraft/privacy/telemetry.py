"""Disable runtime telemetry before loading local models."""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from pathlib import Path

_lock = threading.Lock()
_environments = {}


def configure_process_privacy():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"


def disable_python_onnx_telemetry():
    configure_process_privacy()
    try:
        import onnxruntime
    except ImportError:
        return
    onnxruntime.disable_telemetry_events()


def disable_sherpa_telemetry(sherpa_module):
    """Configure sherpa's own shared ORT library via the stable public C API v1.

    Its Python binding does not expose this setting. Retain the disabled singleton
    environment for the process lifetime, before creating any model sessions.
    The first seven OrtApi entries are defined by the public version-1 ABI.
    """
    configure_process_privacy()
    directory = Path(sherpa_module.__file__).parent / "lib"
    pattern = "onnxruntime.dll" if sys.platform == "win32" else "libonnxruntime.*"
    paths = sorted(directory.glob(pattern))
    if not paths:
        raise RuntimeError("Cannot configure the local runtime's telemetry policy")
    path = paths[0].resolve()
    with _lock:
        if str(path) in _environments:
            return
        library = ctypes.WinDLL(str(path)) if sys.platform == "win32" else ctypes.CDLL(str(path))
        function = ctypes.WINFUNCTYPE if sys.platform == "win32" else ctypes.CFUNCTYPE

        class ApiBase(ctypes.Structure):
            _fields_ = [("get_api", function(ctypes.c_void_p, ctypes.c_uint32)),
                        ("version", function(ctypes.c_char_p))]

        class ApiPrefix(ctypes.Structure):
            _fields_ = [(name, ctypes.c_void_p) for name in (
                "create_status", "error_code", "error_message", "create_env",
                "create_env_with_logger", "enable_telemetry", "disable_telemetry")]

        library.OrtGetApiBase.restype = ctypes.POINTER(ApiBase)
        api_pointer = library.OrtGetApiBase().contents.get_api(1)
        if not api_pointer:
            raise RuntimeError("Local runtime does not support the required privacy API")
        api = ctypes.cast(api_pointer, ctypes.POINTER(ApiPrefix)).contents
        create = function(ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p,
                          ctypes.POINTER(ctypes.c_void_p))(api.create_env)
        disable = function(ctypes.c_void_p, ctypes.c_void_p)(api.disable_telemetry)
        environment = ctypes.c_void_p()
        if create(3, b"Saydraft", ctypes.byref(environment)) or not environment:
            raise RuntimeError("Could not initialize the private local runtime")
        if disable(environment):
            raise RuntimeError("Could not disable local runtime telemetry")
        _environments[str(path)] = (library, environment)
