import threading
from dataclasses import replace

import pytest

from saydraft.cleanup.llm.ownership import ProcessSlot, ProcessSlotBusy
from saydraft.cleanup.llm.sidecar import SidecarConfig
from tests import test_sidecar_manager as manager_tests

Process = manager_tests.Process


@pytest.fixture
def rig(tmp_path):
    yield from manager_tests.rig.__wrapped__(tmp_path)


def test_vulkan_startup_passes_the_selected_native_id_and_reuses_the_ready_instance(rig):
    rig.manager.config = replace(rig.manager.config, backend="vulkan")
    calls = []
    rig.manager._device_selector = lambda *a, **kw: (calls.append(kw) or {"id": "Vulkan1", "name": "Fixture GPU"})
    assert rig.manager.prepare() and rig.manager.prepare()
    argv = rig.launches[0][0]
    assert argv[argv.index("--device") + 1] == "Vulkan1" and len(calls) == 1
    assert calls[0]["slot"] is rig.manager._process_slot and calls[0]["cancel"] is rig.manager._closed
    info = rig.manager.selected_device
    info["id"] = "tampered"
    assert rig.manager.selected_device["id"] == "Vulkan1"


@pytest.mark.parametrize("choice", [None, {"id": "Vulkan64"}, {"id": "Vulkan1 --port 80"}])
def test_missing_or_invalid_selection_keeps_model_process_stopped(rig, choice):
    rig.manager.config = replace(rig.manager.config, backend="vulkan")
    rig.manager._device_selector = lambda *a, **kw: choice
    assert not rig.manager.prepare() and not rig.processes
    assert rig.manager.status["reason"] == "gpu_device_unavailable"


def test_cpu_never_discovers_or_initializes_a_gpu(rig):
    rig.manager._device_selector = lambda *a, **kw: pytest.fail("CPU must not probe GPUs")
    assert rig.manager.prepare() and rig.manager.selected_device is None
    assert "--device" not in rig.launches[0][0]


def test_busy_probe_admission_backs_off_without_a_second_model(rig):
    rig.manager.config = replace(rig.manager.config, backend="vulkan")
    def busy(*args, **kwargs):
        raise ProcessSlotBusy("fixture busy")
    rig.manager._device_selector = busy
    assert not rig.manager.prepare() and not rig.processes
    assert rig.manager.status["reason"] == "another_manager_active"


def test_close_during_device_selection_refuses_a_late_server_launch(rig):
    rig.manager.config = replace(rig.manager.config, backend="vulkan")
    entered, release = threading.Event(), threading.Event()
    def select(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return {"id": "Vulkan1"}
    rig.manager._device_selector = select
    results = []
    thread = threading.Thread(target=lambda: results.append(rig.manager.prepare()))
    thread.start()
    try:
        assert entered.wait(1)
        rig.manager.close()
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive() and results == [False] and not rig.processes


def test_probe_lease_excludes_models_and_releases_only_after_exit():
    slot = ProcessSlot()
    probe, model = Process(), Process()
    with slot.start_probe(lambda *a, **kw: probe, [], env={}, capture_output=True) as current:
        assert current is probe and slot.start(lambda *a, **kw: model, [], env={}) is None
        with pytest.raises(ProcessSlotBusy):
            slot.start_probe(lambda *a, **kw: pytest.fail("second probe"), [], env={})
    assert probe.closed and slot.start(lambda *a, **kw: model, [], env={}) is model
    slot.retire(model)


@pytest.mark.parametrize("backend,device", [("cpu", "Vulkan1"), ("vulkan", "Vulkan64"),
    ("vulkan", "Vulkan1 --model bad"), ("vulkan", True)])
def test_invalid_device_configuration_is_rejected_before_launch(tmp_path, backend, device):
    with pytest.raises(ValueError, match="device"):
        SidecarConfig(tmp_path / "model.gguf", backend=backend, device=device)
