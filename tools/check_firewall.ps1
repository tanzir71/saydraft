#requires -Version 7.0
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$BuildRoot)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted') {
    throw 'Firewall mutation smoke is restricted to disposable GitHub-hosted runners.'
}
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Disposable runner requires an administrator token; CI never requests UAC.'
}
$BuildRoot = (Resolve-Path -LiteralPath $BuildRoot).Path
$RunnerRoot = (Resolve-Path -LiteralPath $env:RUNNER_TEMP).Path
if (-not $BuildRoot.StartsWith($RunnerRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Frozen firewall smoke requires an owned build under RUNNER_TEMP.'
}
$Audit = Get-Content -LiteralPath (Join-Path $BuildRoot 'audit\bundle.json') -Raw | ConvertFrom-Json
if (-not $Audit.packaging_gate) { throw 'A complete audited package is required.' }
$Exe = (Resolve-Path -LiteralPath (Join-Path $BuildRoot 'dist\Saydraft\Saydraft.exe')).Path
$DataRoot = Join-Path $env:LOCALAPPDATA 'Saydraft'
if (Test-Path -LiteralPath $DataRoot) { throw 'Frozen helper smoke requires a fresh disposable profile.' }
$WitnessName = 'Saydraft.TestWitness.' + [guid]::NewGuid().ToString('N')
$WitnessCreated = $false
$ReportPath = Join-Path $BuildRoot 'audit\firewall-helper.json'
$Report = [ordered]@{ complete=$false; frozen_helper=$true; microphone_used=$false; input_injected=$false;
    owner_clipboard_accessed=$false; helper_created_profile=$null; managed_removed=$false; witness_preserved=$false;
    actual_network_blocking_verified=$false; asr_performed=$false; steps=[ordered]@{} }

function Invoke-Helper {
    param([string]$Action)
    $OwnedProcess = Start-Process -FilePath $Exe -ArgumentList @('--manage-firewall', $Action) `
        -WindowStyle Hidden -PassThru -Wait
    return $OwnedProcess.ExitCode
}
function Get-ProgramRules {
    return @(Get-NetFirewallApplicationFilter -PolicyStore PersistentStore | Where-Object {
        $_.Program -ieq $Exe
    } | Get-NetFirewallRule)
}
try {
    if (@(Get-ProgramRules).Count -ne 0) { throw 'Fresh bundled executable already has firewall rules.' }
    New-NetFirewallRule -PolicyStore PersistentStore -Name $WitnessName -DisplayName $WitnessName `
        -Group 'Saydraft.TestWitness' -Program $Exe -Direction Outbound -Action Allow -Enabled False | Out-Null
    $WitnessCreated = $true
    $Report.steps.block = Invoke-Helper -Action 'block'
    $Report.steps.block_idempotent = Invoke-Helper -Action 'block'
    if ($Report.steps.block -ne 0 -or $Report.steps.block_idempotent -ne 0) { throw 'Frozen block helper failed.' }
    $Managed = @(Get-ProgramRules | Where-Object { $_.Group -ceq 'Saydraft.Managed.v1' })
    if ($Managed.Count -ne 1 -or $Managed[0].Enabled -ne 'True' -or $Managed[0].Direction -ne 'Outbound' -or
        $Managed[0].Action -ne 'Block' -or $Managed[0].Profile -ne 'Any') { throw 'Unexpected frozen block rule.' }
    $Report.steps.managed_count = $Managed.Count
    $ManagedName = $Managed[0].Name
    $OriginalDescription = $Managed[0].Description
    try {
        Set-NetFirewallRule -PolicyStore PersistentStore -Name $ManagedName -Description 'Owned conflict fixture'
        $Report.steps.conflict_block = Invoke-Helper -Action 'block'
        $Report.steps.conflict_remove = Invoke-Helper -Action 'remove'
        if ($Report.steps.conflict_block -ne 21 -or $Report.steps.conflict_remove -ne 21) {
            throw 'Frozen helper did not preserve conflicting ownership.'
        }
    } finally {
        Set-NetFirewallRule -PolicyStore PersistentStore -Name $ManagedName -Description $OriginalDescription
    }
    try {
        Set-NetFirewallRule -PolicyStore PersistentStore -Name $ManagedName -RemoteAddress '127.0.0.1'
        $Report.steps.narrowed_block = Invoke-Helper -Action 'block'
        if ($Report.steps.narrowed_block -ne 21) { throw 'Frozen helper silently rewrote an edited rule.' }
    } finally {
        Set-NetFirewallRule -PolicyStore PersistentStore -Name $ManagedName -RemoteAddress Any
    }
    $RuntimeReport = Join-Path $BuildRoot 'audit\firewall-runtime.json'
    $Runtime = Start-Process -FilePath $Exe -ArgumentList @('--verify-package', ('"' + $RuntimeReport + '"')) `
        -WindowStyle Hidden -PassThru -Wait
    if ($Runtime.ExitCode -ne 0) { throw 'Frozen resources/imports/Python policy failed with the block rule.' }
    $Report.steps.package_verification_under_rule = $true
    $Report.steps.remove = Invoke-Helper -Action 'remove'
    $Report.steps.remove_idempotent = Invoke-Helper -Action 'remove'
    $Report.managed_removed = @(Get-ProgramRules | Where-Object { $_.Group -ceq 'Saydraft.Managed.v1' }).Count -eq 0
    $RemainingWitness = @(Get-ProgramRules | Where-Object { $_.Name -ceq $WitnessName -and $_.Group -ceq 'Saydraft.TestWitness' })
    $Report.witness_preserved = $RemainingWitness.Count -eq 1 -and $RemainingWitness[0].Enabled -eq 'False'
    $Report.helper_created_profile = Test-Path -LiteralPath $DataRoot
    $Report.complete = $Report.steps.remove -eq 0 -and $Report.steps.remove_idempotent -eq 0 -and
        $Report.managed_removed -and $Report.witness_preserved -and -not $Report.helper_created_profile
    if (-not $Report.complete) { throw 'Frozen helper final-state checks failed.' }
} finally {
    $Report.steps.cleanup = Invoke-Helper -Action 'remove'
    if ($WitnessCreated) {
        Get-NetFirewallRule -PolicyStore PersistentStore -Name $WitnessName | Where-Object {
            $_.Group -ceq 'Saydraft.TestWitness'
        } | Remove-NetFirewallRule -Confirm:$false
    }
    $Report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding utf8
}
