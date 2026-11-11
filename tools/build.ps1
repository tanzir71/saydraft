$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$InitPath = Join-Path $ProjectRoot "saydraft\__init__.py"
$VersionMatch = Select-String -Path $InitPath -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $VersionMatch) {
    throw "Could not read __version__ from $InitPath"
}
$Version = $VersionMatch.Matches[0].Groups[1].Value
$VersionParts = @($Version.Split(".") + @("0", "0", "0", "0"))[0..3] | ForEach-Object { [int]$_ }

$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
$AppDir = Join-Path $DistDir "Saydraft"
$VersionFile = Join-Path $BuildDir "version_info.txt"
$EntryFile = Join-Path $BuildDir "saydraft_entry.py"

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

@"
from saydraft.main import main
raise SystemExit(main())
"@ | Set-Content -Path $EntryFile -Encoding UTF8

@"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($VersionParts[0]), $($VersionParts[1]), $($VersionParts[2]), $($VersionParts[3])),
    prodvers=($($VersionParts[0]), $($VersionParts[1]), $($VersionParts[2]), $($VersionParts[3])),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Saydraft'),
          StringStruct('FileDescription', 'Saydraft offline dictation'),
          StringStruct('FileVersion', '$Version'),
          StringStruct('InternalName', 'Saydraft'),
          StringStruct('OriginalFilename', 'Saydraft.exe'),
          StringStruct('ProductName', 'Saydraft'),
          StringStruct('ProductVersion', '$Version')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Path $VersionFile -Encoding UTF8

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name Saydraft `
    --icon "assets\tray\mic_idle.ico" `
    --version-file $VersionFile `
    --paths $ProjectRoot `
    --add-data "saydraft\models\manifest.json;saydraft\models" `
    --collect-submodules faster_whisper `
    --collect-binaries ctranslate2 `
    --collect-data ctranslate2 `
    --collect-submodules sherpa_onnx `
    --collect-binaries sherpa_onnx `
    --hidden-import PySide6.QtSvg `
    --hidden-import _webrtcvad `
    --exclude-module torch `
    --exclude-module transformers `
    --exclude-module sklearn `
    --exclude-module scipy `
    --exclude-module pandas `
    --exclude-module django `
    --exclude-module PIL `
    --exclude-module pygame `
    --exclude-module yt_dlp `
    $EntryFile

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$ExternalAssets = Join-Path $ProjectRoot "dist\Saydraft\assets"
$ExternalModels = Join-Path $ProjectRoot "dist\Saydraft\models"
if (Test-Path $ExternalAssets) {
    Remove-Item -LiteralPath $ExternalAssets -Recurse -Force
}
Copy-Item -Path (Join-Path $ProjectRoot "assets") -Destination $ExternalAssets -Recurse -Force
New-Item -ItemType Directory -Force -Path $ExternalModels | Out-Null

Write-Host "Built Saydraft $Version at $AppDir"
