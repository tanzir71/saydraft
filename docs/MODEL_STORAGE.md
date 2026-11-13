# Models, tiers and disk usage

Settings → Models preserves the existing explicit, licensed download/resume
controls and adds a saved performance tier and background storage inventory.
Selecting a tier, language or model never starts a download.

`app.tier` defaults to `auto`; old and invalid preferences migrate to Auto. Auto
uses the latest local performance report, or stays Pending without a measurement.
Lite, Standard and Pro are explicit overrides. The selected tier drives the Home
chip, cleanup recommendation and live-preview eligibility; English restrictions
still apply. The immutable benchmark report keeps its original measurements and
recommendation. An override makes no claim that the machine meets a speed target.

Changing the tier alone preserves individual model, backend and cleanup choices.
**Use tier defaults** stages these choices for review before the shared Save:

| Tier | Speech | Cleanup |
| --- | --- | --- |
| Lite | Whisper base, manual routing, CPU/int8 | Rules only |
| Standard | Parakeet v3 with automatic language routing, CPU/int8 | Manifest 0.8B candidate |
| Pro | Parakeet v3 with automatic language routing, CPU/int8 | Manifest 2B candidate |

Pins and per-app routing preferences survive. Bengali/Arabic pins can therefore
select the shared All languages model through automatic routing. An existing
installed cleanup package is reused in place; otherwise the staged GGUF path
points to managed storage. A measured Vulkan capability suggests that backend
for the cleanup candidates; CPU remains the fallback. The user reviews sizes,
licenses and choices and explicitly uses Download / Resume for missing files.
The rules fallback, live cleanup deadlines and default-off Labs flags are unchanged.
The larger P4 model/default bake-off and native tier latency acceptance remain open.

## Storage inspection

Opening Models or choosing Refresh storage runs inspection off the GUI thread.
Completed, failed and paused speech/cleanup/VAD setup refresh the inventory.
Refresh requests arriving during a scan are coalesced and replayed afterward.

The app lists catalogued folders in profile storage and read-only portable roots,
including identifiable older revision folders and archived package receipts.
It shows exact paths/revisions, recognized bytes, total logical regular-file sizes,
other retained bytes and drive free space. Logical size is not allocated disk
space. Unknown files, compressed caches, unrecognized per-file archives and
interrupted staging remain in the other/retained total. Reparse-linked or unreadable
entries are excluded and counted explicitly; UNC and reparse roots are not followed.
Hard-linked regular files count toward logical size but remain retained other
data and cannot be removed as declared model payloads.

Inventory reads bounded receipts and file metadata, without hashing multi-GB
weights. **Installed (receipt and sizes)** requires the current catalog's exact
receipt and matching sizes. Other complete receipts and partial folders are
labeled separately. Loading and removal perform their own stronger checks.

## Confirmed manual removal

Remove is available for recognized files in managed app storage. Portable copies
are read-only here. The dialog names the model, revision, exact folder and
recognized size; its read-only details wrap long paths and scroll at larger text
sizes. Remove/Cancel remain visible, with Cancel the initial default.

After confirmation, the backend reserves an idle application and checks the
current configured and cached models again. It protects speech dependencies,
per-app routes, preview, the configured cleanup GGUF and runtime, including
resolved aliases of custom paths. Active dictation, retry, performance checks,
microphone tests and another storage operation refuse removal. Settings changed
mid-operation apply afterward. The shared model-write lease also refuses removal
during download/install; nested model/runtime installation uses the same lease.

The backend accepts only managed roots, rechecks local directory/file identities,
single-link regular files and the confirmation snapshot, and SHA-256 verifies
every declared payload before deleting any file. Changed snapshots/checksums are
preserved and require a fresh review. Matching resume metadata authorizes only
its own `.part` and metadata files. It never follows links or recursively removes
a directory. Unknown files, other versions and caches survive.

The completion receipt is removed first. A later file lock/error stops deletion
and reports exact completed counts/bytes and the remaining error; the leftover
folder cannot appear installed through a stale completion marker. Only an empty
package folder is removed afterward. Nothing automatically prunes old versions.

## Versioned installation layout

All new app downloads use `%LOCALAPPDATA%\Saydraft\models\<id>\<version>\`,
including speech, language detection, VAD, preview, cleanup GGUFs and runtimes.
Every bundled catalog entry records an explicit `version` equal to its immutable
`revision` pin. Mutable aliases, reserved names and escaping version paths fail
validation. Older schema-1 descriptors without `version` use their revision.

Discovery checks the current canonical pin, then the earlier role-based layout
within each profile/portable root. Complete legacy installations remain usable
in place; explicit setup can reuse a SHA-256-verified legacy package without a
transfer or migration. Custom GGUF paths stay valid. Damaged current copies do
not hide a complete compatible legacy copy.

File downloads resume in the sibling `<version>.download` directory. The complete
receipt and every payload must verify before a sibling-directory rename publishes
the version. Archive packages keep compressed downloads in the model's
`_packages/<version>/` directory and extract into unique `.installing` siblings.
Space preflight is read-only and budgets both unpacked payloads and any missing
compressed cache, with the existing free-space reserve. It never creates an empty
live version directory. Linked staging/cache paths and writable hard-linked
partials are refused before transfer.

Different pins coexist. Repairing a changed current directory preserves the whole
previous directory under `_archive`; publication failure restores it when the
destination remains available. Unknown files and older pins are never pruned.
Earlier partial transfers remain untouched in their original locations; new
versioned transfers use their own resumable staging rather than moving or copying
the older attempts. The inventory lists compatible legacy/current packages and
identifiable older pins of catalogued IDs. Staging and compressed caches remain
retained other bytes. Current/cached model protection covers both layouts.

No owner model/artifact folder is migrated or removed to implement or test this
transition. A later release may retire catalog IDs; unrecognized data remains
retained rather than acquiring an automatic deletion policy.

## Verification scope

Isolated tiny fixtures cover disk accounting, bounded/invalid receipts, current
and older versions, explicit cancellation, preserved unknown/resume files,
checksum/snapshot refusal, portable/external paths, hard links, junctions,
download leases, partial unlink failures, worker reservation and deferred Save.
Qt checks cover the actual confirmation/default and refreshed saved preferences.
Versioning tests enumerate all 13 bundled entries and cover immutable version
validation, legacy reuse/hash fallback, hidden partial publication, Range resume,
atomic rollback, separate archive caches and read-only peak-space checks. Real
owned Qt/worker composition removes an older fixture version while preserving
current and legacy copies. Storage labels use word-boundary wrapping with a
fallback for long unbroken paths; glyph-width checks verify the full plain text
fits rather than relying only on label height.
Owned offscreen renders exercise both themes, two window sizes, 16/22 px text and
1×/2× density with explicit no-capture/no-clipboard/no-removal adapters.

No owner model is removed for QA. Native owner desktop/removal acceptance remains
unrun under the existing desktop-control stop. P6.3 also retains Notes producers
and packaged firewall requirements; full gallery/accessibility acceptance remains
separate.
