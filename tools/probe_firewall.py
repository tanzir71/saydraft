"""Disposable GitHub-hosted Windows rule/native/download/worker verification.

Never run on an owner machine. Only a new copied interpreter is blocked; the
source interpreter, runner agent, system profiles and unrelated rules survive.
"""

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def rule_shape(executable):
    """Bounded public-fixture diagnostics; no program paths or provider errors."""
    import base64
    script = r"""$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$program = ([Console]::In.ReadToEnd() | ConvertFrom-Json).program
$rules = @(Get-NetFirewallApplicationFilter -PolicyStore PersistentStore | Where-Object {
    $_.Program -ieq $program
} | Get-NetFirewallRule | Where-Object { $_.Group -ceq 'Saydraft.Managed.v1' })
if ($rules.Count -ne 1) { throw 'Unexpected fixture count' }
$rule = $rules[0]
$app = $rule | Get-NetFirewallApplicationFilter
$port = $rule | Get-NetFirewallPortFilter
$address = $rule | Get-NetFirewallAddressFilter
[pscustomobject]@{
    enabled=[string]$rule.Enabled; profile=[string]$rule.Profile;
    direction=[string]$rule.Direction; action=[string]$rule.Action;
    package=[string]$app.Package; protocol=[string]$port.Protocol;
    local=[string]$address.LocalAddress; remote=[string]$address.RemoteAddress;
    service=[string]($rule | Get-NetFirewallServiceFilter).Service;
    alias=[string]($rule | Get-NetFirewallInterfaceFilter).InterfaceAlias;
    type=[string]($rule | Get-NetFirewallInterfaceTypeFilter).InterfaceType
} | ConvertTo-Json -Compress
"""
    from saydraft.privacy.firewall_control import _system_directory
    process = subprocess.run([str(_system_directory() / "WindowsPowerShell/v1.0/powershell.exe"),
        "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand",
        base64.b64encode(script.encode("utf-16-le")).decode("ascii")],
        input=json.dumps({"program": str(executable)}), capture_output=True, text=True,
        encoding="utf-8", timeout=15, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    return json.loads(process.stdout.lstrip("\ufeff"))



def child(request):
    from saydraft.privacy.firewall_verification import native_http, download_probe
    from saydraft.privacy.netguard import NetworkGuard
    NetworkGuard.install()
    if request["kind"] == "native":
        return native_http()
    if request["kind"] == "download":
        return download_probe(request["directory"])
    if request["kind"] == "dictation":
        from tools.latency_trial import run_trial
        report = run_trial(request["trial"])
        return {"complete": report["complete"], "cases": len(report["cases"]),
                "model_ids": [case["asr_model"] for case in report["cases"]],
                "history_before_paste": all(case["history_before_paste"] for case in report["cases"]),
                "memory_clipboard_restored": all(case["clipboard_restored"] for case in report["cases"]),
                "error_type": report.get("error_type")}
    raise ValueError("Unknown owned probe")


def run_probe(output):
    if sys.platform != "win32" or os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise RuntimeError("Firewall mutation probe is restricted to disposable GitHub-hosted Windows runners")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError("Disposable runner requires an administrator token; never launch UAC from CI")
    temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    output = output.absolute()
    if not output.is_relative_to(temp) or output == temp or output.exists():
        raise ValueError("Choose a fresh probe directory under RUNNER_TEMP")
    output.mkdir()
    if output.resolve() != output:
        raise ValueError("Probe directory is linked")
    executable = output / "Saydraft.exe"
    base = Path(sys.base_prefix)
    shutil.copy2(base / "python.exe", executable)
    for pattern in ("python*.dll", "vcruntime*.dll"):
        for dll in base.glob(pattern):
            shutil.copy2(dll, output / dll.name)
    from saydraft.privacy.firewall_control import helper_main, rule_name
    from saydraft.privacy.firewall import inspect_firewall
    from tools.latency_matrix import child_environment
    from tools.latency_environment import runtime_environment
    report = {"complete": False, "measured_at": datetime.now(timezone.utc).isoformat(),
              "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "scope": "copied owned Python executable, production fixed rule script and real worker; not a frozen application",
              "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
              "rule_name": rule_name(executable), "microphone_used": False, "input_injected": False,
              "owner_clipboard_accessed": False, "steps": {}}
    report["runtime_environment"] = runtime_environment()
    request_count = 0
    def invoke(kind, **options):
        nonlocal request_count
        request_count += 1
        directory = output / f"child-{request_count:02d}-{kind}"
        directory.mkdir()
        environment = child_environment(directory)
        environment["PYTHONHOME"] = str(base)
        request = directory / "request.json"
        result = directory / "result.json"
        request.write_text(json.dumps({"kind": kind, **options}), encoding="utf-8")
        process = subprocess.run([str(executable), "-m", "tools.probe_firewall", "--child", str(request), str(result)],
                                 cwd=ROOT, env=environment, capture_output=True, timeout=180,
                                 creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        (directory / "process.json").write_text(json.dumps({"exit_code": process.returncode,
            "stdout_bytes": len(process.stdout), "stderr_bytes": len(process.stderr),
            "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(process.stderr).hexdigest()}), encoding="utf-8")
        if process.returncode != 0 or not result.is_file():
            raise RuntimeError("Owned probe child failed")
        return json.loads(result.read_text(encoding="utf-8"))
    try:
        report["stage"] = "install-public-fixtures"
        from saydraft.model_download import download_asr_model
        whisper = download_asr_model("whisper-base", models_dir=output / "models")
        from saydraft.model_download import download_silero_vad_model
        vad = download_silero_vad_model(models_dir=output / "models")
        report["stage"] = "fresh-rule-check"
        before = inspect_firewall(program=executable)
        if before.state != "absent":
            raise RuntimeError("Fresh executable already has a matching rule")
        report["stage"] = "online-controls-before"
        report["steps"]["native_before"] = invoke("native")
        report["steps"]["download_before"] = invoke("download", directory=str(output / "download-before"))
        if not report["steps"]["native_before"]["reachable"] or not report["steps"]["download_before"]["downloaded"]:
            raise RuntimeError("Online controls failed before any rule was created")
        for key in ("block", "block_idempotent"):
            report["stage"] = key
            report["steps"][key] = helper_main(["block"], target_provider=lambda: executable)
            if key == "block" and report["steps"][key] == 0:
                report["rule_shape"] = rule_shape(executable)
            if report["steps"][key] != 0:
                raise RuntimeError("Owned rule creation/idempotence failed")
        report["steps"]["matching_rules"] = inspect_firewall(program=executable).matching_rules
        if report["steps"]["matching_rules"] != 1:
            raise RuntimeError("Owned block rule is not present in ActiveStore")
        report["stage"] = "blocked-native-and-download"
        report["steps"]["native_blocked"] = invoke("native")
        report["steps"]["download_blocked"] = invoke("download", directory=str(output / "download-blocked"))
        if report["steps"]["native_blocked"]["reachable"] or report["steps"]["download_blocked"]["downloaded"]:
            raise RuntimeError("Owned outbound rule did not block both native and Python transfers")
        if not all(report["steps"]["download_blocked"].get(key) for key in ("firewall_recovery_message", "resume_message")):
            raise RuntimeError("Blocked download lacks its recovery message")
        report["stage"] = "blocked-worker"
        trial_output = output / "worker"
        trial_output.mkdir()
        trial = {"output": str(trial_output), "git_commit": report["git_commit"], "audio_seconds": 3,
                 "repeat": 0, "tier": "lite", "asr_model": "whisper-base", "candidate": None,
                 "backend": "cpu", "device": None, "whisper_dir": str(whisper), "vad_dir": str(vad),
                 "runtime_environment": runtime_environment()}
        report["steps"]["dictation_blocked"] = invoke("dictation", trial=trial)
        if not report["steps"]["dictation_blocked"]["complete"]:
            raise RuntimeError("Real worker failed under the owned block rule")
        report["stage"] = "remove"
        report["steps"]["remove"] = helper_main(["remove"], target_provider=lambda: executable)
        if report["steps"]["remove"] != 0 or inspect_firewall(program=executable).state != "absent":
            raise RuntimeError("Owned rule removal failed")
        report["stage"] = "online-controls-after"
        report["steps"]["native_after"] = invoke("native")
        report["steps"]["download_after"] = invoke("download", directory=str(output / "download-after"))
        report["complete"] = report["steps"]["native_after"]["reachable"] and report["steps"]["download_after"]["downloaded"]
        if not report["complete"]:
            raise RuntimeError("Online controls did not recover after removal")
        report["stage"] = "complete"
    except Exception as error:
        report["error_type"] = type(error).__name__
    finally:
        report["cleanup_exit"] = helper_main(["remove"], target_provider=lambda: executable)
        report["cleanup_absent"] = inspect_firewall(program=executable).state == "absent"
        report["complete"] = report["complete"] and report["cleanup_exit"] == 0 and report["cleanup_absent"]
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", nargs=2, type=Path, metavar=("REQUEST", "RESULT"))
    parser.add_argument("--prepare-speech-model", type=Path, help="explicit pinned fixture download on a disposable runner")
    args = parser.parse_args(argv)
    if args.prepare_speech_model:
        from saydraft.privacy.firewall_verification import require_disposable_runner
        require_disposable_runner()
        from saydraft.model_download import download_asr_model
        if not args.prepare_speech_model.absolute().is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve()):
            parser.error("Fixture root must be under RUNNER_TEMP")
        directory = download_asr_model("whisper-base", models_dir=args.prepare_speech_model)
        print(json.dumps({"directory": str(directory)}))
        return 0
    if args.child:
        request, result = args.child
        data = child(json.loads(request.read_text(encoding="utf-8")))
        with result.open("x", encoding="utf-8") as stream:
            json.dump(data, stream)
        return 0
    if args.output is None:
        parser.error("--output is required")
    report = run_probe(args.output)
    print(json.dumps({key: report.get(key) for key in ("complete", "stage", "cleanup_absent", "error_type", "rule_shape")}))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
