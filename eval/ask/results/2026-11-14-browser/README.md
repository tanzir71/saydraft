# Read-only browser Ask diagnostics · 14 November 2026

Clean `4485386` now passes the [native browser job](https://github.com/tanzir71/saydraft/actions/runs/43582821699).
The [driver](4485386-report.json), [native report](4485386-native-report.json)
and [independent verification](4485386-independent-verification.json) confirm
three real selected-text reads with explicit read-only metadata, unchanged
article/selection, History before presentation, a separate answer Note and
observed browser/child/UIA exits. The [verifier](verify-browser.py.txt) also reads
the original SQLite History/Notes rows and source hash/length provenance. This
still uses a scripted model and memory Copy; a combined actual-model/browser
run remains unverified. The initial Qt screenshots omitted font installation
and show missing glyphs, so they are not visual acceptance. A themed harness
rerun follows. Both earlier failures remain below.

Both first native CI runs refuse the focused Chromium Group (50026) without
reading source text, invoking a model or writing a document. The authored
article and DOM selection remain unchanged, and the owned browser/UIA exits
are observed. These are retained failures, not browser acceptance.

- `c7b9566`: [driver](c7b9566-report.json), [native report](c7b9566-native-report.json),
  [CI artifact](https://github.com/tanzir71/saydraft/actions/runs/43581341731/artifacts/14108047453).
  It establishes that the focused container exposes no directly usable selected
  range. It does not establish whether the text pattern is absent or returns an
  empty selection.
- `3a48913`: [driver](3a48913-report.json), [native report](3a48913-native-report.json),
  [CI](https://github.com/tanzir71/saydraft/actions/runs/43581937175).
  The first correction still refuses capture before its ancestor walk. The next
  correction handles empty focused selections as well as unsupported patterns,
  retains direct range-count/error metadata, and requires one explicitly
  read-only selection from the nearest document. Ambiguous multiple selections
  remain refused.

The [154 controlled checks](controlled-ranges.txt) cover bounded ancestry,
sensitive/native-window/edit boundaries, unknown/mixed read-only metadata,
focus/cancellation, field and native-range identity, and immutable read-only
write refusal. The selected range's read-only metadata overrides a container's
Value default; it is rechecked before replacement. Neither a changed DTO nor a
later writable provider can promote a captured read-only lease. Native
reverification remains pending.

The remote harness uses an owned local HTML article, a new headed Chromium,
real foreground/UIA and the actual Ask worker/review/History/independent Notes.
The model and explicit Copy are scripted ports; no microphone, native hooks,
OS typing or owner clipboard are used. Actual pinned-model smoke is separate
in the [model record](../2026-11-14-selection/README.md). This job does not
establish combined native-model/browser, physical or packaged acceptance.

The [index](index.json) retains byte-exact source artifact paths and hashes.
