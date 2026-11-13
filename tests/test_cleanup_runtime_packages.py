import hashlib
import threading
from pathlib import Path

import pytest

from saydraft.config import default_config
from saydraft.model_download import download_cleanup_runtime
from saydraft.models.manifest import get_model, load_manifest
from saydraft.models.runtime_ids import RUNTIME_MODELS, runtime_model_id


@pytest.mark.parametrize("backend", ["cpu", "vulkan"])
def test_runtime_catalog_keeps_server_dependencies_notices_and_exact_archive_pins(backend):
    model = get_model(runtime_model_id(backend))
    assert model["role"] == "runtime" and model["engine"] == "llama_cpp"
    assert model["cpu_features_required"] == ["avx2"] and model["platform"] == "windows-x64"
    paths = {item["path"] for item in model["files"]}
    assert {"llama-server.exe", "llama-server-impl.dll", "llama-common.dll", "llama.dll", "mtmd.dll",
            "ggml.dll", "ggml-base.dll", "ggml-cpu-haswell.dll", "libomp.dll", "LICENSE-LLVM-OpenMP",
            "LICENSE-llama-cpp.txt"} <= paths
    assert ("ggml-vulkan.dll" in paths) is (backend == "vulkan")
    assert not paths & {"llama-cli.exe", "ggml-rpc.dll", "ggml-rpc-server.exe", "llama-connect.exe"}
    notice = next(item for item in model["files"] if "bundled_source" in item)
    content = Path(notice["bundled_source"]).read_bytes()
    assert len(content) == notice["size"] and hashlib.sha256(content).hexdigest() == notice["sha256"]
    assert "Copyright (c) 2023-2026 The ggml authors" in content.decode()
    assert model["revision"] == f"github-release-asset-{model['archive']['asset_id']}"


@pytest.mark.parametrize("backend", ["cpu", "vulkan"])
def test_cleanup_runtime_download_is_separate_explicit_and_resumable(tmp_path, monkeypatch, backend):
    calls = []
    pause = threading.Event()
    monkeypatch.setattr("saydraft.models.packages.install_archive",
        lambda model, target, **kwargs: calls.append((model, target, kwargs)) or target)
    assert not calls
    target = download_cleanup_runtime(backend, models_dir=tmp_path, pause_event=pause)
    assert target == tmp_path / RUNTIME_MODELS[backend] / get_model(RUNTIME_MODELS[backend])["version"]
    assert len(calls) == 1 and calls[0][2]["pause_event"] is pause


def test_unknown_runtime_backend_cannot_start_a_download(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Unknown backend cannot reach the installer")

    monkeypatch.setattr("saydraft.models.packages.install_archive", unexpected)
    with pytest.raises(ValueError, match="CPU or Vulkan"):
        download_cleanup_runtime("unverified")


def test_runtime_packages_never_appear_as_speech_models():
    from saydraft.ui.model_picker import ModelPicker
    from tests.test_pill_ui import qt_modules

    qt_modules()
    picker = ModelPicker(default_config())
    ids = {picker.combo.itemData(index) for index in range(picker.combo.count())}
    assert not ids & set(RUNTIME_MODELS.values())
    assert all(model["role"] == "runtime" for model in load_manifest()["models"] if model["id"] in RUNTIME_MODELS.values())
