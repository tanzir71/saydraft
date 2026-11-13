"""Read-only inspection of this process's enabled outbound block rules."""

import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys


@dataclass(frozen=True)
class FirewallStatus:
    state: str = "unknown"
    matching_rules: int = 0


_SCRIPT = """$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$filters = @(Get-NetFirewallApplicationFilter -PolicyStore ActiveStore | Where-Object {
    [Environment]::ExpandEnvironmentVariables($_.Program) -ieq $request.program
})
$count = 0
foreach ($filter in $filters) {
    $count += @($filter | Get-NetFirewallRule | Where-Object {
        $_.Enabled -eq 'True' -and $_.Direction -eq 'Outbound' -and $_.Action -eq 'Block'
    }).Count
}
[pscustomobject]@{matching_rules = $count} | ConvertTo-Json -Compress
"""


def inspect_firewall(*, program=None, runner=subprocess.run, platform=None):
    if (platform or sys.platform)!="win32":
        return FirewallStatus("unsupported")
    target = str(program or sys.executable)
    windows = os.environ.get("SystemRoot",r"C:\Windows")
    if target.startswith(("\\\\","//")) or windows.startswith(("\\\\","//")):
        return FirewallStatus()
    command = [str(Path(windows)/"System32/WindowsPowerShell/v1.0/powershell.exe"),
        "-NoProfile","-NonInteractive","-WindowStyle","Hidden","-EncodedCommand",
        base64.b64encode(_SCRIPT.encode("utf-16-le")).decode("ascii")]
    try:
        response = runner(command,input=json.dumps({"program":str(Path(target).absolute())}),
            capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=8,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),check=False)
        if response.returncode!=0:
            return FirewallStatus()
        count = json.loads(response.stdout.lstrip("\ufeff"))["matching_rules"]
        if type(count) is not int or not 0<=count<=100000:
            return FirewallStatus()
        return FirewallStatus("found" if count else "absent",count)
    except Exception:
        return FirewallStatus()
