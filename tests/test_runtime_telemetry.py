import sys
from types import SimpleNamespace

from saydraft.privacy.telemetry import configure_process_privacy, disable_python_onnx_telemetry


def test_process_privacy_overrides_opt_in_environment_flags(monkeypatch):
    for name in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.setenv(name, "0")
    configure_process_privacy()
    import os

    assert all(os.environ[name] == "1" for name in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"))


def test_python_onnx_telemetry_is_disabled_before_model_use(monkeypatch):
    called = []
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(disable_telemetry_events=lambda: called.append("disabled")))
    disable_python_onnx_telemetry()
    assert called == ["disabled"]
