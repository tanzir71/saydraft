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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UI Automation required")
def test_native_selection_uses_only_own_ranges_and_rejects_changed_read_only_or_password_fields(tmp_path):
    output = tmp_path / "own-selection"
    completed = subprocess.run([sys.executable, "-m", "tools.probe_selection", "--output", str(output)],
                               capture_output=True, timeout=30)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert completed.returncode == 0, report
    assert report["probe_complete"] and report["mta_closed"] and report["own_windows_closed"]
    spans = [case for case in report['cases'] if case['case'] == 'replacement_span']
    assert len(spans) == 2 and any(case['replacement_units'] == 9000 for case in spans)
    assert all(case['reason'] == '' and case['own_field_exact'] for case in spans)
    pipeline = [case for case in report['cases'] if case['case'] == 'command_processor_native_target']
    assert len(pipeline) == 2 and {case['fixture_direct_message_write'] for case in pipeline} == {True, False}
    assert all(case['ready_contract'] and case['durable_before_input'] and case['memory_clipboard_restored'] for case in pipeline)
    assert all(case['reason'] == ('ok' if case['fixture_direct_message_write'] else 'insertion_unconfirmed') for case in pipeline)
    assert any(case['case'] == 'password_before_confirmation' and case['no_post_write_text_read'] for case in report['cases'])
    assert any(case['case'] == 'truncated_write_unconfirmed' and case['reason'] == 'insertion_unconfirmed'
               and case['own_field_units'] <= case['fixture_text_limit'] for case in report['cases'])
    assert not report["active_application_read"] and not report["owner_clipboard_accessed"]
    assert not report["input_injected"] and not report["microphone_used"]
    assert [row["case"] for row in report["cases"]] == [
        "long_selection", "same_text_new_range", "changed_text", "replacement_span", "replacement_span",
        "matching_text_elsewhere_unconfirmed", "truncated_write_unconfirmed", "password_before_confirmation",
        "command_processor_native_target", "command_processor_native_target", "read_only", "password", "cancel"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UI Automation required")
def test_held_command_worker_uses_owned_native_ranges_without_owner_audio_clipboard_or_keys(tmp_path):
    output = tmp_path / 'own-command'
    completed = subprocess.run([sys.executable, '-m', 'tools.probe_command_recording', '--output', str(output)],
                               capture_output=True, timeout=60)
    report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    assert completed.returncode == 0, report
    assert report['probe_complete'] and report['mta_closed'] and report['own_windows_closed']
    assert not any(report[key] for key in ('active_application_read', 'input_injected', 'owner_clipboard_accessed',
                                         'microphone_used', 'asr_performed', 'native_edit_model_used'))
    cases = [case for case in report['cases'] if case['case'] == 'held_command_worker']
    assert [case['mode'] for case in cases] == ['prefix_replace', 'ignored_paste', 'read_only_copy', 'failed_edit', 'release_during_prepare']
    assert [case['outcome'] for case in cases] == ['ok', 'insertion_unconfirmed', 'read_only', 'unavailable', 'released_before_capture']
    assert [case['capture_starts'] for case in cases] == [2, 1, 1, 1, 0]
    assert all(case['serial_closed'] and case['own_field_exact'] and case['all_editors_retired']
               and case['memory_clipboard_restored'] for case in cases)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows UI Automation required')
def test_held_command_copy_uses_native_original_metadata_without_owner_clipboard_or_keys(tmp_path):
    output = tmp_path / 'own-command-copy'
    completed = subprocess.run([sys.executable, '-m', 'tools.probe_command_copy', '--output', str(output)],
                               capture_output=True, timeout=60)
    report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    assert completed.returncode == 0, report
    assert report['probe_complete'] and report['mta_closed'] and report['own_windows_closed']
    assert not any(report[key] for key in ('active_application_read', 'input_injected', 'owner_clipboard_accessed',
                                         'microphone_used', 'asr_performed', 'native_edit_model_used'))
    cases = [case for case in report['cases'] if case['case'] == 'held_command_worker']
    assert [case['mode'] for case in cases] == ['fallback_copy', 'fallback_sensitive', 'fallback_cancel']
    assert [case['outcome'] for case in cases] == ['copy_only', 'password_field', 'cancelled_during_copy']
    assert [case['copy_attempts'] for case in cases] == [1, 0, 1]
    assert [case['history_rows'] for case in cases] == [1, 1, 0]
    assert [case['recovery_requests'] for case in cases] == [1, 0, 0]
    assert all(case['paste_attempts'] == case['selection_text_reads'] == 0 for case in cases)
    assert all(case['serial_closed'] and case['own_field_exact'] and case['all_editors_retired']
               and case['memory_clipboard_restored'] and case['selection_pattern_suppressed'] for case in cases)
