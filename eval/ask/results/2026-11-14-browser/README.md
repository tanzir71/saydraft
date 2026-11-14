# Read-only browser Ask diagnostics · 14 November 2026

Clean `666cf5d` passes the [combined real-model browser job](https://github.com/tanzir71/saydraft/actions/runs/43584597735/job/132416287741).
Its [driver](native-model-666cf5d/report.json),
[native report](native-model-666cf5d/native-report.json) and
[independent verification](native-model-666cf5d/independent-verification.json)
confirm actual pinned Qwen3.5-4B CPU generation through real native UIA selection,
Ask review/worker, History and an independent answer Note. The answer is
“The library opens on Saturday at 10:00.”, matching the authored source. Both
[review](native-model-666cf5d/question.png) and
[answer](native-model-666cf5d/answer.png) screenshots were inspected and are
legible with all eight bundled font faces loaded.

The full CI run passes 4,172 tests with 12 explicit skips in 602.81 seconds,
rules 556/556 and adversarial 100/100. App source is unchanged since `4485386`,
whose full CI and unsigned packaging pass. This accepts the specified P7.3
implementation/browser scope; the full original parity goal remains active.

The native sidecar, Python child, UIA worker and owned Chromium all exit;
model/runtime pins and clean source remain unchanged. The article DOM/selection
is unchanged, History precedes presentation, the primary note remains active,
and explicit Copy goes only to memory. The actual model cache was explicitly
prepared by CI setup outside the uploaded evidence folder; runtime uses only
verified local files and cannot fall back to a scripted model in this CI job.

Run `python eval/ask/results/2026-11-14-browser/verify-native-model.py.txt` from
the repository root to replay the retained native/source/SQLite/Notes checks.
The public SQLite database contains only the authored question/answer and two
test notes. This is one English browser fixture, complemented by eighteen
separate authored-text native model smokes; it does not establish broad factual
accuracy, physical hooks/microphone/clipboard or a packaged interaction.

The first local verifier opened application stores, whose schema initialization
rewrote SQLite metadata. The [diagnostic](verifier-page-rewrite-diagnostic.json)
retains that finding: the three relevant tables' rows match the freshly
downloaded artifact. The published database is restored from that same CI run;
the portable verifier uses immutable read-only SQLite and checks unchanged bytes.

The earlier compatibility diagnostics and failures remain unchanged below.

Clean `4485386` now passes the [native browser job](https://github.com/tanzir71/saydraft/actions/runs/43582821699).
The [driver](4485386-report.json), [native report](4485386-native-report.json)
and [independent verification](4485386-independent-verification.json) confirm
three real selected-text reads with explicit read-only metadata, unchanged
article/selection, History before presentation, a separate answer Note and
observed browser/child/UIA exits. The [verifier](verify-browser.py.txt) also reads
the original SQLite History/Notes rows and source hash/length provenance. This
still uses a scripted model and memory Copy; the combined actual-model/browser
run is recorded above. The initial Qt screenshots omitted font installation
and show missing glyphs, so they are not visual acceptance. A themed harness
rerun at `82bf569` passes and is superseded by the themed actual-model run above.
Both earlier failures remain below.

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
reverification is recorded above.

The remote harness uses an owned local HTML article, a new headed Chromium,
real foreground/UIA and the actual Ask worker/review/History/independent Notes.
The earlier model and explicit Copy are scripted ports; `666cf5d` uses the actual
pinned model with memory Copy. No microphone, native hooks, OS typing or owner
clipboard are used. Separate authored-text smokes are in the
[model record](../2026-11-14-selection/README.md). This job does not establish
physical or packaged acceptance.

The [index](index.json) retains byte-exact source artifact paths and hashes.
