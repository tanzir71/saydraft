# Cleanup prompt preparation

Native measurements show that loading weights and passing health checks do not
prepare the first chat request. The isolated 0.8B CPU run takes 4.305 s for its
first cleanup; changed-style prefixes take 3.401 s median. Gemma E2B's initial
request takes 43.987 s. These exceed the unchanged 800 ms app request deadline.

Enabled installed cleanup now prepares a static `Ready` transcript in a daemon
worker. It uses the actual chat template, stage/style and bounded captured app
name/group, with a one-token generation cap. It warms no dictated words, caret
text or glossary. Generated preparation text is discarded; nothing reaches
History, insertion, a microphone or an external service. Weights never download.

Only a complete SSE response with `[DONE]`, no tool calls and a `stop` or `length`
finish can establish preparation. Actual dictation still requires a complete
`stop` response, protected-token restoration and normal detail/structure validation.
Preparation allows 60 s each for background model loading, decoder calibration
and prefix work; the interactive timeout remains 800 ms. Interactive cleanup
never waits for these stages.

Before the prefix probe, the live decoder generates three fixed 60-token garden
continuations with temperature zero and EOS ignored. All three share one manager
lease and deadline. Exact native token counts and positive finite decode rates
are required; generated prose is discarded. Metadata retains all three rates,
their median for reporting and their minimum for conservative prediction.
Measurements cache only for the current server generation. Restart/unload
invalidates them; a malformed measurement cannot establish readiness or repeatedly
probe the same instance. Raw generation runs before the chat-prefix probe so it
does not overwrite the final prepared prefix.

One worker coalesces requests to the latest app/style prefix. Startup uses the
configured profile, and arming uses the captured app/group and selected profile.
Raw/Code skip context preparation. Readiness is tied to the live server generation;
idle unload, restart and style/app changes invalidate it. Missing/failed/pending
preparation preserves rules immediately and records `prompt_warming` or
`prompt_unprepared`. Broken protocol is not repeatedly probed in the same instance.
Shutdown closes the owned server and refuses late preparation results.

Prefix preparation does not certify latency for every transcript, language,
caret value or glossary. The [interactive gate](CLEANUP_GATE.md) now adds need
scoring and per-request budget prediction. Release-deadline propagation and
end-to-end Standard/Pro acceptance remain P4.6 work. Model defaults remain unselected.
The one-token probe primes the chat prefix after decoder warm-up. These samples
do not certify every context length, changing system load or clean-driver-cache
behavior; tier acceptance still requires the remaining latency suite.

The developer quality runner and lifecycle fault probe explicitly disable
interactive preparation, allowing independent cold/use/fallback measurements.
Their config/report records this bypass. Production preparation has its own probe:

```powershell
python -m tools.probe_prompt_preparation --candidate qwen35-08b-q4-k-m --models-dir D:\Saydraft-Evaluation --runtime-dir D:\Saydraft-Runtime\llama-cpp-b12110-cpu-x64 --output D:\Saydraft-Reports\prepared-cpu
```

Vulkan uses its verified runtime plus `--backend vulkan` and an optional explicit
`--device Vulkan1` appropriate to the machine. Every run requires a new output
directory. The probe checks neutral/formal prefixes and actual accepted output
within 800 ms, retaining metadata, host working set and independent native exit
observations. It uses fixed public text and no live delivery.

Validation: 1352 tests pass, four optional native skips with local
Silero/preview/language-ID fixtures; rules 432/432; authored adversarial 100/100;
Ruff/diff pass. Tests cover blocked preparation, latest-context coalescing,
instance changes, partial streams, Raw/Code, captured context and shutdown races.
Calibration tests reject partial/invalid samples and stale instances, check the
single deadline/cache, and prove both background stages preserve foreground rules.

Earlier prefix-only native probes from `086c2bb` pass with networking blocked:

| Model/backend | Initial preparation (including load) | Neutral cleanup | Formal preparation | Formal cleanup |
| --- | ---: | ---: | ---: | ---: |
| Qwen 0.8B CPU, 4 threads | 6.625 s | 0.541 s | 2.989 s | 0.536 s |
| Qwen 2B RTX/Vulkan1, 4 threads | 3.171 s | 0.144 s | 0.246 s | 0.121 s |

All four replies are accepted, exactly match the rules baseline, and complete
within the unchanged 800 ms deadline. Independent native handles observe exit
after both runs. No capture, database or live insertion occurs. These two short
cases per backend verify preparation behavior, not corpus-wide latency or model
quality; GPU driver caches were already primed. Unmodified metadata reports are
retained in `eval/cleanup/results/2026-11-12-preparation/`.

Current decoder-plus-prefix probes from immutable `b393315` also pass:

| Model/backend | Three decode samples (tok/s) | Initial preparation, including calibration/load | Neutral / formal cleanup |
| --- | --- | ---: | ---: |
| Qwen 0.8B CPU | 9.96, 15.04, 16.11 | 33.217 s | 0.730 / 0.754 s |
| Qwen 2B RTX/Vulkan1 | 116.99, 139.76, 138.15 | 4.989 s | 0.125 / 0.124 s |

Both styles reuse the same three samples and generation identifier per process.
All four actual replies are accepted exact matches within 800 ms, and independent
handles observe both native exits. CPU rates differ substantially from the prior
isolated run, reinforcing the live-instance requirement; no tier promotion follows.
These fixed short probes do not establish corpus latency or clean-driver-cache
performance. Reports are retained in `eval/cleanup/results/2026-11-12-calibration/`.
