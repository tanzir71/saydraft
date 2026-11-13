# Packaged firewall acceptance — 2026-11-14

Source: `7d80be2dfc845f9c6fd7b3bd52aa064b13d8bade`.
[CI 43522750848](https://github.com/tanzir71/saydraft/actions/runs/43522750848)
passes **3,283 tests / 12 explicit skips** in 391.04 seconds, rules **556/556**
and authored adversarial checks **100/100**. Default-off/opt-in update metadata
checks also pass. [Package 43522751029](https://github.com/tanzir71/saydraft/actions/runs/43522751029)
passes its clean build, notices/resources, disposable installer lifecycle and
actual frozen firewall smoke. P8.6's fixture-based acceptance is satisfied.

The source probe blocks only its freshly copied interpreter on a disposable
GitHub-hosted Windows runner. A fixed native WinHTTP request and pinned model-file
download work before the rule, fail under it (WinHTTP 12029 / Python URLError),
and work again after removal. Two public-audio utterances traverse the real
worker, pinned Whisper base/Silero, rules, SQLite-before-paste and actual Inserter
with memory keyboard/clipboard. Both complete and restore the memory sentinel.
The managed rule is removed and absence is confirmed. Inspection diagnostics
retain all states/durations with the explicit 30-second CI query budget.

The frozen probe uses the actual bundled `Saydraft.exe`. Its helper creates the
all-profile outbound block rule, repeats it idempotently, refuses conflicting
ownership and narrowed rules, and removes it idempotently. An unrelated rule for
the same executable survives. Frozen public-fixture ASR, cleanup rules and
temporary History succeed before, under and after the rule. Native requests and
pinned Python downloads fail only under the rule, with explicit remove-and-resume
guidance. Frozen imports/resources/Python policy pass under the rule. No app
profile is created, and fixture rules are cleaned up.

`source/` and `frozen/` contain unchanged selected artifact payloads.
`ci-run.json`, `package-run.json` and artifact catalogs are unmodified GitHub API
snapshots. `index.json` hashes every retained payload, metadata archive and
privately retained job log. Both downloaded successful artifact ZIPs matched
GitHub's SHA-256 digests. Evidence collection downloaded metadata only; no model,
installer or portable binary was downloaded for this evidence collection.

Earlier failures are preserved in `earlier/`:

- `b052758`, CI 43520317634: a test lambda assignment failed lint before the
  suite. Fixed with a named function.
- `2e493ac`, CI 43520757779: 3,272 passed / 12 skipped / 10 failures, all the same
  parametrized test comparing forward slashes with a Windows path. Fixed with
  `Path` equality. Its native probe created the rule but rejected the repeated
  Block request; cleanup succeeded.
- `fc5401e`, CI 43521064135: diagnostics showed Windows returns an empty package
  filter for this desktop program, while every other expected field matched.
  The helper now accepts that representation, preserving all other restrictions.
- `d4b5ddf`, CI 43522279974: its source probe stopped on an unknown initial
  read-only status before mutation; cleanup confirmed absence. The original
  provider cause was not captured. Null-safe program-filter handling and bounded
  cold-VM diagnostics were added; do not relabel this as a proven timeout.
  Its separate frozen speech/network package smoke passed.

All scopes use public audio and private disposable state. No owner microphone,
audio-device enumeration, foreground field, OS input or clipboard is exercised.
The runas ABI/cancellation path is tested with owned fake Win32 APIs; CI invokes
the helper with its existing administrator token and does not exercise a manual
UAC consent dialog. Effective organizational policy, separate cleanup-sidecar
coverage, physical Windows use and owner ASR accuracy remain distinct gates.
