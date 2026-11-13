# Retained native cleanup evidence

The current [forced-quality matrix](../eval/cleanup/results/2026-11-13-word-guard/README.md)
contains ten complete jobs at immutable source `4a1e69a`: all five candidates on
CPU and RTX 3060. Each job generated the complete 556-golden/100-adversarial
corpora, including 100 token-counted adversarial replies, three exact 60-token
decode samples and independently observed native exits. Original report bytes
and private journal SHA-256 values are retained. Current guard/prompt source
fingerprints match these reports; that does not relabel their whole-app commit.

The separate [production-policy diagnostics](../eval/cleanup/results/2026-11-13-policy/README.md)
use the actual 800 ms cap and production need/budget gate, with background
preparation outside case timing:

| Recipe | Policy result | Accepted golden replies | Qualification |
|---|---|---:|---|
| CPU Qwen3.5 0.8B | Failed after 186/556 golden cases; no adversarial cases | 0 | Incomplete, refused |
| RTX Qwen3.5 2B | 556/556 golden exact; 100 adversarial low-need skips | 269 | Complete recipe measurement |

RTX has zero golden regressions and no finite preservation failures. Its live
three-sample decode median is 134.54 tok/s. CPU's journal calibration median is
21.00 tok/s; the final failed report has no live calibration. A CPU timeout case
returns rules output after about 9.98 seconds despite the configured cap, then
preparation fails. The cause of that wall-time overrun remains open. The failed
report is retained unchanged, with observed native exit. A complete RTX recipe,
a partial exact CPU score or the separate forced CPU 25.89 tok/s sample cannot
qualify the combined pair, hardware tiers or release latency.

Subsequent transport changes apply the deadline to each socket read/write and
remove per-request watchdog/idle-timer churn. The retained `4a1e69a` policy
reports predate that change; fresh policy measurements remain required. The
forced reports still match unchanged preservation guards and prompts. Earlier
failed reports are not overwritten or reclassified as successes.

## Offline checker

Run `python -m tools.check_cleanup_evidence`. Its defaults now point to the
current policy pair and the current CPU 0.8B / RTX 2B forced reports. The expected
result is refusal, `Native measurement failed`, because the CPU report retains
its error. This is an unresolved measurement outcome, not a passing native gate.
Custom indexes can be selected with `--policy-index` / `--forced-index`.
The checker performs no downloads or inference.

Checks enforce immutable report digests, pinned candidate/runtime identity,
clean isolated full corpora, observed native exits, unchanged source/corpus/prompt
hashes, at least 92% strict hybrid exact output with zero golden/must-keep
regressions, real accepted replies with token evidence, and three finite exact
60-token decoder samples. Forced evidence also pins the pipeline activating
post-rules validation. Normalized LF/CRLF source text is permitted; raw native
report bytes remain strictly pinned. Source or corpus changes require fresh
measurements for affected evidence.

The checker separately reports whether median decode reaches 25/40 tok/s;
interactive prediction uses the minimum sample. Rates do not substitute for
quality, co-loaded ASR or cold/warm release-to-insertion measurements. Safe rules
fallback earns no accepted-model credit. Policy adversarial skips cannot replace
the independent forced adversarial generations. No requirement was relaxed to
accept the failed CPU run; mandatory native-evidence CI wiring remains pending.

## Historical evidence

The [pre-word-guard baseline](../eval/cleanup/results/2026-11-13-baseline/README.md)
retains six completed jobs and the accepted French substitution that motivated
the word-fidelity fix. Older 432-case reports and their failures remain in their
dated result folders; they cannot qualify the current corpus or source. Finite
preservation checks and a successful quality gate do not prove semantic safety,
owner speech accuracy, a model default or full product parity.
