# Saydraft Hub

P6.3 remains in progress. The target is the single 1080×720 Hub described in
plan §8.3, with an 880×600 minimum and Home, History, Dictionary, Snippets,
Style, Notes and Settings in its left rail. Existing Settings and History
windows are still present until their behavior is migrated and parity verified;
the current History work supplies controls that will move with that page.

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

`DictationHistoryStore.weekly_stats(today=...)` reads only `stats_daily`, using
local Monday–Sunday dates. It returns dictation/word/speaking-time totals,
average WPM (words ÷ speaking seconds × 60) and estimated time saved against
40 WPM typing, floored at zero. WPM is unknown when there is no speaking-time
measurement. These are aggregates for the future Home page; that page is not
connected yet. Existing retry accounting continues to avoid counting one
recording twice.

## Verification and remaining work

```powershell
node tools/generate_tokens.mjs --check
python -m pytest tests/test_history_view.py tests/test_history_details_ui.py tests/test_history.py tests/test_history_window.py tests/test_native_clipboard_app.py -q
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

The Hub shell/navigation, Home presentation, Settings/page migration and
retirement of the old windows remain. Full §8.3 also requires the structured
Dictionary/Snippets/Notes pages, microphone picker/test, Privacy controls, complete
model/disk controls, History paging/global search and model/cleanup retry
choices. The later onboarding, Scratchpad/Notetaker and complete gallery/
accessibility milestones retain their original scope.

Before connecting Home's WPM/time-saved presentation, cover weeks mixing legacy
entries with unknown speaking duration and measured entries: daily aggregates
do not currently record measurement completeness. Such a week must show an
unknown measurement rather than treating missing speaking time as zero.
