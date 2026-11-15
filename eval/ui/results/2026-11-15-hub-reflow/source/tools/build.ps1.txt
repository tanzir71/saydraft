#requires -Version 7.0
[CmdletBinding()]
param(
    [string]$Python = (Get-Command python -ErrorAction Stop).Source,
    [string]$OutputRoot,
    [string]$InnoCompiler,
    [string]$PipCache,
    [switch]$SkipInstaller,
    [switch]$AllowDirtySource
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Python = (Resolve-Path -LiteralPath $Python).Path
$GitExecutable = (Get-Command git -ErrorAction Stop).Source
if (-not $OutputRoot) {
    $OutputRoot = Join-Path ([IO.Path]::GetTempPath()) ('Saydraft-build-' + [guid]::NewGuid().ToString('N'))
}
$RunRoot = [IO.Path]::GetFullPath($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputRoot))
$CacheRoot = if ($PipCache) {
    [IO.Path]::GetFullPath($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PipCache))
} else { Join-Path $RunRoot 'pip-cache' }
if ($RunRoot.Equals($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $RunRoot.StartsWith($ProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Choose a fresh output directory outside the source checkout.'
}
if (Test-Path -LiteralPath $RunRoot) { throw 'Build output already exists; retain it and choose a fresh directory.' }
if (-not $SkipInstaller -and -not $InnoCompiler) {
    $Candidates = @((Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'))
    $FoundCompiler = @($Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)
    if ($FoundCompiler.Count -eq 0) { throw 'Install Inno Setup 6/7 or pass -InnoCompiler with its ISCC.exe path.' }
    $InnoCompiler = $FoundCompiler[0]
}
if (-not $SkipInstaller) { $InnoCompiler = (Resolve-Path -LiteralPath $InnoCompiler).Path }

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments, [string]$Stage)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Stage failed with exit code $LASTEXITCODE" }
}

$VersionText = Get-Content -LiteralPath (Join-Path $ProjectRoot 'saydraft\__init__.py') -Raw
$VersionMatch = [regex]::Match($VersionText, '__version__\s*=\s*"(\d+\.\d+\.\d+)"')
if (-not $VersionMatch.Success) { throw 'Could not read the three-part Saydraft __version__.' }
$Version = $VersionMatch.Groups[1].Value
$VersionTuple = ($Version.Split('.') + '0') -join ', '
$SavedEnvironment = @{}
$EnvironmentNames = @('PATH', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONINSPECT', 'PYTHONNOUSERSITE', 'PYINSTALLER_CONFIG_DIR', 'SAYDRAFT_VERSION_FILE',
    'SAYDRAFT_NOTICE_OUTPUT', 'SAYDRAFT_INNO_COMPILER',
    'TEMP', 'TMP', 'LOCALAPPDATA', 'APPDATA', 'USERPROFILE', 'HF_HOME', 'HF_HUB_OFFLINE',
    'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK', 'PYTHONUTF8', 'PYTHONIOENCODING')
foreach ($Name in $EnvironmentNames) { $SavedEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process') }

Push-Location -LiteralPath $ProjectRoot
try {
    $SourceStatus = @(git status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'Git source identity is unavailable.' }
    if ($SourceStatus.Count -gt 0 -and -not $AllowDirtySource) { throw 'Commit the source before a release build.' }
    New-Item -ItemType Directory -Path $RunRoot -ErrorAction Stop | Out-Null
    foreach ($Name in @('temp', 'profile\local', 'profile\roaming', 'profile\home', 'artifacts', 'audit')) {
        New-Item -ItemType Directory -Path (Join-Path $RunRoot $Name) | Out-Null
    }
    $env:PYTHONPATH = ''
    # PyInstaller searches PATH for native dependencies. Desktop launchers can
    # prepend incompatible ICU/VC runtimes; keep only the explicit toolchain and
    # Windows directories, rather than copying unrelated application DLLs.
    $env:PATH = @((Split-Path -Parent $Python), (Join-Path (Split-Path -Parent $Python) 'Scripts'),
        (Split-Path -Parent $GitExecutable), (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
    $env:PYTHONHOME = $env:PYTHONSTARTUP = $env:PYTHONINSPECT = ''
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:TEMP = $env:TMP = Join-Path $RunRoot 'temp'
    $env:LOCALAPPDATA = Join-Path $RunRoot 'profile\local'
    $env:APPDATA = Join-Path $RunRoot 'profile\roaming'
    $env:USERPROFILE = Join-Path $RunRoot 'profile\home'
    $env:HF_HOME = Join-Path $RunRoot 'profile\home\hf'
    $env:HF_HUB_OFFLINE = $env:HF_HUB_DISABLE_TELEMETRY = $env:DO_NOT_TRACK = '1'
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $RunRoot 'pyinstaller-cache'
    $env:SAYDRAFT_NOTICE_OUTPUT = Join-Path $RunRoot 'third-party-notices'
    $env:SAYDRAFT_INNO_COMPILER = if ($SkipInstaller) { '' } else { $InnoCompiler }
    Invoke-Checked -Executable $Python -Arguments @('-c', 'import sys; assert sys.version_info[:2] == (3, 13), "Python 3.13 is required"') -Stage 'Interpreter check'
    $VenvRoot = Join-Path $RunRoot 'venv'
    Invoke-Checked -Executable $Python -Arguments @('-m', 'venv', $VenvRoot) -Stage 'Fresh environment creation'
    $VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
    Invoke-Checked -Executable $VenvPython -Arguments @('-c', 'import sys,site; assert sys.prefix != sys.base_prefix and not site.ENABLE_USER_SITE') -Stage 'Environment isolation check'
    # These pinned dependencies are pure Python and published without wheels.
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', '--isolated', 'install',
        '--disable-pip-version-check', '--only-binary=:all:', '--no-binary=pyperclip,metaphone',
        '--cache-dir', $CacheRoot,
        '-r', (Join-Path $ProjectRoot 'requirements.txt')) -Stage 'Runtime requirements installation'
    & $VenvPython -m pip freeze --all | Set-Content -LiteralPath (Join-Path $RunRoot 'audit\requirements-frozen.txt') -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw 'Dependency receipt failed.' }
    $env:SAYDRAFT_VERSION_FILE = Join-Path $RunRoot 'version_info.txt'
    @"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($VersionTuple), prodvers=($VersionTuple), mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Tanzir Rahman'),
    StringStruct('FileDescription', 'Saydraft offline dictation'),
    StringStruct('FileVersion', '$Version'), StringStruct('ProductVersion', '$Version'),
    StringStruct('InternalName', 'Saydraft'), StringStruct('OriginalFilename', 'Saydraft.exe'),
    StringStruct('ProductName', 'Saydraft')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"@ | Set-Content -LiteralPath $env:SAYDRAFT_VERSION_FILE -Encoding utf8
    $WorkRoot = Join-Path $RunRoot 'work'
    $DistRoot = Join-Path $RunRoot 'dist'
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'PyInstaller', '--clean', '--noconfirm',
        '--workpath', $WorkRoot, '--distpath', $DistRoot, (Join-Path $ProjectRoot 'Saydraft.spec')) -Stage 'PyInstaller'
    $AppDir = Join-Path $DistRoot 'Saydraft'
    $RuntimeReport = Join-Path $RunRoot 'audit\runtime.json'
    $CheckProcess = Start-Process -FilePath (Join-Path $AppDir 'Saydraft.exe') -WindowStyle Hidden -Wait -PassThru `
        -ArgumentList "--verify-package `"$RuntimeReport`""
    if ($CheckProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $RuntimeReport)) { throw 'Frozen runtime verification failed.' }
    $PreflightArgs = @('-m', 'tools.package_audit', '--preflight', '--bundle', $AppDir,
        '--analysis', (Join-Path $WorkRoot 'Saydraft\Analysis-00.toc'), '--artifacts', (Join-Path $RunRoot 'artifacts'),
        '--runtime-report', $RuntimeReport, '--output', (Join-Path $RunRoot 'audit\preflight.json'))
    Invoke-Checked -Executable $VenvPython -Arguments $PreflightArgs -Stage 'Bundle preflight'
    if (-not $SkipInstaller) {
        [Diagnostics.FileVersionInfo]::GetVersionInfo($InnoCompiler).ProductVersion |
            Set-Content -LiteralPath (Join-Path $RunRoot 'audit\inno-version.txt') -Encoding utf8
        Invoke-Checked -Executable $InnoCompiler -Arguments @('/Qp', "/DAppVersion=$Version", "/DAppSource=$AppDir",
            "/O$(Join-Path $RunRoot 'artifacts')", (Join-Path $ProjectRoot 'installer\Saydraft.iss')) -Stage 'Installer compilation'
    }
    $AuditArgs = @('-m', 'tools.package_audit', '--bundle', $AppDir, '--analysis', (Join-Path $WorkRoot 'Saydraft\Analysis-00.toc'),
        '--artifacts', (Join-Path $RunRoot 'artifacts'), '--runtime-report', $RuntimeReport,
        '--output', (Join-Path $RunRoot 'audit\bundle.json'))
    if ($SkipInstaller) { $AuditArgs += '--allow-missing-installer' }
    Invoke-Checked -Executable $VenvPython -Arguments $AuditArgs -Stage 'Bundle audit'
    Write-Host "Built Saydraft $Version. Retained bundle, receipts and artifacts at $RunRoot"
}
finally {
    Pop-Location
    foreach ($Name in $EnvironmentNames) { [Environment]::SetEnvironmentVariable($Name, $SavedEnvironment[$Name], 'Process') }
}
