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


def native_http():
    """A fixed credential-free WinHTTP request, bypassing Python socket hooks."""
    from ctypes import wintypes as w
    api = ctypes.WinDLL("winhttp", use_last_error=True)
    signatures = {
        "WinHttpOpen": ([w.LPCWSTR, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD], w.HANDLE),
        "WinHttpConnect": ([w.HANDLE, w.LPCWSTR, w.WORD, w.DWORD], w.HANDLE),
        "WinHttpOpenRequest": ([w.HANDLE, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, ctypes.c_void_p, w.DWORD], w.HANDLE),
        "WinHttpSetTimeouts": ([w.HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int], w.BOOL),
        "WinHttpSendRequest": ([w.HANDLE, w.LPCWSTR, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.c_size_t], w.BOOL),
        "WinHttpReceiveResponse": ([w.HANDLE, ctypes.c_void_p], w.BOOL),
        "WinHttpQueryHeaders": ([w.HANDLE, w.DWORD, w.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
        "WinHttpCloseHandle": ([w.HANDLE], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        method = getattr(api, name)
        method.argtypes, method.restype = args, result
    handles = []
    try:
        session = api.WinHttpOpen("Saydraft-disposable-firewall-probe", 1, None, None, 0)  # no proxy
        if not session:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(session)
        if not api.WinHttpSetTimeouts(session, 3000, 3000, 3000, 3000):
            raise ctypes.WinError(ctypes.get_last_error())
        connection = api.WinHttpConnect(session, "api.github.com", 443, 0)
        if not connection:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(connection)
        request = api.WinHttpOpenRequest(connection, "GET", "/repos/tanzir71/saydraft/releases/latest", None, None, None, 0x800000)
        if not request:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(request)
        # Disable redirects: no second host is contacted by this probe.
        api.WinHttpSetOption.argtypes = [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD]
        api.WinHttpSetOption.restype = w.BOOL
        policy = w.DWORD(0)  # WINHTTP_OPTION_REDIRECT_POLICY_NEVER
        if not api.WinHttpSetOption(request, 88, ctypes.byref(policy), ctypes.sizeof(policy)):
            raise ctypes.WinError(ctypes.get_last_error())
        disabled = w.DWORD(0x1 | 0x2 | 0x4)  # cookies, redirects, automatic authentication
        if not api.WinHttpSetOption(request, 63, ctypes.byref(disabled), ctypes.sizeof(disabled)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not api.WinHttpSendRequest(request, None, 0, None, 0, 0, 0) or not api.WinHttpReceiveResponse(request, None):
            raise ctypes.WinError(ctypes.get_last_error())
        code, size = w.DWORD(), w.DWORD(ctypes.sizeof(w.DWORD))
        if not api.WinHttpQueryHeaders(request, 19 | 0x20000000, None, ctypes.byref(code), ctypes.byref(size), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"reachable": True, "http_status": code.value}
    except OSError as error:
        return {"reachable": False, "winerror": error.winerror}
    finally:
        for handle in reversed(handles):
            api.WinHttpCloseHandle(handle)


def child(request):
    from saydraft.privacy.netguard import NetworkGuard
    NetworkGuard.install()
    if request["kind"] == "native":
        return native_http()
    if request["kind"] == "download":
        from saydraft.models.downloader import download_model
        from saydraft.models.manifest import get_model
        from saydraft.models.errors import download_failure_message
        source = get_model("whisper-base")
        file = next(file for file in source["files"] if file["path"] == "config.json")
        model = {**source, "files": [file]}
        try:
            download_model(model, Path(request["directory"]))
            return {"downloaded": True}
        except Exception as error:
            message = download_failure_message(error)
            return {"downloaded": False, "error_type": type(error).__name__,
                    "firewall_recovery_message": "remove Saydraft’s block rule" in message,
                    "resume_message": "Download to resume" in message}
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
    args = parser.parse_args(argv)
    if args.child:
        request, result = args.child
        data = child(json.loads(request.read_text(encoding="utf-8")))
        with result.open("x", encoding="utf-8") as stream:
            json.dump(data, stream)
        return 0
    if args.output is None:
        parser.error("--output is required")
    report = run_probe(args.output)
    print(json.dumps({"complete": report["complete"], "cleanup_absent": report["cleanup_absent"], "error_type": report.get("error_type")}))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
