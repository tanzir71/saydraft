$ErrorActionPreference='Stop'
$TaskRepo='C:/Users/tanzir/Desktop/voice_tray'
$TaskQa='D:/Saydraft-Codex-QA-20261112-01a1cbc7/cleanup-repair-20261117-r1'
$TaskDist=(Resolve-Path -LiteralPath (Join-Path $TaskRepo 'site/dist')).Path
$TaskSource=(git -C $TaskRepo rev-parse HEAD).Trim()
$TaskGitDir=(git -C $TaskRepo rev-parse --absolute-git-dir).Trim()
foreach($TaskPage in @('index.html','download/index.html','changelog/index.html','wispr-flow-alternative/index.html','typeless-alternative/index.html','offline-dictation-windows/index.html','dictation-for-developers/index.html')) {
    $TaskHtml=Get-Content -LiteralPath (Join-Path $TaskDist $TaskPage) -Raw
    if($TaskPage -notin @('index.html','download/index.html','changelog/index.html') -and ($TaskHtml -notmatch '(?i)unsigned' -or $TaskHtml -notmatch '/saydraft/download/')) { throw "Missing preview availability/link: $TaskPage" }
}
[IO.File]::WriteAllBytes((Join-Path $TaskDist '.nojekyll'),[byte[]]@())
$TaskIndex=Join-Path $TaskQa 'pages.index'
if(Test-Path -LiteralPath $TaskIndex){throw 'Publication index already exists'}
$TaskPreviousIndex=[Environment]::GetEnvironmentVariable('GIT_INDEX_FILE','Process')
try {
    [Environment]::SetEnvironmentVariable('GIT_INDEX_FILE',$TaskIndex,'Process')
    git -C $TaskRepo read-tree --empty
    if($LASTEXITCODE -ne 0){throw 'Isolated index failed'}
    git -C $TaskDist --git-dir=$TaskGitDir --work-tree=$TaskDist add -f --all -- .
    if($LASTEXITCODE -ne 0){throw 'Generated staging failed'}
    $TaskTree=(git -C $TaskDist --git-dir=$TaskGitDir --work-tree=$TaskDist write-tree).Trim()
    git -C $TaskRepo fetch origin gh-pages
    if($LASTEXITCODE -ne 0){throw 'Publication parent fetch failed'}
    $TaskParent=(git -C $TaskRepo rev-parse FETCH_HEAD).Trim()
    $TaskMessage=Join-Path $TaskQa 'pages-commit-message.txt'
    [IO.File]::WriteAllText($TaskMessage,('Publish 0.1.1 voice notes and verified download; site source '+$TaskSource))
    $TaskCommit=(git -C $TaskRepo commit-tree $TaskTree -p $TaskParent -F $TaskMessage).Trim()
    if($LASTEXITCODE -ne 0 -or $TaskCommit -notmatch '^[a-f0-9]{40}$'){throw 'Publication commit failed'}
    git -C $TaskRepo push origin ($TaskCommit+':refs/heads/gh-pages')
    if($LASTEXITCODE -ne 0){throw 'Publication push failed'}
} finally {
    [Environment]::SetEnvironmentVariable('GIT_INDEX_FILE',$TaskPreviousIndex,'Process')
}
[ordered]@{source_commit=$TaskSource;pages_commit=$TaskCommit;tree=$TaskTree;parent=$TaskParent;build_local=$true;custom_workflow_dispatched=$false}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $TaskQa 'pages-publication.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $TaskQa 'pages-publication.json')
gh api repos/tanzir71/saydraft/pages --jq '{build_type,source,status,html_url}'
