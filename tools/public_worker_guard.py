"""Refusing owner ports for the public-file worker latency fixture only."""

import atexit
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import types

KIND = "public-file-worker-with-refusing-foreground-port"
OWNER_FLAGS = (
    "real_audio_sdk_imported", "owner_profile_used", "owner_clipboard_used",
    "owner_native_input_used", "device_enumeration", "microphone_used",
)


def fixture_receipt_path(receipt):
    return Path(receipt).with_suffix(".worker.json")


def install(receipt):
    """Install before app imports; native foreground construction always raises.

    The existing worker imports two foreground types even with its explicit
    memory context. Supply the immutable value contract and a refusing class.
    This never constructs or queries a native context provider.
    """
    name = "saydraft.context.foreground"
    if name in sys.modules:
        raise ValueError("Start a fresh process before installing worker fixture ports")
    from tools.public_file_guard import install as install_file_guard

    install_file_guard(receipt)
    from saydraft.core.interfaces import TargetContext
    from saydraft.context.selection import SelectionSnapshot
    from saydraft.privacy.netguard import NetworkGuard

    NetworkGuard.install()
    attempts = []

    @dataclass(frozen=True)
    class SelectedContext:
        target: TargetContext = TargetContext()
        selection: SelectionSnapshot = SelectionSnapshot()

    class RefusingForeground:
        def __init__(self, *args, **kwargs):
            attempts.append("foreground_adapter_construction")
            raise AssertionError("Owner foreground/native context is barred")

    fixture = types.ModuleType(name)
    fixture.SelectedContext = SelectedContext
    fixture.ForegroundContextProvider = RefusingForeground
    fixture.NativeForegroundApi = RefusingForeground
    sys.modules[name] = fixture

    def record():
        fixture_receipt_path(receipt).write_text(json.dumps({
            "pid": os.getpid(), "kind": KIND, "port_attempts": attempts,
            "production_context_adapter_loaded": False,
            "selection_value_fields": ["target", "selection"],
        }, indent=2) + "\n", encoding="utf-8")

    atexit.register(record)


def verify_receipts(receipt):
    """Only terminal children with matching refusal receipts can qualify."""
    receipt = Path(receipt)
    fixture_path = fixture_receipt_path(receipt)
    guard = json.loads(receipt.read_text(encoding="utf-8"))
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if (type(guard.get("pid")) is not int or guard["pid"] <= 0
            or type(fixture.get("pid")) is not int or fixture["pid"] != guard["pid"]
            or guard.get("blocked_attempts") != []
            or any(guard.get(name) is not False for name in OWNER_FLAGS)
            or fixture.get("kind") != KIND or fixture.get("port_attempts") != []
            or fixture.get("production_context_adapter_loaded") is not False
            or fixture.get("selection_value_fields") != ["target", "selection"]):
        raise ValueError("Public-file worker guard refused qualification")
    return {
        "verified": True, "actual_python_pid": guard["pid"],
        "guard": {"path": receipt.name, "sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()},
        "fixture": {"path": fixture_path.name, "sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest()},
    }
