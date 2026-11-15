"""Fresh-process proof of refusing worker ports, without capture or model use."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import public_worker_guard as guard


def child(tmp_path, code):
    receipt = tmp_path / "owner-io-guard.json"
    result = subprocess.run(
        [sys.executable, "-c", code, str(receipt)],
        cwd=Path(guard.__file__).resolve().parents[1], capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=45,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    return receipt, result


def test_worker_trial_import_uses_only_refusing_foreground_and_immutable_value(tmp_path):
    receipt, result = child(tmp_path, """
import dataclasses,json,os,sys
from tools.public_worker_guard import install
install(sys.argv[1])
import tools.latency_trial
from saydraft.context.foreground import SelectedContext,ForegroundContextProvider
assert ForegroundContextProvider.__module__=='tools.public_worker_guard'
value=SelectedContext()
assert [field.name for field in dataclasses.fields(value)]==['target','selection']
try:value.target=None
except dataclasses.FrozenInstanceError:pass
else:raise AssertionError('Mutable selected context')
print(json.dumps({'pid':os.getpid()}))
""")
    proof = guard.verify_receipts(receipt)
    assert proof["verified"] and proof["actual_python_pid"] == json.loads(result.stdout)["pid"]


def test_owned_native_meter_initializes_without_opening_any_process(tmp_path):
    receipt, _ = child(tmp_path, """
import sys
from tools.public_worker_guard import install
install(sys.argv[1])
from tools.bench_cleanup import NativeMeter
meter=NativeMeter()
assert meter.handles==meter.pids==[]
assert meter.peaks()==meter.finish()==[]
""")
    assert guard.verify_receipts(receipt)["verified"]
    record = json.loads(receipt.read_bytes())
    assert {"caller": "tools.bench_cleanup", "dll": "psapi"} in record["reviewed_dependency_dlls"]


@pytest.mark.parametrize("name", ["psapi", "user32"])
def test_unreviewed_memory_or_owner_ui_dll_is_still_refused(tmp_path, name):
    receipt, _ = child(tmp_path, f"""
import ctypes,sys
from tools.public_worker_guard import install
install(sys.argv[1])
try:ctypes.WinDLL({name!r})
except AssertionError:pass
else:raise AssertionError('Unreviewed native DLL was permitted')
""")
    assert json.loads(receipt.read_bytes())["blocked_attempts"] == ["ctypes.WinDLL:" + name]
    with pytest.raises(ValueError, match="refused qualification"):
        guard.verify_receipts(receipt)


@pytest.mark.parametrize("module", ["sounddevice", "soundcard", "pynput", "pyperclip"])
def test_audio_and_input_sdk_body_is_never_initialized(tmp_path, module):
    receipt, _ = child(tmp_path, f"""
import sys
from tools.public_worker_guard import install
install(sys.argv[1])
try:__import__({module!r})
except AssertionError:pass
else:raise AssertionError('Owner SDK import was permitted')
assert {module!r} not in sys.modules
""")
    assert json.loads(receipt.read_bytes())["blocked_attempts"] == [module]
    with pytest.raises(ValueError, match="refused qualification"):
        guard.verify_receipts(receipt)


def test_inference_runtime_telemetry_disable_uses_only_its_loaded_package_dll(tmp_path):
    receipt, _ = child(tmp_path, """
import sys
from pathlib import Path
from tools.public_worker_guard import install
install(sys.argv[1])
import sherpa_onnx
from saydraft.privacy.telemetry import disable_sherpa_telemetry,_environments
disable_sherpa_telemetry(sherpa_onnx)
expected=str((Path(sherpa_onnx.__file__).parent/'lib/onnxruntime.dll').resolve())
assert expected in _environments
""")
    assert guard.verify_receipts(receipt)["verified"]
    records = json.loads(receipt.read_bytes())["reviewed_dependency_dlls"]
    assert any(row["caller"] == "saydraft.privacy.telemetry"
               and Path(row["dll"]).name == "onnxruntime.dll" for row in records)


@pytest.mark.parametrize("outside_package", [False, True])
def test_telemetry_caller_cannot_load_an_unrelated_native_library(tmp_path, outside_package):
    receipt, _ = child(tmp_path, f"""
import ctypes,sys
from pathlib import Path
from tools.public_worker_guard import install
install(sys.argv[1])
import sherpa_onnx
candidate=str(Path(sys.argv[1]).parent/'onnxruntime.dll') if {outside_package!r} else 'user32'
namespace={{'__name__':'saydraft.privacy.telemetry','ctypes':ctypes,'candidate':candidate}}
try:exec("ctypes.WinDLL(candidate)",namespace)
except AssertionError:pass
else:raise AssertionError('Telemetry caller loaded an unrelated DLL')
""")
    expected = str(receipt.parent / "onnxruntime.dll") if outside_package else "user32"
    assert json.loads(receipt.read_bytes())["blocked_attempts"] == ["ctypes.WinDLL:" + expected]
    with pytest.raises(ValueError, match="refused qualification"):
        guard.verify_receipts(receipt)


def test_gpu_metadata_is_refused_without_explicit_permission(tmp_path):
    receipt, _ = child(tmp_path, """
import sys
from tools.public_worker_guard import install
install(sys.argv[1])
from saydraft.models.windows_hardware import vulkan_devices
try:vulkan_devices()
except AssertionError:pass
else:raise AssertionError('GPU discovery lacked permission')
""")
    assert json.loads(receipt.read_bytes())["blocked_attempts"] == ["ctypes.WinDLL:vulkan-1.dll"]
    with pytest.raises(ValueError):
        guard.verify_receipts(receipt)


def test_explicit_gpu_metadata_permission_keeps_owner_ports_barred(tmp_path):
    receipt, _ = child(tmp_path, """
import sys
from tools.public_worker_guard import install
install(sys.argv[1],allow_gpu_metadata=True)
from saydraft.models.windows_hardware import vulkan_devices
rows=vulkan_devices()
assert isinstance(rows,list) and all('name' in row and 'device_type' in row for row in rows)
""")
    assert guard.verify_receipts(receipt, allow_gpu_metadata=True)["verified"]
    record = json.loads(receipt.read_bytes())
    assert record["gpu_metadata_allowed"] is True and record["gpu_metadata_dlls"]
    assert all(record[name] is False for name in guard.OWNER_FLAGS)
    with pytest.raises(ValueError):
        guard.verify_receipts(receipt)


@pytest.mark.parametrize("name", ["user32", "vulkan-1.dll"])
def test_gpu_permission_does_not_allow_unreviewed_callers_or_owner_ui(tmp_path, name):
    receipt, _ = child(tmp_path, f"""
import ctypes,sys
from tools.public_worker_guard import install
install(sys.argv[1],allow_gpu_metadata=True)
try:ctypes.WinDLL({name!r},winmode=0x800)
except AssertionError:pass
else:raise AssertionError('GPU permission allowed an unrelated native call')
""")
    with pytest.raises(ValueError):
        guard.verify_receipts(receipt, allow_gpu_metadata=True)


def test_gpu_permission_requires_system32_only_loading_even_for_reviewed_caller(tmp_path):
    receipt, _ = child(tmp_path, """
import ctypes,sys
from tools.public_worker_guard import install
install(sys.argv[1],allow_gpu_metadata=True)
namespace={'__name__':'saydraft.models.windows_hardware','ctypes':ctypes}
try:exec("ctypes.WinDLL('vulkan-1.dll')",namespace)
except AssertionError:pass
else:raise AssertionError('GPU driver lookup was not restricted to System32')
""")
    with pytest.raises(ValueError):
        guard.verify_receipts(receipt, allow_gpu_metadata=True)


@pytest.mark.parametrize("name", ["ForegroundContextProvider", "NativeForegroundApi"])
def test_constructing_any_foreground_port_is_refused_and_recorded(tmp_path, name):
    receipt, _ = child(tmp_path, f"""
import sys
from tools.public_worker_guard import install
install(sys.argv[1])
module=sys.modules['saydraft.context.foreground']
try:getattr(module,{name!r})()
except AssertionError:pass
else:raise AssertionError('Native context construction was permitted')
""")
    fixture = json.loads(guard.fixture_receipt_path(receipt).read_bytes())
    assert fixture["port_attempts"] == ["foreground_adapter_construction"]
    with pytest.raises(ValueError):
        guard.verify_receipts(receipt)


@pytest.mark.parametrize("drift", [*guard.OWNER_FLAGS, "blocked", "native_port", "pid", "bool_pid", "kind", "missing"])
def test_missing_or_unsafe_terminal_receipt_never_qualifies(tmp_path, drift):
    receipt = tmp_path / "guard.json"
    record = {"pid": 1234, "blocked_attempts": [], **dict.fromkeys(guard.OWNER_FLAGS, False)}
    fixture = {"pid": 1234, "kind": guard.KIND, "port_attempts": [],
               "production_context_adapter_loaded": False, "selection_value_fields": ["target", "selection"]}
    if drift in guard.OWNER_FLAGS:
        record[drift] = True
    elif drift == "blocked":
        record["blocked_attempts"].append("sounddevice")
    elif drift == "native_port":
        fixture["port_attempts"].append("foreground_adapter_construction")
    elif drift == "pid":
        fixture["pid"] += 1
    elif drift == "bool_pid":
        record["pid"], fixture["pid"] = 1, True
    elif drift == "kind":
        fixture["kind"] = "unknown-port"
    else:
        record.pop("owner_clipboard_used")
    receipt.write_text(json.dumps(record), encoding="utf-8")
    guard.fixture_receipt_path(receipt).write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(ValueError):
        guard.verify_receipts(receipt)
