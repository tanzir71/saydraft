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

Dictionary, Snippets and Style are the same controls moved into rail pages.
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
The structured Dictionary/Snippets editors and full remaining §8.3 features
listed below are still outstanding; the shell is not full P6.3 acceptance.

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

“Export filtered history…” exports only the loaded entries matching the current
filter, in their displayed order. The current list retains its existing
200-entry limit; global search/paging/export scope remains part of the Hub work.
Both raw and cleaned values are exported, independently of the selected view.

- Markdown uses dynamically sized fenced text blocks, including for metadata,
  so dictated markup and embedded fences stay literal.
- CSV uses UTF-8, quoted fields and CRLF records. Formula-like string cells
  receive a leading apostrophe for spreadsheet use; other strings retain their
  exact text, including commas, quotes and line breaks. Audio paths are omitted.
- A completed, flushed temporary file replaces the explicitly chosen destination
  atomically. A failed write/replacement preserves an existing export. Cancel is
  a no-op; write errors remain visible in the page status.

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

Full §8.3 still requires the structured
Dictionary/Snippets/Notes pages, microphone picker/test, Privacy controls, complete
model/disk controls, History paging/global search and model/cleanup retry
choices. The later onboarding, Scratchpad/Notetaker and complete gallery/
accessibility milestones retain their original scope.
