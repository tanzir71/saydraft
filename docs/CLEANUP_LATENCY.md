# Release-to-delivery fixture replay

For the written §11 3/10/30/90-second cold/warm matrix, use
[`tools.bench matrix`](LATENCY_MATRIX.md). This page retains the earlier warm
3/8/20-second probe and its historical evidence.

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

Add `--streaming-capture` to feed 100 ms audio frames at their real sample cadence
through the production background-ASR queue. This mode retains the normal 0.5 s
minimum-recording guard and its History recording duration reflects real elapsed
capture. Partial recognition still cannot reach History/insertion before release.
The same worker, release deadline, cleanup, SQLite and checked stub insertion run
after release; stage metadata separates background work from the remaining tail.
It opens no microphone and makes no OS paste. With twenty samples per duration,
real-time capture alone takes about ten minutes per run. Use fresh output paths
and collect runs sequentially without competing benchmarks.

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
without a device override. The first native baseline is recorded below.

The immutable `ec3a680` baseline now completes all sixty samples in each of rules,
CPU 0.8B policy and RTX 2B policy, with History-first checked delivery and every
native exit observed. No run meets every latency target. Rules p50/p95 at 3/8/20 s
are 0.479/0.547, 0.950/1.071 and 2.001/2.817 s. RTX accepts forty replies (all
3/8-second cases); its p50/p95 are 0.822/1.304, 1.473/1.970 and 2.455/2.734 s.
CPU accepts none: 59 budget skips and one tokenizer timeout in a nearly exhausted
release budget; both its original and restarted native processes exit. Its
20-second p50/p95 are 2.969/3.725 s. No model generation receives timeout credit.

These whole-clip baselines explicitly disable background ASR. Long-input ASR
costs dominate, so comparison with production background recognition is required.
Unmodified reports/digests are in `eval/cleanup/results/2026-11-12-release-replay/`;
local fixture databases and journals remain retained. Completion is recorded
separately from target acceptance, and no tier/default claim follows.

The immutable `0dbf024` real-time background-ASR run completes sixty RTX 2B
samples and meets the stated with-LLM targets in each duration group. Release
p50/p95 at 3/8/20 s is 0.506/0.834, 1.077/1.276 and 0.427/0.696 s. Forty model
replies are accepted for 3/8-second inputs; twenty long inputs budget-skip. No
delivery occurs before release, SQLite persistence precedes every insertion stub,
and the native process exits. Unmodified report/journal digests are retained in
`eval/cleanup/results/2026-11-12-background-replay/`. These warm repeated-fixture
results do not establish owner accuracy, Standard/rules-only background targets,
real-device/OS paste or general tier/default acceptance.

Harness validation: 1400 tests pass with four optional native skips; rules 432/432,
adversarial checks 100/100, and Ruff/diff checks pass. Focused tests reject undersized
sample groups, expose a slow p95 behind a fast median, preserve decision counts,
use the distinct written thresholds and refuse dirty source before artifact creation.
Streaming-feed tests preserve every sample, retain its real cadence including a
partial final frame, and refuse an unavailable background callback.
