# Prepared legacy-site transition

This is a reviewable G9 candidate, not the current root page or a deployment.
`index.html` displays “VoiceTray is now Saydraft”, links to the current project
and provides the canonical Saydraft URL. It uses approved paper/ink colors,
has no scripts, remote fonts, analytics or automatic redirect, and keeps creator
credit. The Vercel project and `vercel.json` are retained.

The original plan §0.2 reserves G9 for an owner decision. After that approval,
from a clean checkout, the prepared script performs the required real `git mv`
of root `index.html` and `demo/` into `_archive/site-v1/`, checks their original
bytes, and copies the reviewed banner to root. It validates absolute paths
before the directory move. `vercel.json` and `.vercelignore` must remain byte
identical. The archive is history/reference; it is not the Pages build source.

```powershell
./docs/launch/legacy-site/apply-transition.ps1 -Repository D:/path/to/saydraft
```

Review the resulting Git diff and validate the banner before committing/pushing.
The script neither commits, pushes nor deploys. A source change alone does not
prove the old URL serves the banner; P9.7 acceptance requires a later HTTP check.
P9.1 also retains its branch-workflow preview gate, which is not run under the
owner's current local-only/no-Actions instruction. The `/demo/` port is independently
implemented in Astro and must be validated with the normal website checks.

An unauthenticated public request to `https://voicetray-offline.vercel.app/`
on 15 November returned HTTP 402. Its page body and banner were not verified.
The prepared source and isolated fixture do not establish P9.7 live acceptance;
that requires a later successful hosted-page check. No hosting setting changed.
