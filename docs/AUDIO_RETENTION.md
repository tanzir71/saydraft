# Saved-recording retention

Settings → Privacy keeps recording retention off by default. Existing opt-in
profiles migrate to Keep forever. `recording.audio_retention_days` is zero for
forever, or 1–3650 for a time limit; `recording.retain_audio` still controls new
capture retention. Turning retention off preserves existing files and remembers
the staged time limit. Merely editing controls starts no cleanup. Shared Save
applies the policy; an applied time limit enables background expiry immediately
and every fifteen minutes. Clean up expired recordings now uses only the exact
saved policy, never an unsaved draft.

Expiry reads 200 metadata rows at a time, through a fixed starting ID ceiling.
It does not load raw/cleaned text. A valid saved timestamp and the file's last
modification time must both precede the UTC cutoff. A later recognition retry
does not reset the original recording's age. Invalid/future dates, recent file
changes and active retry leases preserve the recording for a later pass.

Only indexed UUID-named `.wav` files directly inside the app's local audio
directory qualify. External/UNC paths, custom names, unindexed files, partial
writes, hardlinks, reparse entries and linked audio roots stay untouched. The
resolved parent plus file/directory identities are rechecked immediately before
unlinking one managed entry. There is no recursive deletion. Retry/load and
expiry share a per-root lock across AudioStore instances; a complete History
retry holds its lease through persistence. Capture of a new recording uses a new
UUID and is protected by its recent timestamp.

Successful expiry clears `audio_path` on all History versions sharing that file.
Raw/cleaned text, IDs, timestamps, model/style provenance and daily statistics
remain unchanged. Missing eligible files can have their stale audio links cleared.
An unlink failure preserves the reference and file. If the file was removed but
the metadata write failed, feedback counts the removal and failure; the next
sweep repairs the stale link. Cancellation is checked before deletion. Once a
file is removed, clearing its references finishes even if cancellation arrives.
This is controlled expiry, not a secure-erasure guarantee or removal of other
files/backups.

SQLite remains schema version 2. An additive partial index on non-null audio
paths makes clearing shared references efficient. Existing databases receive a
consistent backup before that missing index is added. No existing table, column,
transcript, owner extension or statistics row is removed by migration.

Each applied configuration owns one lazy background worker and daemon timer.
Off/forever create no worker or timer and touch no audio files. Requests are
serialized; Settings replacement and shutdown cancel old work without a GUI
join. Policy/generation checks reject stale feedback. Already committed metadata
changes can still refresh History after an owner retires. Feedback contains
counts, not paths, dictated text or provider exception details.

## Verification

```powershell
python -m pytest tests/test_audio_retention.py tests/test_audio_retention_owner.py tests/test_firewall_status.py tests/test_privacy_page.py -q
```

Fifty-five new cases cover real owned WAV/SQLite expiry, complete text/statistics
preservation, shared retry versions, date boundaries, current file changes,
missing links, metadata repair, cancellation, unavailable paths, hardlinks/reparse
guards, concurrent retry leases, metadata paging, inactive policies, scheduling/
shutdown, applied-policy gating, queued Qt composition and firewall query scope.
All test audio and deleted entries are public fixtures in isolated temporary
profiles. No owner recordings, model/artifact directories, clipboard, microphone,
desktop input or playback are touched.

Owned offscreen rendering covers off/forever/days/working/result states in both
themes, 1080×720/880×600 sizes, 16/22 px text and 1×/2× density (80 PNGs). Exact
sizes, wrapped-label height and zero horizontal overflow pass; selected final
states are inspected. Full gallery, accessibility, packaged firewall installation
and native network-boundary acceptance remain separate requirements.

Final full verification passes 2622 tests with five explicit optional/native
skips. Rules pass 556/556, adversarial validation passes 100/100, Ruff and all
12 generated token outputs pass. The real Windows read-only rule helper also
completes successfully for this source Python process and reports zero matching
enabled outbound block rules; only its state/count are retained in QA storage.
That observation does not establish helper/profile/address coverage or a packaged
firewall boundary, and no OS rule was changed.
