# Latest cleanup qualification

The offline checker now uses the completed `44ed9c4` overnight measurements,
without running models or duplicating their archived reports. `policy-index.json`
and `forced-index.json` independently pin the unchanged archive SHA-256 and each
selected member's original SHA-256. The historical archive and its manifest remain
unchanged. Existing plain-file indexes remain supported.

Run `python -m tools.check_cleanup_evidence`. Expected exit: **1**. This is a
preserved qualification failure, not a broken invocation.

| Backend / mode | Exact output | Accepted model replies | Median decoder rate / target | Result |
| --- | --- | --- | --- | --- |
| CPU 0.8B policy | 556/556 | 0 | 24.36 / 25 tok/s | No hybrid model credit; speed fails |
| CPU 0.8B forced | 555/556 | 385 | 22.95 / 25 tok/s | One golden regression; speed fails |
| Pro 2B policy | 556/556 | 269 | 126.16 / 40 tok/s | Scoped policy quality/speed pass |
| Pro 2B forced | 553/556 | 393 | 144.54 / 40 tok/s | Three golden regressions |

Every stage retains all 556 goldens and 100 authored adversarial cases, native
exit evidence, pinned model/runtime identities and matching relevant current
cleanup source/corpus/prompts. Evidence validity is separate from quality and
speed. The CLI reports all stages and fails unless each passes all three. Its
legacy Python `check()` API retains separate speed flags and quality-only success.

The old checker did not reject forced golden regressions. That gap is closed:
passing policy output cannot hide a forced-model regression. The original
92% exact threshold, zero-regression requirement, 25/40 tok/s targets, three
60-token samples and production 800ms policy deadline are unchanged.

## Verification

Forty-seven guarded tests pass, including archive/member digest changes,
traversal/duplicate/link/missing/oversized members, unpacking bounds, stale source,
rules-only model credit, forced golden regressions, decoder sample validity and
CLI failure while quality passes but CPU speed fails. Ruff passes. The first
new test incorrectly assumed the historical forced index listed CPU first;
the fixture now selects that candidate by name. Both attempts are retained.

The real-data check verifies all four original reports. The captured output is
`qualification.json`. Test logs, guard receipts, producer and file hashes accompany
this record. The guard records no host audio SDK, microphone, clipboard, native
input, owner profile or GPU discovery access. No VM was prepared or started.
The desktop app source and published portable are unchanged.

## Next smallest useful work

- Forced comma regressions: investigate candidate/prompt behavior on the three
  already observed development cases, then repeat the unchanged complete corpora
  before considering a promotion. Keep goldens and thresholds unchanged.
- CPU: investigate model/runtime throughput and useful production-budget model
  participation. Rules-only 556/556 does not establish the hybrid quality target;
  do not increase the 800ms deadline merely to turn fallback into model credit.
- Broader multilingual/owner accuracy, co-loaded cold/warm latency and real
  Windows acceptance remain separate. VM work is stopped for storage, and host
  audio/clipboard/input restrictions remain in force.

These findings are scoped to cleanup evidence. They do not accept a hardware
tier, full application latency, owner speech accuracy or a new model default.
