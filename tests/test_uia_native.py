import json
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UI Automation required")
def test_windowless_mta_reads_only_own_password_and_plain_controls_then_retires(tmp_path):
    output = tmp_path / "own-controls"
    subprocess.run([sys.executable, "-m", "tools.probe_uia_reader", "--output", str(output)],
                   check=True, capture_output=True, timeout=30)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["probe_complete"] and report["own_windows_closed"] and not report["failures"]
    assert not report["active_application_read"] and not report["input_injected"] and not report["owner_clipboard_accessed"]
    assert [result["status"] for result in report["results"]] == ["password", "ok"]
