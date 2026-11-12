# Interactive cleanup gate

The production pipeline scores the protected original transcript before rules
remove cues. Backtracking, list cues, filler density at least 15%, more than 25
words, and Polished intensity each add two points; a non-neutral style adds one.
Two points permit a budget check. Raw and Code continue to bypass prose cleanup.
Low-need text keeps the rules result without constructing or contacting a model.

Enabled cleanup requires background decoder and prompt preparation. The client
uses the minimum of the live instance's three decode samples. It tokenizes the
rules result and final user message, compares token IDs with the last completed
request for the same generation and static prefix, and estimates:

`predicted_seconds = (changed_user_tokens + 12) / (4 * decode_tps)
                   + min(output_cap, ceil(source_tokens * 1.25) + 2) / decode_tps`

The 4x prefill estimate and 12-token boundary allowance are heuristics, not a
measured prefill rate or a guaranteed cache hit. The hard deadline is binding.
Missing/stale calibration, an unknown prefix, or an estimate above the remaining
budget preserves rules. An unknown prefix schedules background re-preparation.
Only ephemeral token IDs track the previous user message; it is not persisted.

The request uses the smaller of the configured 800 ms cap and an optional outer
deadline, reserving 50 ms for fallback/delivery. Prompt assembly, tokenization and
generation consume that same absolute deadline. Expired requests do not start a
model. The worker captures the release event's monotonic timestamp and carries
its two-second outer deadline in ephemeral `DictationContext` metadata. Recorder
shutdown, executor queueing, ASR, preview completion and processor work all consume
that budget; captured-app/language replacement preserves it. No fresh budget starts
after recognition, and each new recording starts without a previous deadline.
The outer cap follows the with-LLM p95 ceiling in §1 row 8; it does not guarantee
that ASR, fallback, History or insertion finishes within the target, or establish
the tighter rules-only or p50 targets. Standalone cleanup without a release event
retains the configured request cap.

History stores the existing accepted/fallback/skip reason before insertion. The
diagnostic log contains score/cue labels, token counts and predicted/remaining
milliseconds, with no transcript, app name, glossary, caret text or generated text.
Tokenization-only skips receive no generation token credit in evaluation reports.
Accepted replies still require complete SSE, a stop finish and existing detail,
protected-token and structure validation.

Scientific quality measurements explicitly disable interactive preparation/gating;
they remain separate from app policy. To exercise the actual gate on installed,
verified developer candidates, add `--budget-gate` to
`python -m tools.probe_prompt_preparation` (see [preparation](CLEANUP_PREPARATION.md)).
Five fixed public cases cover neutral/formal low need, high need and expiry.
High-need cases may legitimately skip for budget; `accepted_replies` is reported
separately. Five correct policy outcomes do not imply five model replies or model
quality acceptance. The probe performs no capture, database write or live insertion.

Validation: 1383 tests pass with four optional native skips; rules 432/432,
authored adversarial checks 100/100, and Ruff/diff checks pass.

Tests cover pre-rule cues, Unicode word counts, low-need/expired zero-call paths,
live rates, shared deadlines, tokenization time, cache invalidation, metadata
privacy and History ordering. Worker/processor tests charge simulated recorder,
queue and ASR delays through the real gate/client and prove an expired budget
still saves rules before simulated insertion. Automatic adapter/benchmark integration, full gated
quality and Standard/Pro end-to-end latency acceptance
remain required. No candidate is promoted or selected by this change.

Native policy proof from immutable `735e5d8`, with networking blocked:

| Backend | Live decode minimum | Low-need outcomes | High-need outcomes | Expired budget | Accepted replies |
| --- | ---: | --- | --- | --- | ---: |
| Qwen 0.8B CPU, 4 threads | 15.88 tok/s | Both skip; each <1 ms | Both budget-skip; 38/42 ms | Skip, <1 ms | 0 |
| Qwen 2B RTX/Vulkan1, 4 threads | 120.91 tok/s | Both skip; each <1 ms | Both accepted exact; 179/143 ms | Skip, <1 ms | 2 |

Each backend completes all five expected policy outcomes and every result exactly
matches its rules baseline. Independent native handles observe both processes
exit. CPU predicts 756 ms before the hard reserve, above the 715 ms remaining
after tokenization, so its policy pass contains no generated cleanup replies.
Initial background preparation takes 18.701 s CPU / 5.717 s RTX; changed-style
prefix preparation takes 4.383 s / 0.277 s. This is short-case policy evidence,
with primed driver caches, not full-corpus quality or tier latency acceptance.
Unmodified reports: `eval/cleanup/results/2026-11-12-gate/`.
