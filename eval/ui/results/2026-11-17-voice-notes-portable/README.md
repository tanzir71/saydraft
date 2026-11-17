# Unsigned 0.1.1 portable and public verification

Clean source: **`dcfab880d1896f1fbdb32be7e34387c2b46b0ad5`**.
[Published preview](https://github.com/tanzir71/saydraft/releases/tag/v0.1.1-preview.20261117).

Artifact: `Saydraft-0.1.1-win-x64.zip`, **157,322,503 bytes**.
SHA-256: `479938ff19281bacbbb9e9da5860cf7e56b174292a68fd5cc4f76ed6fd29a95f`.
Local retained build:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/cleanup-note-package-20261117-r1`.

The existing clean worktree was advanced to that exact committed source, then
`tools/build.ps1` created a fresh isolated environment/output with the pinned
requirements, shared pip cache and `-SkipInstaller`. No dirty-source override,
model download, VM work, or normal app launch was used. The actual hidden EXE's
`--verify-package` passes, including the approved UI Automation initialization
check. Its receipt reports no microphone, device enumeration, foreground read,
clipboard access or native input injection.

Independent read/hash verification compares all **1,440** actual disk and ZIP
payloads with the complete audited set, safe unique ZIP paths and exact artifact
digest. Structural code comparison checks **92** embedded modules against Git,
including every UI module, app/controller, worker/container, NoteStore, comma
guard and cleanup admission. Both theme stylesheets and brand artwork match.
The 40 notice components / 511 notice files remain intact. A further 23 guarded
packaging source/notice checks pass. The separate
[262-case repair record](../2026-11-17-voice-notes/README.md) covers the behavior.

`public-release.json` records an unauthenticated full streaming read of the
uploaded ZIP, SHA256SUMS and BUILD_INFO.json. Every size and SHA-256 matches the
local original; the tag targets the exact source and is a public prerelease.
The initial upload invocation refused a missing BUILD_INFO path before publishing;
explicit metadata was then created separately and attached to the successful
release. No built ZIP bytes were changed. Website publication has its own record.

This qualifies the selected unsigned portable and its tested changes. The
signed installer/full packaging parity gates remain false in the original audit.
No new physical microphone/F10/insertion acceptance, owner/multilingual accuracy,
hardware tier or end-to-end latency pass is claimed. All original receipts and
producers here are pinned by `manifest.json`; no binary or model weights are
duplicated in the repository.
