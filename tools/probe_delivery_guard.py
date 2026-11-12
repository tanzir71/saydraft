"""Read-only native integrity-query/handle-lifetime proof against this process."""

import argparse
import ctypes as ct
import json
import os
import subprocess
from ctypes import wintypes as wt
from pathlib import Path

from saydraft.insert.guards_win import NativeDeliveryApi


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "input_injected": False, "clipboard_accessed": False, "other_processes_queried": False,
        "elevated_window_acceptance_performed": False}
    try:
        api = NativeDeliveryApi()
        api.kernel.GetProcessHandleCount.argtypes = [wt.HANDLE, ct.POINTER(wt.DWORD)]
        api.kernel.GetProcessHandleCount.restype = wt.BOOL
        process = api.kernel.GetCurrentProcess()
        def count():
            value = wt.DWORD()
            if not api.kernel.GetProcessHandleCount(process, ct.byref(value)):
                raise OSError("Handle count is unavailable")
            return value.value
        own, explicit = api.integrity(), api.integrity(os.getpid())
        report["own_integrity"], report["explicit_query_integrity"] = own, explicit
        report["handles_before"] = count()
        matches = own == explicit
        for _ in range(20):
            matches = (api.integrity() == own and api.integrity(os.getpid()) == explicit) and matches
        report["queries"], report["all_queries_match"] = 42, matches
        report["handles_after"] = count()
    except Exception as error:
        report["error_type"] = type(error).__name__
    report["probe_complete"] = bool(not report.get("error_type") and report.get("all_queries_match")
        and report["handles_before"] == report["handles_after"])
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
