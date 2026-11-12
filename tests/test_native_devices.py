import threading

import pytest

from saydraft.models.native_devices import choose_device, parse_devices, probe_devices, select_device
from saydraft.cleanup.llm.ownership import ProcessSlot
from tests.test_sidecar_manager import Process as OwnedProcess

OUTPUT = b"driver initialization\nAvailable devices:\n  Vulkan0: Integrated (32000 MiB, 24000 MiB free)\n  Vulkan1: Discrete (12000 MiB, 11000 MiB free)\n"
WINDOWS = [{"name": "Discrete", "device_type": 2}, {"name": "Integrated", "device_type": 1}]


def test_native_ids_are_matched_by_name_not_windows_order_or_shared_memory_size():
    devices = parse_devices(OUTPUT)
    assert choose_device(devices, WINDOWS)["id"] == "Vulkan1"
    assert choose_device(devices, list(reversed(WINDOWS)))["id"] == "Vulkan1"
    assert choose_device(devices, WINDOWS, required_bytes=16000 * 1024**2)["id"] == "Vulkan0"
    assert choose_device(devices, WINDOWS, required_bytes=32000 * 1024**2) is None


def test_unknown_or_ambiguous_mapping_never_guesses_an_ordinal():
    assert choose_device(parse_devices(OUTPUT), []) is None
    assert choose_device(parse_devices(OUTPUT), [{"name": "Discrete", "device_type": 1},
        {"name": "Discrete", "device_type": 2}]) is None


@pytest.mark.parametrize("output", [b"no header", OUTPUT + b"Available devices:\n", OUTPUT + b"Vulkan2: malformed\n",
    b"Available devices:\n Vulkan0: broken (1 MiB, 2 MiB free)\n",
    OUTPUT + b" Vulkan1: duplicate (2 MiB, 1 MiB free)\n", b"\xff"])
def test_malformed_inventory_is_refused(output):
    with pytest.raises((UnicodeError, ValueError)):
        parse_devices(output)


def test_empty_inventory_is_not_acceleration():
    assert parse_devices(b"Available devices:\n  (none)\n") == []
    assert parse_devices(OUTPUT.replace(b"\n", b"\r\n")) == parse_devices(OUTPUT)
    with pytest.raises(ValueError, match="byte bound"):
        parse_devices(b"x" * 65537)


class Process:
    def __init__(self, argv, **kwargs):
        self.argv, self.kwargs, self.closed = argv, kwargs, False
        self.code = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def poll(self):
        return self.code

    def read_output(self, **kwargs):
        return OUTPUT


def test_probe_verifies_before_launch_and_uses_only_offline_metadata_arguments(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setenv("HF_TOKEN", "fixture secret")
    def spawn(argv, **kwargs):
        process = Process(argv, **kwargs)
        seen.append(process)
        return process
    devices = probe_devices(tmp_path, process_factory=spawn, verify=lambda *a, **kw: True)
    assert devices[1]["id"] == "Vulkan1" and seen[0].closed
    assert seen[0].argv[1:] == ["--offline", "--list-devices"]
    assert seen[0].kwargs["capture_output"] and seen[0].kwargs["max_output_bytes"] == 65536
    assert "HF_TOKEN" not in seen[0].kwargs["env"]
    with pytest.raises(ValueError, match="verification"):
        probe_devices(tmp_path, process_factory=lambda *a, **kw: pytest.fail("unverified launch"),
                      verify=lambda *a, **kw: False)


def test_cancellation_closes_the_owned_probe(tmp_path):
    cancelled, processes = threading.Event(), []
    def spawn(argv, **kwargs):
        process = Process(argv, **kwargs)
        process.code = None
        processes.append(process)
        cancelled.set()
        return process
    with pytest.raises(RuntimeError, match="cancelled"):
        probe_devices(tmp_path, process_factory=spawn, verify=lambda *a, **kw: True, cancel=cancelled)
    assert processes[0].closed


def test_hung_probe_deadline_closes_it(tmp_path):
    ticks, processes = iter((0, 10)), []
    def spawn(argv, **kwargs):
        process = Process(argv, **kwargs)
        process.code = None
        processes.append(process)
        return process
    with pytest.raises(TimeoutError):
        probe_devices(tmp_path, process_factory=spawn, verify=lambda *a, **kw: True, clock=lambda: next(ticks))
    assert processes[0].closed


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), 31, True])
def test_invalid_probe_budget_does_not_launch(tmp_path, timeout):
    with pytest.raises(ValueError, match="timeout"):
        probe_devices(tmp_path, timeout=timeout, process_factory=lambda *a, **kw: pytest.fail("unexpected launch"))


def test_production_selection_uses_the_slot_and_respects_memory_and_explicit_ids(tmp_path, monkeypatch):
    from saydraft.models import native_devices

    slot, processes = ProcessSlot(), []
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fixture")
    def factory(*args, **kwargs):
        process = OwnedProcess()
        processes.append(process)
        return process
    def inventory(directory, *, process_factory, **kwargs):
        with process_factory([], env={}, capture_output=True) as process:
            assert slot._process is process
            assert slot.start(lambda *a, **kw: pytest.fail("concurrent model"), [], env={}) is None
        return parse_devices(OUTPUT)
    monkeypatch.setattr(native_devices, "probe_devices", inventory)
    options = {"slot": slot, "cancel": threading.Event(), "process_factory": factory, "windows_probe": lambda: WINDOWS}
    assert select_device(tmp_path, model, **options)["id"] == "Vulkan1"
    assert select_device(tmp_path, model, requested="Vulkan0", **options)["id"] == "Vulkan0"
    assert select_device(tmp_path, model, requested="Vulkan9", **options) is None
    assert all(process.closed for process in processes) and slot._process is None
