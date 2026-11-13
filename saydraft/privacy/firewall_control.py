"""Explicit, packaged-only management of one path-specific outbound block rule.

No caller supplies an executable or script to the elevated entrypoint. The helper
derives its own frozen executable and touches only its deterministic local rule.
"""

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading


HELPER_ARGUMENT = "--manage-firewall"
_EXITS = {0: "applied", 20: "unsupported", 21: "conflict", 22: "failed"}
_launch_lock = threading.Lock()


@dataclass(frozen=True)
class FirewallChange:
    state: str = "failed"


def packaged_executable(*, executable=None, frozen=None, platform=None):
    """Source Python, remote paths and linked installations cannot be blocked."""
    if (platform or sys.platform) != "win32" or not (getattr(sys, "frozen", False) if frozen is None else frozen):
        return None
    path = Path(executable or sys.executable)
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")) or path.name.lower() != "saydraft.exe":
        return None
    try:
        if not path.is_file() or os.path.normcase(str(path.resolve(strict=True))) != os.path.normcase(str(path)):
            return None
        for item in (path, *path.parents):
            if item.lstat().st_file_attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                return None
    except (OSError, AttributeError):
        return None
    return path


def rule_name(program):
    digest = hashlib.sha256(str(program).casefold().encode("utf-8")).hexdigest()
    return "Saydraft.Outbound.v1." + digest


# Every variable value is read as JSON from stdin. No paths or shell fragments
# are interpolated into this script. Never remove rules by display name/group.
_MANAGE_SCRIPT = r"""$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $module = Join-Path ([Environment]::GetFolderPath('System')) 'WindowsPowerShell\v1.0\Modules\NetSecurity\NetSecurity.psd1'
    Import-Module -Name $module -Force -ErrorAction Stop
    $rules = @(NetSecurity\Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object { $_.Name -ceq $request.name })
    if ($rules.Count -gt 1) { exit 21 }
    if ($rules.Count -eq 1) {
        $rule = $rules[0]
        $apps = @($rule | NetSecurity\Get-NetFirewallApplicationFilter)
        if ($rule.Group -cne 'Saydraft.Managed.v1' -or $rule.Description -cne $request.name -or
            $rule.Direction -ne 'Outbound' -or $rule.Action -ne 'Block' -or
            $apps.Count -ne 1 -or $apps[0].Program -ine $request.program) { exit 21 }
        if ($request.action -ceq 'remove') {
            $rule | NetSecurity\Remove-NetFirewallRule -Confirm:$false -ErrorAction Stop
        } else {
            # Refuse edited/disabled/narrowed rules rather than overwriting them.
            $ports = @($rule | NetSecurity\Get-NetFirewallPortFilter)
            $addresses = @($rule | NetSecurity\Get-NetFirewallAddressFilter)
            $services = @($rule | NetSecurity\Get-NetFirewallServiceFilter)
            $interfaces = @($rule | NetSecurity\Get-NetFirewallInterfaceFilter)
            $types = @($rule | NetSecurity\Get-NetFirewallInterfaceTypeFilter)
            if ($rule.Enabled -ne 'True' -or $rule.Profile -ne 'Any' -or
                $ports.Count -ne 1 -or $ports[0].Protocol -ne 'Any' -or
                $addresses.Count -ne 1 -or $addresses[0].LocalAddress -ne 'Any' -or
                $addresses[0].RemoteAddress -ne 'Any' -or $apps[0].Package -ne 'Any' -or
                $services.Count -ne 1 -or $services[0].Service -ne 'Any' -or
                $interfaces.Count -ne 1 -or $interfaces[0].InterfaceAlias -ne 'Any' -or
                $types.Count -ne 1 -or $types[0].InterfaceType -ne 'Any') { exit 21 }
        }
    } elseif ($request.action -ceq 'block') {
        NetSecurity\New-NetFirewallRule -PolicyStore PersistentStore -Name $request.name `
            -DisplayName 'Saydraft — block outbound connections' -Group 'Saydraft.Managed.v1' `
            -Description $request.name -Program $request.program -Direction Outbound -Action Block `
            -Enabled True -Profile Any -Protocol Any -LocalAddress Any -RemoteAddress Any `
            -InterfaceType Any -Service Any -ErrorAction Stop | Out-Null
    }
    $after = @(NetSecurity\Get-NetFirewallRule -PolicyStore PersistentStore | Where-Object { $_.Name -ceq $request.name })
    if (($request.action -ceq 'remove' -and $after.Count -ne 0) -or
        ($request.action -ceq 'block' -and $after.Count -ne 1)) { exit 22 }
    exit 0
} catch { exit 22 }
"""


def _system_directory():
    import ctypes
    buffer = ctypes.create_unicode_buffer(32768)
    api = ctypes.WinDLL("kernel32", use_last_error=True).GetSystemDirectoryW
    api.argtypes, api.restype = [ctypes.c_wchar_p, ctypes.c_uint], ctypes.c_uint
    size = api(buffer, len(buffer))
    if not 0 < size < len(buffer):
        raise OSError("System directory unavailable")
    return Path(buffer.value)


def helper_main(arguments, *, target_provider=packaged_executable, runner=subprocess.run, system_directory=_system_directory):
    """Fixed elevated entrypoint, before config, Qt, audio or app services."""
    if len(arguments) != 1 or arguments[0] not in ("block", "remove"):
        return 20
    target = target_provider()
    if target is None:
        return 20
    try:
        powershell = system_directory() / "WindowsPowerShell/v1.0/powershell.exe"
        command = [str(powershell), "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                   "-EncodedCommand", base64.b64encode(_MANAGE_SCRIPT.encode("utf-16-le")).decode("ascii")]
        response = runner(command, input=json.dumps({"program": str(target), "name": rule_name(target), "action": arguments[0]}),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
        return response.returncode if response.returncode in _EXITS else 22
    except Exception:
        return 22


def _elevated_launch(program, action):
    """Own and close the runas process handle; UAC cancellation is a normal result."""
    import ctypes
    from ctypes import wintypes

    class ExecuteInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ole = ctypes.OleDLL("ole32")
    ole.CoInitializeEx.argtypes, ole.CoInitializeEx.restype = [ctypes.c_void_p, wintypes.DWORD], ctypes.c_long
    ole.CoUninitialize.argtypes, ole.CoUninitialize.restype = [], None
    initialized = ole.CoInitializeEx(None, 0x2 | 0x4) in (0, 1)
    shell.ShellExecuteExW.argtypes, shell.ShellExecuteExW.restype = [ctypes.POINTER(ExecuteInfo)], wintypes.BOOL
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes, kernel.GetExitCodeProcess.restype = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
    info = ExecuteInfo(cbSize=ctypes.sizeof(ExecuteInfo), fMask=0x40 | 0x100 | 0x400,
                       lpVerb="runas", lpFile=str(program), lpParameters=f"{HELPER_ARGUMENT} {action}",
                       lpDirectory=str(program.parent), nShow=0)
    try:
        if not shell.ShellExecuteExW(ctypes.byref(info)):
            return FirewallChange("cancelled" if ctypes.get_last_error() == 1223 else "failed")
        if not info.hProcess:
            return FirewallChange("unknown")
        if kernel.WaitForSingleObject(info.hProcess, 0xFFFFFFFF) != 0:
            return FirewallChange("unknown")
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code)):
            return FirewallChange("unknown")
        return FirewallChange(_EXITS.get(code.value, "failed"))
    finally:
        if info.hProcess:
            kernel.CloseHandle(info.hProcess)
        if initialized:
            ole.CoUninitialize()


def change_firewall(action, *, target_provider=packaged_executable, launcher=_elevated_launch):
    """Call only after an explicit user request; never from app startup or Save."""
    if action not in ("block", "remove"):
        return FirewallChange("unsupported")
    target = target_provider()
    if target is None:
        return FirewallChange("unsupported")
    if not _launch_lock.acquire(blocking=False):
        return FirewallChange("busy")
    try:
        return launcher(target, action)
    except Exception:
        return FirewallChange()
    finally:
        _launch_lock.release()
