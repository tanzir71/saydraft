# Release-to-delivery fixture replay

`tools.probe_cleanup_latency` measures release through native Parakeet/language
identification, production cleanup, SQLite History and checked stub insertion.
It uses the bundled eight-second public fixture, replayed at 3/8/20 seconds,
with at least 20 samples in each duration group. Every sample uses the real worker,
captured context and monotonic release deadline. No microphone, global hooks or
OS keys are used. Source/candidate identifiers and metadata are recorded; only the
separate QA History database contains public fixture text.

Capture is instantaneous replay. The probe explicitly disables the minimum
recording-duration guard for its injected session and disables background ASR,
so the entire clip is recognized after release. This does not measure live
recording, microphone/device shutdown, overlapping background recognition, Qt
rendering or target-application paste behavior. History's recording duration is
replay wall time; report `audio_seconds` records the actual ASR input length.
Repeated fixture timings cannot establish owner accuracy, diverse-speaker latency
or general hardware-tier acceptance.

ASR/model initialization and static prefix preparation happen before release.
Rules mode uses Balanced cleanup. LLM mode uses Polished cleanup so the need gate
can admit real work; normal prediction, timeout, output validation and rules
fallback remain active. Accepted replies and all per-duration decisions are
reported separately. An all-rules run cannot meet the probe's with-LLM target.

The report uses nearest-rank p50/p95 and retains maxima and per-case metadata.
Rules targets are 600 ms/1.2 s; with-LLM targets are 1.2 s/2.0 s. Completion checks
all requested samples, History-before-delivery, release-deadline propagation and
native exits. `latency_target_met` additionally checks the latency targets and
requires actual accepted replies in LLM mode. A completed measurement can still
miss its target; no defaults or tier settings are changed by this developer tool.

Only verified installed models/runtimes are used, with networking blocked. Each
run requires a clean immutable checkout and a new output directory. Do not run
competing benchmarks or model transfers while collecting timing evidence.

```powershell
python -m tools.probe_cleanup_latency --mode rules --parakeet-dir D:\QA\Parakeet --lid-dir D:\QA\LanguageID --output D:\QA\New-Rules-Run
python -m tools.probe_cleanup_latency --mode llm --parakeet-dir D:\QA\Parakeet --lid-dir D:\QA\LanguageID --candidate qwen35-2b-q4-k-m --models-dir D:\QA\Candidates --runtime-dir D:\QA\llama-cpp-b12110-vulkan-x64 --backend vulkan --device Vulkan1 --output D:\QA\New-Pro-Run
```

The device identifier must be appropriate to the actual machine; this tool does
not implement automatic native adapter selection. CPU uses its verified runtime
without a device override. Full native measurements remain pending at this stage.

Harness validation: 1398 tests pass with four optional native skips; rules 432/432,
adversarial checks 100/100, and Ruff/diff checks pass. Focused tests reject undersized
sample groups, expose a slow p95 behind a fast median, preserve decision counts,
use the distinct written thresholds and refuse dirty source before artifact creation.
