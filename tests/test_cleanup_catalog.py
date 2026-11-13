"""Pinned cleanup setup preserves versions and exposes no implicit downloads."""

import copy
import hashlib
import io
import json
import threading
from pathlib import Path
from urllib.error import URLError

import pytest

from saydraft.model_download import model_relative_dir
from saydraft.models.cleanup import cleanup_bundle, download_cleanup_model, recommend_cleanup, transfer_bytes
from saydraft.models.downloader import DownloadPaused, _receipt, download_model, installation_ready
from saydraft.models.manifest import bundled_license_path, get_model, load_manifest
from saydraft.privacy.netguard import NetworkGuard


@pytest.fixture(autouse=True)
def reset_network():
    yield
    NetworkGuard.uninstall()


def test_app_catalog_matches_measured_pins_and_bundles_notices_without_developer_files():
    defaults = load_manifest()["cleanup_defaults"]
    candidates = json.loads(Path("eval/cleanup/candidates.json").read_text())["models"]
    assert defaults == {"lite": None, "standard": "qwen35-08b-q4-k-m", "pro": "qwen35-2b-q4-k-m"}
    for model_id in (defaults["standard"], defaults["pro"]):
        model = get_model(model_id)
        candidate = next(row for row in candidates if row["id"] == model_id)
        assert model["role"] == "llm" and model["license"] == "Apache-2.0"
        assert model["revision"] == candidate["revision"] and model["files"][:2] == candidate["files"]
        notice = model["files"][-1]
        assert notice["path"] == "LICENSE.txt" and "url" not in notice
        raw = bundled_license_path(notice["bundled_source"]).read_bytes()
        assert len(raw) == notice["size"] and hashlib.sha256(raw).hexdigest() == notice["sha256"]
        assert model_relative_dir(model) == Path(model_id) / model["version"]
        for backend in ("cpu", "vulkan"):
            package = cleanup_bundle(model_id, backend)
            assert package[0] == model and package[1]["backend"] == backend
            assert transfer_bytes(package[1]) == package[1]["archive"]["size"]


@pytest.mark.parametrize("tier,expected", [("pending", None), ("lite", None),
    ("standard", "qwen35-08b-q4-k-m"), ("pro", "qwen35-2b-q4-k-m")])
def test_recommendation_uses_recorded_tier_and_does_not_enable_or_install(tier, expected):
    report = {"assessment": {"tier": tier}, "vulkan": [{"name": "verified GPU"}]}
    before = copy.deepcopy(report)
    result = recommend_cleanup(report)
    assert result["model_id"] == expected and report == before
    assert result["backend"] == ("vulkan" if expected else "cpu")
    assert recommend_cleanup(None) == {"tier": "pending", "model_id": None, "backend": "cpu"}


@pytest.mark.parametrize("value", ["../LICENSE", "assets/licenses/../other.txt", "C:/secret", "assets/private.txt"])
def test_bundled_notices_cannot_escape_license_resources(value):
    with pytest.raises(ValueError):
        bundled_license_path(value)


@pytest.fixture
def setup_package(tmp_path, monkeypatch):
    model = copy.deepcopy(get_model("qwen35-08b-q4-k-m"))
    payload = b"small pinned GGUF fixture"
    model["files"] = [{"path": "test.gguf", "url": "https://models.example/pin/test.gguf",
        "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}, model["files"][-1]]
    model["download_hosts"] = ["models.example"]
    runtime = {"id": "test-runtime", "role": "runtime", "engine": "llama_cpp", "revision": "runtime-v1",
        "files": [{"path": "server.exe", "url": "https://models.example/server", "size": 7,
                   "sha256": hashlib.sha256(b"runtime").hexdigest()}]}
    calls, runtime_calls = [], []
    failed = threading.Event()
    def opener(request, **kwargs):
        calls.append(request.full_url)
        if failed.is_set():
            raise URLError("interrupted test transfer")
        response = io.BytesIO(payload)
        response.status = 200
        response.headers = {}
        return response
    def installer(runtime_model, target, **kwargs):
        runtime_calls.append(target)
        assert runtime_model == runtime
        if not installation_ready(runtime_model, target, check_hashes=True):
            target.mkdir(parents=True, exist_ok=True)
            (target / "server.exe").write_bytes(b"runtime")
            (target / ".verified.json").write_text(json.dumps(_receipt(runtime_model)))
        return target
    monkeypatch.setattr("saydraft.models.cleanup.cleanup_bundle", lambda *args: [model, runtime])
    monkeypatch.setattr("saydraft.models.downloader.download_model", lambda *args, **kwargs:
                        download_model(*args, opener=opener, **kwargs))
    monkeypatch.setattr("saydraft.models.packages.install_archive", installer)
    return model, runtime, calls, runtime_calls, failed


def test_explicit_model_runtime_install_is_atomic_cached_and_preserves_old_versions(tmp_path, setup_package):
    model, runtime, calls, runtime_calls, _ = setup_package
    old = tmp_path / "llm" / model["id"] / "older-version"
    old.mkdir(parents=True)
    (old / "keep.txt").write_text("owner data")
    target = tmp_path / model_relative_dir(model)
    progress = []
    path = download_cleanup_model(model["id"], "cpu", models_dir=tmp_path, progress_callback=progress.append)
    assert path == target / "test.gguf" and installation_ready(model, target, check_hashes=True)
    assert installation_ready(runtime, runtime_calls[-1], check_hashes=True)
    assert calls == [model["files"][0]["url"]] and progress[-1] == 100
    assert (old / "keep.txt").read_text() == "owner data"
    download_cleanup_model(model["id"], "cpu", models_dir=tmp_path)
    assert len(calls) == 1
    (target / "test.gguf").write_bytes(b"changed")
    (target / "owner.txt").write_text("retained")
    download_cleanup_model(model["id"], "cpu", models_dir=tmp_path)
    assert installation_ready(model, target, check_hashes=True)
    archived = list((target.parent / "_archive").glob("*/owner.txt"))
    assert len(archived) == 1 and archived[0].read_text() == "retained"


def test_interruption_keeps_staging_and_never_publishes_or_installs_runtime(tmp_path, setup_package):
    model, _, calls, runtime_calls, failed = setup_package
    failed.set()
    target = tmp_path / model_relative_dir(model)
    with pytest.raises(URLError):
        download_cleanup_model(model["id"], "cpu", models_dir=tmp_path)
    assert not target.exists() and not runtime_calls and calls
    assert target.with_name(target.name + ".download").is_dir()
    failed.clear()
    assert download_cleanup_model(model["id"], "cpu", models_dir=tmp_path).is_file()


def test_pause_before_setup_never_changes_disk_or_starts_network(tmp_path, setup_package):
    _, _, calls, runtime_calls, _ = setup_package
    pause = threading.Event()
    pause.set()
    with pytest.raises(DownloadPaused):
        download_cleanup_model("selected", "cpu", models_dir=tmp_path, pause_event=pause)
    assert not calls and not runtime_calls and not list(tmp_path.iterdir())


def test_wrong_bundled_notice_checksum_refuses_before_any_weight_transfer(tmp_path, setup_package):
    model, _, calls, runtime_calls, _ = setup_package
    model["files"][-1]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="notice"):
        download_cleanup_model(model["id"], "cpu", models_dir=tmp_path)
    assert not calls and not runtime_calls
