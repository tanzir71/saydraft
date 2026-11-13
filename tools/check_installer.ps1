#requires -Version 7.0
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$BuildRoot)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$BuildRoot = (Resolve-Path -LiteralPath $BuildRoot).Path
$Audit = Get-Content -LiteralPath (Join-Path $BuildRoot 'audit\bundle.json') -Raw | ConvertFrom-Json
if (-not $Audit.packaging_gate) { throw 'Installer smoke requires an audited, clean-source package.' }
$Installers = @(Get-ChildItem -LiteralPath (Join-Path $BuildRoot 'artifacts') -Filter 'Saydraft-*-Setup.exe')
if ($Installers.Count -ne 1) { throw 'Expected one installer.' }
$InstallRoot = Join-Path $BuildRoot 'installed-smoke'
$DataRoot = Join-Path ([IO.Path]::GetFullPath($env:LOCALAPPDATA)) 'Saydraft'
$RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if ((Test-Path -LiteralPath $InstallRoot) -or (Test-Path -LiteralPath $DataRoot)) {
    throw 'Use a disposable Windows account with no existing Saydraft installation or data.'
}
$ExistingRun = Get-ItemProperty -LiteralPath $RunKey -Name Saydraft -ErrorAction SilentlyContinue
if ($null -ne $ExistingRun) { throw 'An existing Saydraft startup entry must be preserved; use a fresh account.' }

function Invoke-OwnedProcess {
    param([string]$Executable, [string]$Arguments)
    $OwnedProcess = Start-Process -FilePath $Executable -ArgumentList $Arguments -WindowStyle Hidden -PassThru -Wait
    if ($OwnedProcess.ExitCode -ne 0) { throw "Owned installer process failed with exit code $($OwnedProcess.ExitCode)." }
}

$ReportPath = Join-Path $BuildRoot 'audit\installer-smoke.json'
$Report = [ordered]@{ complete=$false; default_keeps_data=$false; explicit_removes_data=$false;
    autostart_default_off=$false; autostart_opt_in=$false; startup_removed=$false;
    custom_models_preserved=$false; junction_target_preserved=$false;
    microphone_used=$false; input_injected=$false; owner_clipboard_accessed=$false }
try {
    Invoke-OwnedProcess -Executable $Installers[0].FullName -Arguments "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=`"$InstallRoot`" /LOG=`"$BuildRoot\audit\install-keep.log`""
    $Exe = Join-Path $InstallRoot 'Saydraft.exe'
    if (-not (Test-Path -LiteralPath $Exe)) { throw 'Installer did not create the application.' }
    $Report.autostart_default_off = $null -eq (Get-ItemProperty -LiteralPath $RunKey -Name Saydraft -ErrorAction SilentlyContinue)
    Invoke-OwnedProcess -Executable $Exe -Arguments "--verify-package `"$BuildRoot\audit\installed-runtime.json`""
    New-Item -ItemType Directory -Path (Join-Path $DataRoot 'models') | Out-Null
    $Fixture = 'Saydraft installer lifecycle fixture'
    $FixturePaths = @('config.json', 'history.db', 'notes.txt', 'models\fixture.bin')
    foreach ($Relative in $FixturePaths) { [IO.File]::WriteAllText((Join-Path $DataRoot $Relative), $Fixture) }
    Invoke-OwnedProcess -Executable (Join-Path $InstallRoot 'unins000.exe') -Arguments "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=`"$BuildRoot\audit\uninstall-keep.log`""
    if (Test-Path -LiteralPath $Exe) { throw 'Uninstall left the application executable installed.' }
    $Report.default_keeps_data = @($FixturePaths | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $DataRoot $_)) -or
        [IO.File]::ReadAllText((Join-Path $DataRoot $_)) -ne $Fixture
    }).Count -eq 0
    Invoke-OwnedProcess -Executable $Installers[0].FullName -Arguments "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /TASKS=autostart /DIR=`"$InstallRoot`" /LOG=`"$BuildRoot\audit\install-remove.log`""
    $Startup = Get-ItemProperty -LiteralPath $RunKey -Name Saydraft -ErrorAction Stop
    $Report.autostart_opt_in = $Startup.Saydraft -eq ('"' + $Exe + '"')
    $Outside = Join-Path $BuildRoot 'custom-model-fixture'
    New-Item -ItemType Directory -Path $Outside | Out-Null
    [IO.File]::WriteAllText((Join-Path $Outside 'keep.txt'), $Fixture)
    $Link = Join-Path $DataRoot 'external-model-link'
    # Both paths are explicitly owned fixtures. Only the app-data root is removed;
    # the external witness must survive the uninstaller's reparse-point handling.
    if (-not ([IO.Path]::GetFullPath($Outside).StartsWith($BuildRoot + '\', [StringComparison]::OrdinalIgnoreCase)) -or
        -not ([IO.Path]::GetFullPath($Link).StartsWith($DataRoot + '\', [StringComparison]::OrdinalIgnoreCase))) {
        throw 'Installer fixture paths escaped their expected roots.'
    }
    New-Item -ItemType Junction -Path $Link -Target $Outside | Out-Null
    Invoke-OwnedProcess -Executable (Join-Path $InstallRoot 'unins000.exe') -Arguments "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /REMOVEDATA=1 /LOG=`"$BuildRoot\audit\uninstall-remove.log`""
    $Report.explicit_removes_data = -not (Test-Path -LiteralPath $DataRoot)
    $Report.startup_removed = $null -eq (Get-ItemProperty -LiteralPath $RunKey -Name Saydraft -ErrorAction SilentlyContinue)
    $Report.junction_target_preserved = [IO.File]::ReadAllText((Join-Path $Outside 'keep.txt')) -eq $Fixture
    $Report.custom_models_preserved = $Report.junction_target_preserved
    $Report.complete = $Report.default_keeps_data -and $Report.explicit_removes_data -and
        $Report.autostart_default_off -and $Report.autostart_opt_in -and $Report.startup_removed -and
        $Report.junction_target_preserved
    if (-not $Report.complete) { throw 'Installer lifecycle checks did not pass.' }
}
finally {
    $Report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding utf8
}
