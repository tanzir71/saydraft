# Pro release-latency baseline: completed, target missed

Source: `8b705cc294fc5e372082ebf2e82829591e9b81fc`, clean detached checkout.
The complete 160-case matrix ran with twenty cold and twenty warm samples at
each duration. All 80 pair processes exited successfully. All 160 recorded native
child exits, durable-History-before-delivery checks, clipboard restoration,
no-early-delivery checks and release-deadline checks pass.

**The Pro latency target is not met.** Both ten-second medians exceed the 1.2 s
limit. Decoder readiness/rate meets the recipe, but the overall tier recipe does
not qualify. Standard remains unmeasured; the earlier Lite result also remains
separate. No threshold was relaxed and no sample was discarded.

| Clip | Cold p50 | Cold p95 | Warm p50 | Warm p95 |
|---|---:|---:|---:|---:|
| 3 s | 0.6166 s | 0.7030 s | 0.6333 s | 0.7534 s |
| 10 s | **1.2675 s** | 1.3227 s | **1.2127 s** | 1.2576 s |
| 30 s | 0.3169 s | 0.3657 s | 0.3104 s | 0.3540 s |
| 90 s | 0.8422 s | 1.0282 s | 0.8165 s | 0.9859 s |

The recipe uses Parakeet v3 int8, the pinned local language detector and Silero,
plus Qwen3.5 2B Q4_K_M with llama.cpp b12110 on Vulkan1 (RTX 3060).
The real cleanup model is accepted in all 3/10-second cases: forty cold and forty
warm. The 30/90-second cases use the normal `skip_budget` rules fallback. Their
short release tails do not mean the whole recordings were recognized instantly.
All release-time decoder medians are at least 99.78 tokens/s, above the 40 tok/s
recipe threshold.

Capture is real-time replay of bundled public audio. Microphone, foreground,
keyboard and clipboard ports are owned fixtures; the normal Inserter and its
150 ms waits run through a checked memory Ctrl+V. These are release-to-simulated-
paste measurements, not physical target-app latency, cold app startup, owner
speech accuracy or a promise for another PC. The normal release path includes
History and target checks; those checks were not removed to improve results.

The immutable trial checkout stayed unchanged. Source fingerprints and runtime
environment match before/after; every model/runtime payload and bundled model
notice in the pre-run receipt was rehashed after the terminal parent exit.
During sampling, work in the separate main checkout was limited to source/docs
editing and lightweight static/metadata checks. No local tests, builds, model
jobs, audio-corpus transfers or pushes ran concurrently with sampling.

## Retained proof

- [Full report and eight-cell summary](report.json).
- [Pre-run model/runtime hashes](model-before.json).
- [Independent post-run verification](verification-after.json): 160 cases,
  80 child reports/journals, all recorded native exits and model/source hashes.
- [Byte index](index.json): 323 original JSON/JSONL metadata artifacts. Every pair
  retains its request, terminal-process receipt, report and case journal.

Private QA SQLite files and native binaries are excluded. Raw metadata bytes are
preserved by `.gitattributes`; the index records their exact SHA-256 values.
These results precede the later multilingual-cleanup and language-evidence work.
Diagnose the ten-second ASR/cleanup tail from this baseline before changing the
release path, then repeat a complete qualifying run. P4.6 remains open.
