# Retained native cleanup evidence

The [forced-quality matrix](../eval/cleanup/results/2026-11-13-word-guard/README.md)
retains ten complete jobs at immutable `4a1e69a`: all five candidates on CPU and
RTX 3060. Each job generated 556 golden and 100 adversarial inputs, including
100 token-counted adversarial replies, three exact 60-token decode samples and
independently observed native exits. Original report bytes and private journal
SHA-256 values remain pinned. Preservation guards and prompts still match these
reports; their source commit is not relabeled as the current whole-app commit.

## Current policy replay

The [post-deadline replays](../eval/cleanup/results/2026-11-13-deadline-policy/README.md)
at immutable `1486b09` use the production need/budget gate and 800 ms cap. Each
completes 556 golden and 100 adversarial policy inputs, with no timeouts, golden
regressions or finite preservation failures:

| Recipe | Golden exact | Accepted model replies | Decode median | Slowest timed case |
|---|---:|---:|---:|---:|
| CPU Qwen3.5 0.8B | 556/556 | 0 | 20.74 tok/s | 53.6 ms |
| RTX Qwen3.5 2B | 556/556 | 269 | 114.80 tok/s | 315.6 ms |

CPU keeps deterministic rules and cannot earn hybrid credit or the 25 tok/s
Standard tier. Its separate forced 25.89 sample cannot replace the live policy
calibration. RTX has 278 token-counted golden replies, including nine rejected
responses; only 269 accepted replies earn credit. Every adversarial policy input
skips for low need. Independent forced generation prevents those skips from
being mistaken for actual model preservation evidence.

Background startup, calibration and static-prefix preparation are outside case
timing. Case maxima cover a synthetic processor with stub delivery, excluding
ASR and physical insertion. They do not qualify cold/warm release latency,
owner accuracy, a hardware tier or a model default. All owned native exits were
observed. Source/prompt fingerprints match the replayed implementation.

Owned CPU fault checks additionally retain an 80 ms timeout returning fallback
control in 85.3 ms and a cached-input interruption returning control 9.6 ms after
termination began, with no partial output. The first uncached interruption setup
failed to observe generation before its 800 ms cap; that failed command is also
retained. Exact-input priming was outside the corrected interruption's timing.
Native idle/activity/reload checks also pass with a 250 ms probe interval while
production stays at 900 s. A 100-cycle synthetic app probe preserves all History
rows and stub insertions; all 66 native sidecars exit after shutdown. The separate
scoped §11 200-cycle gate now also passes in the
[combined native run](../eval/soak/results/2026-11-14-native/README.md), with
3.50% RSS growth and all 100 sidecars exiting. Its clipboard is in-memory;
physical Windows acceptance remains separate.

## Offline checker

Run `python -m tools.check_cleanup_evidence`. Its defaults select the current
policy pair and the separate forced CPU 0.8B / RTX 2B reports. The expected
result is refusal, `Rules fallback cannot earn accepted model credit`, because
CPU accepted no model replies. Measurement completion is not hybrid acceptance.
Custom indexes can be selected with `--policy-index` / `--forced-index`.
The checker performs no downloads or inference.

Checks enforce immutable report digests, pinned candidate/runtime identity,
clean isolated full corpora, observed native exits, unchanged source/corpus/prompt
hashes, at least 92% strict hybrid exact output with zero golden/must-keep
regressions, real accepted replies with token evidence, and three finite exact
60-token decoder samples. Forced evidence pins the pipeline activating post-rules
validation. Only LF/CRLF source variants are permitted; raw native report bytes
remain strictly pinned. Affected source/corpus changes require fresh evidence.

Median decode is separately compared with 25/40 tok/s; interactive prediction
uses the minimum sample. Rates cannot substitute for quality, co-loaded ASR or
cold/warm release-to-insertion measurements. No requirement was relaxed to
accept CPU fallback; mandatory native-evidence CI wiring remains pending.
The deadline-path implementation passed 175 focused checks and full CI at
`1486b09`: 3045 passed, 12 skipped; rules 556/556 and authored validator 100/100.
Those checks complement the retained native measurements, not owner acceptance.

## Historical evidence

The [earlier policy diagnostics](../eval/cleanup/results/2026-11-13-policy/README.md)
retain the original 9.98-second CPU overrun and partial failure at `4a1e69a`.
The [pre-word-guard baseline](../eval/cleanup/results/2026-11-13-baseline/README.md)
retains the French substitution that motivated the word-fidelity fix. Older
432-case reports and their failures remain in dated result folders. None may
qualify changed source/corpora. Finite checks and fixture reviews do not prove
semantic safety, owner speech accuracy or full product parity.
