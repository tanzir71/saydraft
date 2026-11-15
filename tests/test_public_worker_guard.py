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
