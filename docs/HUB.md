# Saydraft Hub

P6.3 remains in progress. The app now uses one persistent 1080×720 Hub with an
880×600 minimum and Home, History, Dictionary, Snippets, Style, Notes and
Settings in its left rail. Tray actions and Bar error fixes route into that
window. Closing/reopening retains the page objects and staged edits.

## Shared pages and Home

`ui/settings_page.py` and `ui/history_page.py` contain the migrated QWidget
controls. The separate window modules/classes are retired. Configuration
collection, validation, revision-aware Dictionary saving, snippets/profiles,
autostart, explicit downloads/pause, style preview and History actions retain
their existing behavior. The app's older injected factory/attribute names remain
as adapter compatibility names; their values are embedded pages.

Dictionary, Snippets and Style are hosted in rail pages.
One shared Save action applies staged values across those pages and Settings.
Settings sections use a named selector, including separate General, Shortcuts
and Privacy sections. Audio retention lives in Privacy and still defaults off.
All sections use scroll containers; larger text does not force the Hub beyond
its minimum size. Closing the Hub pauses each existing download owner.

Home shows the current shortcut as keycaps, local-week word/WPM/time-saved
metrics, model/tier, an Offline status button opening Privacy, and the last five
dictations. Opening a recent row clears an old History filter before selecting
that record. UTC/legacy timestamps display in local time; exports retain the
stored timestamp. Retired keycaps hide before deferred deletion, and unchanged
shortcuts retain their widgets. Original vector icons avoid missing symbol
glyphs and follow theme changes. Six model-label encoding artifacts are fixed;
artifact URLs, hashes, versions, licenses and all other catalog data are unchanged.

Notes currently has an empty state pending the Scratchpad and Notetaker producers.
The full remaining §8.3 features listed below are still outstanding; the shell
and structured editors are not full P6.3 acceptance.

## Dictionary controls

Dictionary now has searchable term, protected-term and replacement-pair lists
with Manual, Learned and Imported source chips. Select a row to update/remove
it, or add a new term/spoken phrase. Shared Save also stages a pending form before
validating the complete edit. Duplicate detection uses NFC and case folding.
Replacement text, including backslashes, stays literal during cleanup. A closed
Advanced JSON editor retains access to owner extension fields and uses the
private selection MIME converter. Learning and Auto-add keep their default-off
configuration and existing eligibility checks.

Import accepts bounded UTF-8 JSON, including a BOM, merges new entries, and keeps
existing spellings and replacement values on conflicts. The summary reports
added, duplicate and conflicting entries. Imports remain staged until shared
Save. Export writes a portable copy of the current staged data, strips internal
learning/import metadata, and refuses the active Dictionary path. The dialog sets
its suffix before overwrite confirmation and writes to the exact selected path.
Atomic replacement failures retain the destination bytes.

Source labels persist in a private import metadata map; they do not contain file
paths or transcripts. Unchanged entries retain their provenance across saves.
Make manual explicitly claims a learned/imported entry; saving that claim retires
the previous learning Undo for that term. Unrelated saves preserve valid learning
receipts, including Undo back to an imported spelling after a case correction.
Pasted private metadata cannot revive receipts or forge imported provenance.

Queued learning results update a clean editor on the GUI thread without opening
a Hub. A draft, invalid JSON or pending form stays intact when the saved Dictionary
changes; an edited stale snapshot refuses Save before applying configuration.
Reload saved Dictionary explicitly discards the draft. Unknown owner fields and
the complete 4 MB payload budget, including private metadata, are preserved.
The compatibility JSON remains the live store; the SQLite Dictionary table still
contains the earlier copy-only migration.

## Snippets controls

Snippets now has a searchable trigger/expansion list, multiline editing, variable
buttons and a private test panel. `{date}` and `{clipboard}` resolve once after
cleanup, with limits and spoken-trigger fallback. The test uses a supplied
clipboard sample and includes pending form edits. Shared Save persists live
snippets in the existing SQLite table, preserving the legacy file and a
pre-adoption database backup. Adoption receipts prevent later legacy imports
from resurrecting deletions. Revision checks refuse changed stale drafts;
unchanged editors keep newer rows. Advanced JSON/legacy text remains available.
See `docs/SNIPPETS.md` for matching, variables, limits, migration and verification.
The shared footer status now wraps at larger text sizes.

## History controls

History now has mutually exclusive raw and changes views. Changes are plain
text: deletions are struck through and insertions use the approved signal/ink
colors plus an underline. Words keep their combining marks and emoji sequences;
whitespace is preserved by the comparison. Entries over 50,000 combined
characters use coarse complete before/after runs to bound comparison work.
The changes display may add a thin visual separator between touching edit runs.
It is a review view, not the source for the Copy/Paste again buttons.

Copy and Paste again explicitly identify raw versus cleaned text and operate
on that stored value. Selecting changes retains the existing private Qt MIME
conversion for copy/drag; no transcript is rendered as HTML. The app/title
metadata label is also explicitly plain text. The expandable “Why this result?”
panel shows speech/cleanup models, cleanup decision, language, style/intensity
and recorded stage timings, and tolerates missing legacy metadata.

Search covers the complete History database, including raw/cleaned text and
app, language, style, model and decision metadata. It uses literal Unicode
substring matching with NFC normalization and case folding; `%`, `_` and
SQL-looking input have no special meaning. Search is limited to 512 characters.
Newer/Older navigation shows at most 200 bounded previews per page, with a
matching range/total. Only the selected row loads its complete text and metadata.
Home links can locate a saved row beyond the first page.

Browsing uses a private, consistent SQLite copy beside the live database.
Incremental online-backup steps release source locks between reads; a test
commits a live dictation between steps. Source connections close after copying,
and the copy is read-only during browsing/export. The source journal mode is
unchanged. The local runtime is SQLite 3.50.4, before the upstream WAL-reset fix;
this change does not enable WAL. Release packaging still needs a qualified
SQLite runtime. See SQLite's [backup API](https://www.sqlite.org/backup.html)
and [WAL-reset advisory](https://www.sqlite.org/wal.html#walreset).

One serial background reader handles snapshots, search, paging and selected-row
details. Debounced requests cancel old work; generation checks discard late
results. Loading clears stale selections and disables their actions. A fresh
snapshot retains the selected row when possible; the Refresh button returns to
the latest page. Paging/search keep the same snapshot until refresh, so new
dictations or live edits cannot move rows between pages.

“Export…” streams every matching entry from that snapshot, newest first,
including entries beyond the displayed page. Both raw and cleaned values are
exported, independently of the selected view. Opening the Save dialog freezes
the query and snapshot even if background work changes the displayed page.

- Markdown uses dynamically sized fenced text blocks, including for metadata,
  so dictated markup and embedded fences stay literal.
- CSV uses UTF-8, quoted fields and CRLF records. Formula-like string cells
  receive a leading apostrophe for spreadsheet use; other strings retain their
  exact text, including commas, quotes and line breaks. Audio paths are omitted.
- A separate background exporter writes one row at a time. Search and paging
  remain available. Cancel export stops before atomic replacement and preserves
  an existing destination; a completed replacement reports success.
- A completed, flushed temporary file replaces the explicitly chosen destination
  atomically. Failed writes/replacement preserve existing bytes and show a
  generic page error. The live database, its sidecars and the export's own
  snapshot cannot be chosen as destinations.

Snapshots stay alive while the reader, page or an export references them. Refresh
does not delete a running export's copy. Unreferenced copies and cancelled partial
copies are removed; abrupt process termination can leave a private copy behind.
Closing the Hub retains its page/workers for reopening; application shutdown or
destruction of the page cancels owned work without joining on the GUI thread.
No transcript, search term or provider error detail is logged by these jobs.

The Save dialog applies its default suffix before normal overwrite confirmation,
including when the format filter changes. The application writes to that exact
selected path and never appends a suffix afterward. This uses Qt's documented
[default suffix](https://doc.qt.io/qt-6/qfiledialog.html#defaultSuffix-prop) and
[default overwrite confirmation](https://doc.qt.io/qt-6/qfiledialog.html#Option-enum).
Offscreen tests inspect the real dialog settings/selected path while replacing
its modal execution; no native desktop dialog is exercised during QA.

The existing safe clipboard recovery, rejected reinsert feedback, dictionary
selection action and retained-audio All languages retry remain wired. Retry
still saves a new review entry without replacing the original or pasting it.

## Home data

`DictationHistoryStore.weekly_stats(today=...)` reads `stats_daily` plus duration
completeness metadata, using local Monday–Sunday dates without loading raw or
cleaned text. It returns dictation/word/speaking-time totals,
average WPM (words ÷ speaking seconds × 60) and estimated time saved against
40 WPM typing, floored at zero. WPM is unknown when there is no speaking-time
measurement. Weeks mixing measured recordings with missing/zero legacy duration
show unknown WPM/time saved, rather than treating unmeasured speaking time as
zero. Existing retry accounting continues to avoid counting one recording twice.

## Verification and remaining work

```powershell
node tools/generate_tokens.mjs --check
python -m pytest tests/test_hub.py tests/test_history_view.py tests/test_history_details_ui.py tests/test_history.py tests/test_history_window.py tests/test_settings_window.py tests/test_native_clipboard_app.py -q
python -m pytest tests/test_history_queries.py tests/test_history_paging_ui.py -q
python -m pytest tests/test_dictionary_page.py tests/test_dictionary_portable.py tests/test_dictionary_store.py -q
```

Tests cover exact reconstruction of both diff inputs, Bengali/Arabic combining
marks, emoji, large entries, literal markup, CSV fields/formulas, atomic failure,
local week/year boundaries, view selection, private MIME, export filtering,
cancel/error feedback and filename/filter precedence. Owned offscreen renders at
880×600 have been inspected in light and dark; the toolbar/controls leave a
155-pixel transcript viewport with result details expanded. List selection and
focus colors now come from the shared generated light/dark themes. No owner
clipboard, microphone, input, desktop capture or sound playback is used.

The initial 2026-11-13 revision adds 31 cases. Full verification passes 2390 tests with
five explicit optional/native skips, rules 556/556, adversarial validation
100/100, lint and all 12 generated outputs. Site build/type checks and all
15 browser checks also pass; existing component/Bar snapshots remain exact.
The Save-dialog refinement adds a regression for preserving the exact confirmed
path; its full suite passes 2391 tests with the same five explicit skips. All
54 focused History/clipboard checks and lint pass. Native dialog acceptance
remains unexercised while desktop control is stopped.

The shared-page tests compare complete collected configurations before/after
reparenting, save edits made on several pages, preserve staged values after a
rejected save, and exercise real app routing/reopening of the same owned window.
They also cover recent-row selection, offline status, empty/incomplete metrics,
download pausing and the shortcut-label lifetime regression. Larger-text checks
cover the 880×600 Hub in both themes and reach the final shortcut/Save controls.
Guarded owned rendering exports 16 page/section states in both themes at
1080×720 and 880×600, at 1× and 2× density (128 PNGs); every logical/pixel size
is checked. Selected final renders are visually inspected. These are QA exports,
not the complete P6.6 gallery/snapshot acceptance.

The shared-Hub revision adds 16 cases and passes 2407 tests with five explicit
optional/native skips, rules 556/556, adversarial validation 100/100, lint and
all 12 generated outputs. Site build/type checks and all 15 browser checks pass.
The final guarded 1×/2× render review follows the keycap-lifetime fix; earlier
renders exposing that defect are retained separately in QA storage. Existing
component/Bar snapshot tests still pass. No native desktop control resumed.

The structured Dictionary revision adds 25 cases. Final full verification passes
2432 tests with five explicit optional/native skips, rules 556/556, adversarial
validation 100/100, lint and all 12 generated outputs. Site build/type checks and
all 15 browser checks pass. Owned renders cover all three Dictionary lists in
both themes, at 1080×720/880×600, with 16/22 px body text and 1×/2× density
(48 exact-size PNGs); selected final renders are inspected. Larger-text tests
also reject horizontal overflow and reach Reload/Save through the scroll view.
Invalid encoding, oversized startup files and deep JSON nesting refuse editing
without rereading or overwriting the rejected saved file.

One earlier full run reported a confirmation assertion in the existing
own-control native tracked-edit probe. Its failed run log is retained; the
temporary probe JSON is no longer present after subsequent test runs. The isolated
repeat and final full suite pass. The native observer/probe and its checks are
unchanged, and the underlying intermittency remains unresolved. These probes use
only owned invisible controls. Desktop/manual acceptance remains deferred.

The structured Snippets revision adds 34 cases. Final full verification passes
2466 tests with five explicit optional/native skips, rules 556/556, adversarial
validation 100/100, lint and all 12 generated outputs. The three editor/test/
advanced states render in both themes, at both window sizes, with 16/22 px text
and 1×/2× density (48 exact-size PNGs with no horizontal overflow). Selected final
renders are inspected. Larger-text tests reach Test/Reload/Save and keep the Hub
at 880×600. Migration tests preserve complete History rows, owner extensions and
source bytes; failed transactions/stale drafts retain the newer store. Variable
tests cover opaque cleanup input, one-pass values, Unicode matching, output
budgets, field/cancellation refusals, read-only clipboard ports/owned memory and
failed feedback without opaque tokens reaching History. No owner clipboard,
microphone, sound or desktop input is used.

The global History revision adds 34 cases covering 451-row paging/search,
Unicode/literal queries, selected-row lookup, immutable views, live commits
during incremental backup, streaming exports, cancellation/atomic failures,
database-path protection and out-of-order worker results. Refresh, error and
close/reopen tests keep stale selections from reaching actions. The Save-dialog
test changes the displayed filter during its replaced modal execution and
verifies that the original query is exported. Guarded owned renders cover four
History states in both themes/sizes, with 16/22 px text and 1×/2× density
(64 exact-size PNGs without horizontal overflow); selected final states are
inspected. These are QA exports, not complete gallery acceptance.
Final full verification passes 2500 tests with five explicit optional/native
skips; rules pass 556/556 and adversarial validation passes 100/100. Ruff and
all 12 generated token outputs pass. No website source changes are part of this
History revision; the deployed section gutters and creator credit were separately
confirmed in production HTML/CSS.

The first full run retained a timeout in the existing authenticated local HTTP
health test; the first isolated rerun timed out in its oversized-body case.
A subsequent unchanged isolated run passes all 12 cases, including both absolute
deadline checks. Five separate public-fixture requests measured 8–14 ms and
correctly rejected oversized bodies. Logs remain in permanent QA storage; the
intermittent timeout's cause is unresolved. No loopback code or test deadline
was changed for this History revision.

Full §8.3 still requires Notes producers, microphone picker/test, Privacy controls,
complete model/disk controls and model/cleanup retry choices. The later
onboarding, Scratchpad/Notetaker and complete gallery/
accessibility milestones retain their original scope.
