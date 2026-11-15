"""Isolate an owned file-only QA child before importing app or audio packages."""

import atexit
import ctypes
import importlib.abc
import json
import os
from pathlib import Path
import sys
import types


def install(receipt_path):
    if any(name in sys.modules for name in ["soundcard", "sounddevice"]):
        raise ValueError("Start a fresh process before applying the file-only guard")
    receipt_path = Path(receipt_path).resolve()
    if receipt_path.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Keep file-only QA state outside the checkout")
    profile = receipt_path.parent / (receipt_path.stem + "-profile")
    for part in ["local", "roaming", "home", "temp"]:
        (profile / part).mkdir(parents=True, exist_ok=False)
    os.environ.update(
        LOCALAPPDATA=str(profile / "local"),
        APPDATA=str(profile / "roaming"),
        USERPROFILE=str(profile / "home"),
        TEMP=str(profile / "temp"),
        TMP=str(profile / "temp"),
        HF_HOME=str(profile / "home/huggingface"),
        HF_HUB_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        DO_NOT_TRACK="1",
        QT_QPA_PLATFORM="offscreen",
        PYTHONDONTWRITEBYTECODE="1",
    )
    attempts, dependency_dlls = [], []

    class OwnerIOGuard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in [
                "sounddevice",
                "soundcard",
                "pynput",
                "pyperclip",
                "win32clipboard",
            ] or fullname in [
                "saydraft.app",
                "saydraft.logging_config",
                "saydraft.single_instance",
                "saydraft.context.foreground",
                "saydraft.context.uia_native",
                "saydraft.insert.clipboard_win",
            ]:
                attempts.append(fullname)
                raise AssertionError("Owner I/O import is barred: " + fullname)

    sys.meta_path.insert(0, OwnerIOGuard())
    original = getattr(ctypes, "WinDLL", None)
    if original is not None:

        def guarded_dll(name, *args, **kwargs):
            caller = sys._getframe(1).f_globals.get("__name__")
            sherpa_file = getattr(sys.modules.get("sherpa_onnx"), "__file__", None)
            allowed = (
                str(name).lower() in ["kernel32", "kernel32.dll"]
                or (
                    caller == "filelock._windows"
                    and str(name).lower() in ["ntdll", "advapi32"]
                )
                or (
                    caller == "truststore._windows"
                    and str(name).lower() == "crypt32.dll"
                )
                or (
                    # NativeMeter queries memory only through handles obtained
                    # from its own WindowsJobProcess children; no enumeration.
                    caller == "tools.bench_cleanup"
                    and str(name).lower() in ["psapi", "psapi.dll"]
                )
                or (
                    # The production privacy adapter must disable telemetry in
                    # this already-imported package's own inference runtime.
                    caller == "saydraft.privacy.telemetry"
                    and sherpa_file is not None
                    and Path(name).resolve()
                    == (Path(sherpa_file).parent / "lib" / "onnxruntime.dll").resolve()
                )
            )
            if not allowed:
                attempts.append("ctypes.WinDLL:" + str(name))
                raise AssertionError("Owner native UI/device APIs are barred")
            dependency_dlls.append({"caller": caller, "dll": str(name)})
            return original(name, *args, **kwargs)

        ctypes.WinDLL = guarded_dll
    migration = types.ModuleType("saydraft.compat.migrate")
    migration.LEGACY_NAME = "VoiceTray"
    migration.profile_root = lambda: profile / "local"
    sys.modules[migration.__name__] = migration

    def receipt():
        record = {
            "pid": os.getpid(),
            "blocked_attempts": attempts,
            "reviewed_dependency_dlls": dependency_dlls,
            "real_audio_sdk_imported": any(
                name in sys.modules for name in ["soundcard", "sounddevice"]
            ),
            "owner_profile_used": False,
            "owner_clipboard_used": False,
            "owner_native_input_used": False,
            "device_enumeration": False,
            "microphone_used": False,
        }
        receipt_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    atexit.register(receipt)
