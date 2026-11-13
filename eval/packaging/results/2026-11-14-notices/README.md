# Unsigned package with retained notices

Producer: [`94e4cce`](https://github.com/tanzir71/saydraft/commit/94e4cce651ea54cf0f0c807d5d13f8177e0de801).
The [Package run](https://github.com/tanzir71/saydraft/actions/runs/43506285087)
and [CI run](https://github.com/tanzir71/saydraft/actions/runs/43506285180) passed.
This completes P8.1's unsigned clean-build and installer acceptance.

- Installer: **103,968,660 bytes** (104.0 MB; limit 250,000,000).
  SHA-256: `8e80ac7e3d535f4a0453a782fe5757c02f05f012279cb45a687aabf3d23c14fe`.
- Portable ZIP: **160,033,514 bytes**.
  SHA-256: `7e2fe1c1748003d214aad79c7fcf62e14c743ae094fae0cd86f6c7f124321490`.
- Bundle: **409,303,225 bytes**, **1,417 files**, **1,517 inspected modules**.
- Notices: **38 components**, **506 files**; index SHA-256
  `7f33cd43bd47dcc5f94439d5fdd048ab94be58e4d56ac144b52d6cb882a39964`.
- CI: **3,169 passed / 12 skipped**, rules **556/556**, authored adversarial
  validator **100/100**. This is the producer's count, not a later commit's CI.

The original audit/runtime/installed-runtime/lifecycle/preflight reports,
frozen requirements and compiler-version receipt are retained byte for byte.
`third-party-notices.json` is the exact index from the delivered portable ZIP.
`module-table.json` contains only names/kinds derived from the original Analysis
TOC, recording its source hash. `artifact-verification.json` records independent
local hashing of the downloaded installer/ZIP and checking all 506 notice
payloads inside the ZIP. `index.json` hashes these ten retained evidence files.
The raw TOC and CI log remain in private QA storage; their hashes are retained.

Frozen verification passes before and after installation: full notice hashes,
resources, native imports, fonts, tray images and the Python NetworkGuard.
The module/file audit refuses development/unrelated packages, weights, profile
data, links and the unused Qt PDF/QML/Quick runtimes. The disposable lifecycle
proves default data retention, explicit removal, opt-in autostart, startup-entry
cleanup and preservation of an external junction target. None of these checks
uses owner capture, audio-device enumeration, ASR, foreground data, input or
clipboard access.

The [initial unsigned receipts](../2026-11-14-unsigned/README.md) are retained
with their original missing-notice scope. This rebuild collects supplied wheel
notices and [pinned upstream supplements](../../../../assets/licenses/packaged/README.md),
including Qt, CTranslate2/Intel and FFmpeg dependencies. The complete shipped
index records license files, component versions and source links. Its presence
is an inventory/integrity result; corresponding-source delivery and other
public-release requirements are separate. The `0.0.0.0` compiler ProductVersion
receipt is unusable as compiler-version proof; no exact compiler-version claim
is made.

There is no signing, public release, native-firewall, owner-accuracy or physical
dictation acceptance in these receipts. The installer remains unsigned.
