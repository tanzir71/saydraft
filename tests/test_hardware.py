import json
import os

import pytest

from saydraft.models.hardware import assess_tier, latest_report, probe_hardware, save_report
from saydraft.privacy.netguard import NetworkGuard


@pytest.mark.parametrize("ram,asr,small,big,gpu,tier,reason", [
    (7, 0.5, 50, 60, True, "lite", "ram_below_8_gib"),
    (16, 1.21, 50, 60, True, "lite", "asr_over_budget"),
    (16, 1.2, 25, None, False, "standard", "llm_08b_measured"),
    (16, 1.2, 24.9, None, False, "lite", "cleanup_below_budget"),
    (16, 0.8, None, 40, False, "pro", "llm_2b_measured"),
    (16, 0.8, None, None, True, "pro", "gpu_available"),
    (16, 0.8, None, None, False, "pending", "cleanup_benchmark_missing"),
    (16, None, None, None, True, "pending", "benchmark_incomplete"),
    (None, 0.8, 30, 40, True, "pending", "benchmark_incomplete"),
])
def test_tier_matrix_requires_measurements_and_respects_thresholds(ram, asr, small, big, gpu, tier, reason):
    hardware = {"ram_bytes": ram * 1024**3 if ram is not None else None,
                "vulkan": [{"name": "Measured device"}] if gpu else []}
    assert assess_tier(hardware, asr_seconds=asr, llm_08_tps=small, llm_2_tps=big) == {
        "tier": tier, "reason": reason}


@pytest.mark.parametrize("measurement", [float("nan"), float("inf"), -0.1])
def test_invalid_timings_cannot_claim_a_tier(measurement):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        assess_tier({}, asr_seconds=measurement)


def test_probe_failure_does_not_hide_other_capabilities_or_guess_acceleration():
    def unavailable():
        raise OSError("missing driver")

    report = probe_hardware(probes={"ram_bytes": lambda: 16 * 1024**3, "cuda": unavailable})
    assert report["ram_bytes"] == 16 * 1024**3 and report["cuda"] is None
    assert report["errors"] == {"cuda": "OSError"}
    assert assess_tier(report)["tier"] == "pending"


def test_snapshots_are_append_only_and_corrupt_latest_file_is_preserved(tmp_path):
    first = save_report({"schema_version": 1, "assessment": {"tier": "pending"}}, tmp_path)
    original = first.read_bytes()
    second = save_report({"schema_version": 1, "assessment": {"tier": "lite"}}, tmp_path)
    os.utime(second, ns=(first.stat().st_mtime_ns + 1000000,) * 2)
    assert latest_report(tmp_path)["assessment"]["tier"] == "lite"
    second.write_text("{", encoding="utf-8")
    assert latest_report(tmp_path)["assessment"]["tier"] == "pending"
    assert first.read_bytes() == original and second.read_text(encoding="utf-8") == "{"
    assert json.loads(first.read_text(encoding="utf-8"))["assessment"]["tier"] == "pending"


@pytest.mark.skipif(os.name != "nt", reason="native Windows hardware APIs")
def test_windows_native_capability_probe_is_serializable_offline():
    NetworkGuard.install()
    try:
        report = probe_hardware()
        assert report["logical_cores"] >= 1 and report["ram_bytes"] > 0
        assert isinstance(report["cpu_features"]["avx2"], bool)
        json.dumps(report, allow_nan=False)
    finally:
        NetworkGuard.uninstall()
