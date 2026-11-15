# Full overnight follow-up — 16 November 2026

The five-stage R2 batch completed in 2h 00m 10s, from 17:43:21 to 19:43:31 UTC
on 15 November (23:43–01:43 in Dhaka). The independently held controller handle
reported exit 0. All five stage trees exited with code 0; all six independent
verification commands and the observer itself exited with code 0. Keep-awake
was released. This describes measurement integrity, not universal quality acceptance.

The benchmark pins clean source `44ed9c458a78e84e55751b827ed71b96114632ae`.
The later app UI v2 implementation is outside this measured source snapshot.
Models, corpora, original thresholds and decoder settings were not promoted or changed.

## Results

| Stage | Golden exact matches | Accepted golden model replies | Preservation failures | Decoder median | Gate outcome |
|---|---:|---:|---:|---:|---|
| CPU 0.8B forced | 555 / 556 | 385 | 0 | 22.94548 tokens/s | Regression gate failed; below 25 tokens/s target |
| Pro 2B forced | 553 / 556 | 393 | 0 | 144.54443 tokens/s | Regression gate failed; above 40 tokens/s target |
| CPU 0.8B production policy | 556 / 556 | **0** | 0 | 24.35910 tokens/s | Delivered output passes; entirely rules fallback; speed target missed |
| Pro 2B production policy | 556 / 556 | 269 | 0 | 126.16138 tokens/s | Delivered output passes; speed target met |

Every cleanup pass covered all 556 goldens and all 100 authored adversarial cases.
Forced CPU accepted 99 adversarial replies; forced Pro accepted 100. Both policy
passes skipped generation on all adversarial cases as low-need. Those skipped
cases earn no model-generation credit. The CPU policy pass earns no generation
credit anywhere in the corpus. Each decoder median uses three 60-token samples.

The Pro release-latency matrix completed all 160 cases: 80 cold/warm pairs,
20 repeats per phase at each of 3, 10, 30 and 90 seconds. Independent verification
checked all 160 native exits, 80 distinct Python children, 80 QA History databases
and 267 source objects. Every cell met p50 ≤ 1.2s and p95 ≤ 2.0s. The largest
cell p95 was **1.77473s** (warm, 10 seconds). The largest observed case was
1.80720s. Cold and warm phases each accepted 19 cleanup-model replies; remaining
cases used the production budget/fallback behavior. Model use was measured,
not inferred from a passing output alone.

## Preserved failures and continuation

Forced CPU and Pro both changed `balanced-chat-05` from the expected
`Thanks comma talk soon` to `Thanks, comma talk soon`. Pro also produced:

- `balanced-general-04`: `Hello, comma, world` instead of `Hello comma world`.
- `balanced-email-01`: `Hello, comma team.` instead of `Hello comma team.`.

The literal word “comma” remained, but the model added unwanted punctuation.
These are exact-output regressions despite passing preservation checks. A future
cleanup change should address the candidate/prompt behavior and rerun the same
corpora. Do not change the goldens or lower a threshold to erase the failures.
CPU decoder speed also needs separate investigation before claiming its target.
No default or model promotion follows from this run.

## Evidence and limits

`raw-evidence.tar.gz` preserves 546 original text objects byte for byte, including
all five reports, cleanup journals, all 480 pair metadata objects, refusing-port
receipts, orchestration and verifier scripts, controller/observer statuses, and
the native terminal receipt. `manifest.json` hashes every member and the archive.
All archive members were reread and independently hash-compared after creation.
The original QA databases remain in the isolated D: run; their verifier receipts
and hashes are included. Model binaries, audio, profiles and databases are excluded.

The earlier R1 attempt remains separately labelled `previous-r1/` and unqualified:
it stopped at 120/160 latency cases with exit 1 and did not run cleanup stages.
It contributes no cases to R2.

These are public-file and in-memory capture/input fixtures. They establish neither
physical Windows insertion behavior nor owner accuracy across languages. Owner
accuracy acceptance remains deferred by instruction; native acceptance belongs
in a disposable Windows VM. The unsigned portable was unchanged during this run:
SHA-256 `83456b5a9a50672db1ad74119c956c733c2768a287f301f701711b2e75aceb5c`.
