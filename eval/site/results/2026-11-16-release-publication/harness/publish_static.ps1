$ErrorActionPreference='Stop'
$taskRepo='C:/Users/tanzir/Desktop/voice_tray'
$taskQa='D:/Saydraft-Codex-QA-20261112-01a1cbc7/release-publication-20261116-r1'
$taskDist=(Resolve-Path -LiteralPath ($taskRepo+'/site/dist')).Path
foreach ($taskPage in @('index.html','download/index.html','changelog/index.html')) {
    if (-not (Test-Path -LiteralPath (Join-Path $taskDist $taskPage))) { throw 'Expected static page missing' }
}
[IO.File]::WriteAllBytes((Join-Path $taskDist '.nojekyll'),[byte[]]@())
$taskSource=(git -C $taskRepo rev-parse HEAD).Trim()
$taskGitDir=(git -C $taskRepo rev-parse --absolute-git-dir).Trim()
$taskIndex=Join-Path $taskQa 'pages.index'
if (Test-Path -LiteralPath $taskIndex) { throw 'Retain the previous publication index and choose a fresh one' }
$env:GIT_INDEX_FILE=$taskIndex
git -C $taskRepo read-tree --empty
if ($LASTEXITCODE -ne 0) { throw 'Cannot create isolated publication index' }
git -C $taskDist --git-dir=$taskGitDir --work-tree=$taskDist add -f --all -- .
if ($LASTEXITCODE -ne 0) { throw 'Cannot stage generated site' }
$taskTree=(git -C $taskDist --git-dir=$taskGitDir --work-tree=$taskDist write-tree).Trim()
$taskOld=git -C $taskRepo ls-remote origin refs/heads/gh-pages
$taskMessage=Join-Path $taskQa 'pages-commit-message.txt'
[IO.File]::WriteAllText($taskMessage,('Publish unsigned Windows preview; site source '+$taskSource))
$taskArgs=@('-C',$taskRepo,'commit-tree',$taskTree,'-F',$taskMessage)
if ($taskOld) { $taskParent=$taskOld.Split()[0]; git -C $taskRepo fetch origin gh-pages; if ($LASTEXITCODE -ne 0) { throw 'Cannot fetch publication parent' }; $taskArgs+=@('-p',$taskParent) }
$taskCommit=(& git @taskArgs).Trim()
if ($LASTEXITCODE -ne 0 -or $taskCommit -notmatch '^[a-f0-9]{40}$') { throw 'Cannot create site commit' }
git -C $taskRepo push origin ($taskCommit+':refs/heads/gh-pages')
if ($LASTEXITCODE -ne 0) { throw 'Cannot push generated site' }
Remove-Item Env:GIT_INDEX_FILE
@{source_commit=$taskSource;pages_commit=$taskCommit;tree=$taskTree;files=@(Get-ChildItem -LiteralPath $taskDist -File -Recurse).Count;build_local=$true;custom_workflow_dispatched=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskQa 'pages-publication.json') -Encoding utf8
gh api --method PUT repos/tanzir71/saydraft/pages --input (Join-Path $taskQa 'pages-config.json')
if ($LASTEXITCODE -ne 0) { throw 'Cannot configure Pages publishing source' }
gh api repos/tanzir71/saydraft/pages --jq '{build_type,source,status,html_url}' | Set-Content -LiteralPath (Join-Path $taskQa 'pages-after.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $taskQa 'pages-publication.json')
Get-Content -LiteralPath (Join-Path $taskQa 'pages-after.json')
