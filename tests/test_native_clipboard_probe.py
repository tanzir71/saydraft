"""Default native probe must never fall back to the owner's clipboard in CI."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Windows native clipboard isolation")
def test_native_clipboard_replay_uses_private_surface_or_refuses_before_owner_access(tmp_path):
    output = tmp_path / "native-clipboard"
    result = subprocess.run([sys.executable, "-m", "tools.probe_native_clipboard", "--output", str(output)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert not report["owner_clipboard_accessed"] and not report["input_injected"]
    assert report["private_desktop_closed"] and report["private_station_closed"]
    assert report["original_surface_restored"]
    if (not report.get("isolated_window_station") and not report.get("stage")
            and report.get("error", "").startswith(("Private window station unavailable:", "Private desktop unavailable:"))):
        pytest.skip("Windows account cannot create the separate clipboard test surface; no owner access occurred")
    assert result.returncode == 0 and report["probe_complete"], report
    assert report["deliveries"] == report["history_rows"] == report["iterations"] == 10
    assert report["exact_restored_formats"] == 3 and report["private_copy_verified"]
    assert report["gdi_before"] == report["gdi_after_replay"]
    assert not report["asr_performed"] and not report["win_v_acceptance_performed"]


@pytest.mark.skipif(os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true',
                    reason='Native copy qualification uses a disposable Windows CI runner only')
def test_native_selection_copy_restores_all_formats_on_private_surface(tmp_path):
    output = tmp_path / 'own-selection-copy'
    result = subprocess.run([sys.executable, '-m', 'tools.probe_selection_copy', '--output', str(output)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
    report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
    assert not report['owner_clipboard_accessed'] and not report['input_injected'] and not report['microphone_used']
    assert report['private_desktop_closed'] and report['private_station_closed'] and report['original_surface_restored']
    if (not report.get('isolated_window_station') and not report.get('stage')
            and report.get('error', '').startswith(('Private window station unavailable:', 'Private desktop unavailable:'))):
        pytest.skip('Windows account refused the separate clipboard surface before any clipboard access')
    assert result.returncode == 0 and report['probe_complete'], report
    assert report['owned_edit_closed'] and report['clipboard_recovery_retired'] and report['pre_input_refusal']
    assert len(report['cases']) == 3 and all(c['all_formats_exact'] and c['text_exact'] for c in report['cases'])
