import base64
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from saydraft.privacy import firewall_control as control


def test_source_and_unsupported_installations_never_launch_elevation(tmp_path):
    target = tmp_path / "Saydraft.exe"
    target.write_bytes(b"owned fixture")
    assert control.packaged_executable(executable=target, frozen=False, platform="win32") is None
    assert control.packaged_executable(executable=target, frozen=True, platform="linux") is None
    assert control.packaged_executable(executable="Saydraft.exe", frozen=True, platform="win32") is None
    assert control.packaged_executable(executable=r"\\server\share\Saydraft.exe", frozen=True, platform="win32") is None
    assert control.packaged_executable(executable=tmp_path / "python.exe", frozen=True, platform="win32") is None
    calls = []
    for action in ("block", "remove", "anything"):
        result = control.change_firewall(action, target_provider=lambda: None, launcher=lambda *a: calls.append(a))
        assert result == control.FirewallChange("unsupported")
    assert not calls


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse-point attributes")
def test_packaged_target_is_an_existing_unlinked_executable(tmp_path):
    target = tmp_path / "Saydraft.exe"
    target.write_bytes(b"owned fixture")
    assert control.packaged_executable(executable=target, frozen=True, platform="win32") == target
    target.unlink()
    assert control.packaged_executable(executable=target, frozen=True, platform="win32") is None


@pytest.mark.parametrize("action", ["block", "remove"])
@pytest.mark.parametrize("code", [0, 20, 21, 22, 99])
def test_helper_uses_fixed_hidden_script_json_data_and_bounded_exit_codes(action, code):
    target = Path("C:/Owned'; Write-Host injected/Saydraft.exe")
    calls = []
    def run(command, **options):
        calls.append((command, options))
        return SimpleNamespace(returncode=code)
    result = control.helper_main([action], target_provider=lambda: target, runner=run,
                                 system_directory=lambda: Path("C:/Windows/System32"))
    assert result == (code if code in control._EXITS else 22)
    command, options = calls[0]
    script = base64.b64decode(command[-1]).decode("utf-16-le")
    assert script == control._MANAGE_SCRIPT and "Write-Host injected" not in script
    assert command[0].endswith("WindowsPowerShell/v1.0/powershell.exe")
    assert command[command.index("-WindowStyle") + 1] == "Hidden"
    assert options["timeout"] == 30 and "shell" not in options
    assert json.loads(options["input"]) == {"action": action, "program": str(target), "name": control.rule_name(target)}
    assert "NetSecurity\\Remove-NetFirewallRule -Confirm:$false" in script
    assert "Where-Object { $_.Name -ceq $request.name }" in script
    assert "Set-NetFirewallRule" not in script and "-PolicyStore PersistentStore" in script


@pytest.mark.parametrize("arguments", [[], ["allow"], ["block", "C:/other.exe"], ["remove", "--all"]])
def test_helper_rejects_extra_parameters_before_any_target_or_process_access(arguments):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid helper parameters were used")
    assert control.helper_main(arguments, target_provider=forbidden, runner=forbidden) == 20


def test_helper_refuses_source_and_fails_closed_without_provider_details():
    def forbidden(*args, **kwargs):
        raise AssertionError("Source helper launched PowerShell")
    assert control.helper_main(["block"], target_provider=lambda: None, runner=forbidden) == 20
    def fail(*args, **kwargs):
        raise TimeoutError("private provider details")
    assert control.helper_main(["block"], target_provider=lambda: Path("C:/owned/Saydraft.exe"),
                               runner=fail, system_directory=lambda: Path("C:/Windows/System32")) == 22


def test_rule_identity_is_path_specific_case_insensitive_and_bounded():
    assert control.rule_name("C:/First/Saydraft.exe") == control.rule_name("c:/first/saydraft.EXE")
    assert control.rule_name("C:/First/Saydraft.exe") != control.rule_name("C:/Second/Saydraft.exe")
    assert len(control.rule_name("x" * 40000)) < 100


def test_only_one_elevation_request_runs_and_failures_release_the_owner():
    entered, release = threading.Event(), threading.Event()
    result = []
    def launch(target, action):
        entered.set()
        assert release.wait(3)
        return control.FirewallChange("cancelled")
    def target():
        return Path("C:/Owned/Saydraft.exe")
    thread = threading.Thread(target=lambda: result.append(control.change_firewall("block", target_provider=target, launcher=launch)))
    try:
        thread.start()
        assert entered.wait(1)
        assert control.change_firewall("remove", target_provider=target, launcher=launch) == control.FirewallChange("busy")
    finally:
        release.set()
        thread.join(2)
    assert result == [control.FirewallChange("cancelled")]
    def fail(*args):
        raise OSError("private launch details")
    assert control.change_firewall("remove", target_provider=target, launcher=fail) == control.FirewallChange()
    assert control.change_firewall("remove", target_provider=target,
                                   launcher=lambda *a: control.FirewallChange("applied")) == control.FirewallChange("applied")


def test_helper_dispatch_happens_before_any_application_services(monkeypatch):
    from saydraft.main import main
    calls = []
    monkeypatch.setattr(sys, "argv", ["Saydraft.exe", control.HELPER_ARGUMENT, "remove"])
    monkeypatch.setattr(control, "helper_main", lambda args: calls.append(args) or 21)
    monkeypatch.setattr("saydraft.privacy.netguard.NetworkGuard.install", lambda: pytest.fail("Helper installed app services"))
    assert main() == 21 and calls == [["remove"]]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows ctypes ABI without launching any process")
@pytest.mark.parametrize("shell_ok,error,wait,exit_code,expected", [
    (False, 1223, 0, 0, "cancelled"), (False, 5, 0, 0, "failed"),
    (True, 0, 0, 0, "applied"), (True, 0, 0, 21, "conflict"),
    (True, 0, 0, 255, "failed"), (True, 0, 0xFFFFFFFF, 0, "unknown")])
def test_runas_abi_flags_fixed_arguments_exit_codes_and_handle_retirement(monkeypatch, shell_ok, error, wait, exit_code, expected):
    import ctypes
    calls = []
    def execute(pointer):
        info = pointer._obj
        calls.append((info.lpVerb, info.lpFile, info.lpParameters, info.lpDirectory, info.fMask, info.nShow))
        if shell_ok:
            info.hProcess = 4242
        return shell_ok
    def get_code(handle, pointer):
        pointer._obj.value = exit_code
        return True
    def close(handle):
        calls.append(("closed", handle))
        return True
    shell = SimpleNamespace(ShellExecuteExW=execute)
    kernel = SimpleNamespace(WaitForSingleObject=lambda handle, timeout: wait,
                             GetExitCodeProcess=get_code, CloseHandle=close)
    ole = SimpleNamespace(CoInitializeEx=lambda *args: 0, CoUninitialize=lambda: calls.append(("com-retired",)))
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kwargs: shell if name == "shell32" else kernel)
    monkeypatch.setattr(ctypes, "OleDLL", lambda name: ole)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error)
    assert control._elevated_launch(Path("C:/Owned/Saydraft.exe"), "block") == control.FirewallChange(expected)
    verb, program, parameters, directory, flags, show = calls[0]
    assert (verb, parameters, show) == ("runas", "--manage-firewall block", 0)
    assert program.endswith("Saydraft.exe") and directory.endswith("Owned")
    assert flags & 0x40 and flags & 0x100 and flags & 0x400
    assert (("closed", 4242) in calls) == shell_ok
    assert calls[-1] == ("com-retired",)
