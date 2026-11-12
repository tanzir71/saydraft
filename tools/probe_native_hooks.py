"""Test owned native hooks with unassigned vkE8 only; no microphone or user text."""

import argparse
import ctypes as c
import json
import subprocess
import threading
import time
from pathlib import Path

from saydraft.hotkeys._win32_hooks import Win32Hooks
from saydraft.hotkeys.chords import Binding, Chord
from saydraft.hotkeys.llhook import LowLevelHooks
from saydraft.input_origin import SAYDRAFT_INPUT_TAG
from saydraft.insert.sendinput import _Input, _KeyboardInput


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    done, actions, failures = threading.Event(), [], []
    api = Win32Hooks()
    def action(transition, when):
        actions.append({"phase": transition.phase, "timestamp": when, "thread": threading.get_ident()})
        if transition.phase == "release":
            done.set()
    hooks = LowLevelHooks([Binding("qa", Chord.parse("vkE8"))], api_factory=lambda: api,
        on_action=action, on_failure=failures.append)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "input": "unassigned vkE8 only; no Win/Ctrl, mouse, text, microphone or insertion"}
    try:
        hooks.start()
        report["both_hooks_installed"] = len(api.handles) == 2
        # Tagged mask input must not recurse. Untagged accessibility/macro input can fire.
        api.mask()
        values = (_Input * 2)()
        for value, flags in zip(values, (0, 2)):
            value.type = 1
            value.data.ki = _KeyboardInput(0xE8, 0, flags, 0, SAYDRAFT_INPUT_TAG ^ 1)
        assert api.user.SendInput(2, values, c.sizeof(_Input)) == 2
        assert done.wait(3)
        report["phases"] = [row["phase"] for row in actions]
        report["off_hook_dispatch"] = all(row["thread"] == hooks._worker.ident
            and row["thread"] != hooks._pump_thread.ident for row in actions)
        report["timestamps_ordered"] = actions[0]["timestamp"] <= actions[-1]["timestamp"]
        started, cpu = time.perf_counter(), time.process_time()
        time.sleep(.5)
        report["idle_sample_seconds"] = time.perf_counter() - started
        report["idle_cpu_seconds"] = time.process_time() - cpu
        report["idle_cpu_percent"] = 100 * report["idle_cpu_seconds"] / report["idle_sample_seconds"]
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        report["closed"] = hooks.close()
        report["remaining_hooks"] = len(api.handles)
        report["status"], report["failures"] = hooks.status, failures
        report["probe_complete"] = (report.get("both_hooks_installed") and report.get("off_hook_dispatch")
            and report.get("timestamps_ordered") and report.get("phases") == ["press", "release"]
            and report["closed"] and report["remaining_hooks"] == 0 and not failures and not report.get("error_type"))
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
