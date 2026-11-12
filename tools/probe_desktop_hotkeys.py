"""Observe two F9 taps through the real native gesture route; inject no input."""

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

from saydraft.config import default_config
from saydraft.hotkeys import HotkeyConfig, HotkeyController
from saydraft.hotkeys.llhook import LowLevelHooks
from saydraft.hotkeys.wispr import wispr_running


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    done, owners, transitions, gestures, failures = threading.Event(), [], [], [], []
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "input": "external F9 taps only; this observer injects no keys",
        "delivery": "gesture callbacks only; no microphone, recognition, History or insertion",
        "start_menu_acceptance_performed": False, "wispr_running": wispr_running()}

    def publish():
        temporary = args.output / "report.pending"
        temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
        temporary.replace(args.output / "report.json")

    def factory(bindings, *, on_action, on_failure):
        def action(transition, when):
            transitions.append({"name": transition.name, "phase": transition.phase,
                "reason": transition.reason, "timestamp": when})
            on_action(transition, when)
            report["transitions"], report["gestures"] = transitions, gestures
            publish()
            if len(transitions) >= 4:
                done.set()
        owner = LowLevelHooks(bindings, on_action=action, on_failure=on_failure)
        owners.append(owner)
        return owner

    def stopped(session):
        gestures.append({"phase": "stop", "locked": session.locked, "duration": session.duration_seconds})

    controller = HotkeyController(HotkeyConfig.from_app_config(default_config()),
        on_record_start=lambda: gestures.append({"phase": "start"}), on_record_stop=stopped,
        on_record_cancel=lambda: gestures.append({"phase": "cancel"}), on_save=lambda: None,
        on_backend_failure=lambda reason: (failures.append(reason), done.set()), native_factory=factory)
    try:
        controller.start()
        report["ready"] = controller.is_backend_alive()
        publish()
        print("Native observer ready: tap F9 twice in an empty editor.", flush=True)
        report["completed_in_time"] = done.wait(max(1, min(300, args.timeout)))
        # Let the fourth transition finish before bounded retirement.
        time.sleep(.05)
    except Exception as error:
        report["error_type"] = type(error).__name__
    finally:
        report["closed"] = controller.stop()
        report["transitions"], report["gestures"], report["failures"] = transitions, gestures, failures
        report["native_status"] = owners[0].status if owners else None
        report["both_hooks_removed"] = bool(owners and not owners[0]._api.handles)
        report["probe_complete"] = bool(report.get("completed_in_time") and not report.get("error_type")
            and not failures and report["closed"] and report["both_hooks_removed"]
            and report["native_status"] == {"state": "closed", "reason": None,
                                          "pump_alive": False, "worker_alive": False}
            and [(row["name"], row["phase"]) for row in transitions] == [
                ("record1", "press"), ("record1", "release"), ("record1", "press"), ("record1", "release")]
            and [row["phase"] for row in gestures] == ["start", "stop"] and gestures[-1]["locked"])
        publish()
        print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
