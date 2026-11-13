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


def test_hub_runtime_entrypoints_force_cache_only_without_account_credentials(monkeypatch):
    import huggingface_hub
    from saydraft.privacy.telemetry import restrict_hub_to_cache

    calls = []

    def helper(*args, **kwargs):
        calls.append((args, kwargs))
        return 'public cached fixture'

    monkeypatch.setattr(huggingface_hub, 'hf_hub_download', helper)
    monkeypatch.setattr(huggingface_hub, 'snapshot_download', helper)
    restrict_hub_to_cache()
    first = huggingface_hub.hf_hub_download
    restrict_hub_to_cache()
    assert huggingface_hub.hf_hub_download is first
    for name in ('hf_hub_download', 'snapshot_download'):
        assert getattr(huggingface_hub, name)('public/model', local_files_only=False, token=True) == 'public cached fixture'
    assert calls == [(('public/model',), {'local_files_only': True, 'token': False})] * 2
