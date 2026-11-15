param([Parameter(Mandatory = $true)][string]$Repository)
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path -LiteralPath $Repository).ProviderPath
$rootPath = [IO.Path]::GetFullPath($repoPath).TrimEnd([IO.Path]::DirectorySeparatorChar)
$gitRoot = (& git -C $rootPath rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($gitRoot) -ne $rootPath) { throw 'Use the repository root.' }
if (& git -C $rootPath status --porcelain) { throw 'Commit or preserve existing changes before this transition.' }
$archive = [IO.Path]::GetFullPath((Join-Path $rootPath '_archive/site-v1'))
$candidate = Join-Path $rootPath 'docs/launch/legacy-site/index.html'
# Validate every final move target before invoking git, including the recursive demo move.
foreach ($relative in @('index.html', 'demo', '_archive/site-v1/index.html', '_archive/site-v1/demo')) {
    $resolved = [IO.Path]::GetFullPath((Join-Path $rootPath $relative))
    if (-not $resolved.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes repository: $relative" }
}
if (Test-Path -LiteralPath $archive) { throw 'The archive already exists; review it before proceeding.' }
foreach ($relative in @('index.html', 'demo/index.html', 'vercel.json', '.vercelignore')) {
    if (-not (Test-Path -LiteralPath (Join-Path $rootPath $relative) -PathType Leaf)) { throw "Missing legacy input: $relative" }
}
if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw 'Missing reviewed banner.' }
$indexHash = (Get-FileHash -LiteralPath (Join-Path $rootPath 'index.html') -Algorithm SHA256).Hash
$demoHash = (Get-FileHash -LiteralPath (Join-Path $rootPath 'demo/index.html') -Algorithm SHA256).Hash
$vercelHash = (Get-FileHash -LiteralPath (Join-Path $rootPath 'vercel.json') -Algorithm SHA256).Hash
$ignoreHash = (Get-FileHash -LiteralPath (Join-Path $rootPath '.vercelignore') -Algorithm SHA256).Hash
New-Item -ItemType Directory -Path $archive | Out-Null
& git -C $rootPath mv -- index.html _archive/site-v1/index.html
if ($LASTEXITCODE -ne 0) { throw 'Could not archive legacy index.' }
& git -C $rootPath mv -- demo _archive/site-v1/demo
if ($LASTEXITCODE -ne 0) { throw 'Could not archive legacy demo.' }
Copy-Item -LiteralPath $candidate -Destination (Join-Path $rootPath 'index.html')
if ((Get-FileHash -LiteralPath (Join-Path $archive 'index.html') -Algorithm SHA256).Hash -ne $indexHash) { throw 'Archived landing bytes changed.' }
if ((Get-FileHash -LiteralPath (Join-Path $archive 'demo/index.html') -Algorithm SHA256).Hash -ne $demoHash) { throw 'Archived demo bytes changed.' }
if ((Get-FileHash -LiteralPath (Join-Path $rootPath 'vercel.json') -Algorithm SHA256).Hash -ne $vercelHash) { throw 'Vercel configuration changed.' }
if ((Get-FileHash -LiteralPath (Join-Path $rootPath '.vercelignore') -Algorithm SHA256).Hash -ne $ignoreHash) { throw 'Vercel exclusions changed.' }
[ordered]@{ archived_via_git_mv = $true; legacy_index_sha256 = $indexHash; legacy_demo_sha256 = $demoHash; vercel_config_unchanged = $true; hosting_deployed = $false } | ConvertTo-Json
