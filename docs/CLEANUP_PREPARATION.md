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
Preparation allows 60 s each for background model loading and prompt work; the
interactive timeout remains 800 ms.

One worker coalesces requests to the latest app/style prefix. Startup uses the
configured profile, and arming uses the captured app/group and selected profile.
Raw/Code skip context preparation. Readiness is tied to the live server generation;
idle unload, restart and style/app changes invalidate it. Missing/failed/pending
preparation preserves rules immediately and records `prompt_warming` or
`prompt_unprepared`. Broken protocol is not repeatedly probed in the same instance.
Shutdown closes the owned server and refuses late preparation results.

Prefix preparation does not certify latency for every transcript, language,
caret value or glossary. Need-score, remaining-budget prediction and end-to-end
Standard/Pro acceptance remain P4.6 work. Model defaults remain unselected.
The one-token probe primes the chat prefix; decoder warm-up/calibration and
clean-driver-cache checks remain necessary before tier acceptance.

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

Validation: 1333 tests pass, four optional native skips with local
Silero/preview/language-ID fixtures; rules 432/432; authored adversarial 100/100;
Ruff/diff pass. Tests cover blocked preparation, latest-context coalescing,
instance changes, partial streams, Raw/Code, captured context and shutdown races.

Immutable native probes from `086c2bb` pass with networking blocked:

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
