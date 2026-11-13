import json
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UI Automation required")
def test_windowless_mta_reads_only_own_password_and_plain_controls_then_retires(tmp_path):
    output = tmp_path / "own-controls"
    completed = subprocess.run([sys.executable, "-m", "tools.probe_uia_reader", "--output", str(output)],
                               capture_output=True, timeout=30)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert completed.returncode == 0, report
    assert report["probe_complete"] and report["own_windows_closed"] and not report["failures"]
    assert not report["active_application_read"] and not report["input_injected"] and not report["owner_clipboard_accessed"]
    assert [result["status"] for result in report["results"]] == ["password", "ok"]
    assert [result["status"] for result in report["policy_attempts"]] == ["password", "ok"]
    assert all(set(result) == {"password_case", "is_password", "status", "control_type"}
               for result in report["policy_attempts"])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UI Automation required")
def test_native_context_session_rules_sqlite_and_memory_delivery_compose_without_owner_access(tmp_path):
    output = tmp_path / "own-app-context"
    subprocess.run([sys.executable, "-m", "tools.probe_uia_app", "--output", str(output)],
                   check=True, capture_output=True, timeout=60)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["probe_complete"] and report["own_windows_closed"]
    assert not report["active_application_read"] and not report["owner_clipboard_accessed"]
    assert not report["input_injected"] and not report["asr_performed"] and not report["microphone_used"]
    assert [row["reason"] for row in report["cases"]] == ["password_field", ""]
    assert [row["deliveries"] for row in report["cases"]] == [0, 1]
    assert all(row["raw_clean_exact"] and row["serial_closed"] and row["mta_closed"] for row in report["cases"])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UI Automation required")
def test_native_tracked_edit_reads_fresh_original_field_and_refuses_password_changes(tmp_path):
    output = tmp_path / "own-tracked-edit"
    subprocess.run([sys.executable, "-m", "tools.probe_tracked_edit", "--output", str(output)],
                   check=True, capture_output=True, timeout=60)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["probe_complete"] and report["own_windows_closed"] and not report["failures"]
    assert not report["active_application_read"] and not report["input_injected"] and not report["owner_clipboard_accessed"]
    assert [row["case"] for row in report["cases"]] == ["correction", "runtime_lookup", "password", "becomes_password", "asynchronous", "session"]
    assert report["cases"][-2]["independent_critical_reader"] and report["cases"][-2]["observation_closed"]
    assert report["cases"][-1]["history_before_input"] and report["cases"][-1]["session_suggestion_emitted"]
    assert report["cases"][-1]["session_dictionary_add_undo"]
    assert report["cases"][-1]["session_owners_closed"] and not report["microphone_used"] and not report["asr_performed"]
