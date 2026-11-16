# Local build retention

The owner stopped all VM work on 16 November 2026 because storage is limited and
requested cleanup of past builds. Do not download VM tools/media or prepare disks.

The local inventory identified **24,751,600,064 bytes (23.05 GiB)** of obsolete
package output, including the stopped partial QEMU download. The cleanup script
passed its preview run; automatic approval review rejected deletion as
`blocked by policy`, without a more specific reason. No deletion is claimed.
The owner-run script and full target inventory are retained in
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/roadmap-resumption-20261116-r1/`:

- `cleanup-past-builds.ps1`: preview by default; `-Apply` removes the exact
  allowlisted paths. It checks absolute paths and rejects reparse points before
  deletion, verifies the retained release ZIP, and writes `cleanup-completed.json`
  only after successful removal.
- `cleanup-plan.json`, `build-inventory.json` and `cleanup-preview.log`: selected
  paths, logical sizes and the completed dry run.

The script preserves all source/worktrees, model weights, profiles and audit/test
receipts. It retains the published `12bc27f` ZIP and extracted app under
`delivery-brand-package-20261116-r1`, plus the existing
`app-ui-v2-package-20261116-r1/venv` used for local regression checks. The retained
ZIP SHA-256 is
`b24ca638e91035c35029b67577b7d62859e22904618a9fa7e982a330ec40901f`.

For future builds, keep one current portable and one reusable test environment.
Retain source commits, dependency/build metadata, hashes and test receipts rather
than every generated environment, PyInstaller work tree and superseded package.
Remove old generated outputs after validating their replacement; do not delete
models or profiles as build cleanup. Rebuild the desktop app only when app or
packaging changes require it. Website/documentation changes use the existing site
dependencies and do not require another desktop package.

The full roadmap and unexecuted acceptance remain in the
[delivery handover](DELIVERY_HANDOVER.md). Storage cleanup does not qualify native
Windows behavior, multilingual accuracy or experimental model quality.
