# Cold and warm release latency

`python -m tools.bench matrix` measures the §11 matrix: 3/10/30/90-second clips,
twenty independent cold samples and twenty warm samples per duration, separately
for Lite, Standard and Pro recipes. The bundled public eight-second recording is
trimmed or repeated to the exact requested sample count. No accuracy acceptance
follows from this repeated fixture; owner accuracy remains deferred.

Each pair starts a fresh Python/worker/ASR process. Cold is its first utterance;
warm is its second, reusing the same services. OS file and driver caches may
already be warm. There is no explicit model, decoder or prompt priming between
utterances. Normal worker startup and context warmup run as in the app. Cleanup
readiness and live decoder calibration are captured at capture, immediately after
release and delivery, including unavailable or unfinished preparation. The release
snapshot records its observation offset and never postpones the release event.

The worker prepares ASR before capture. Service construction, arming/model-load
and capture times are reported separately; they are not added to release latency.
This is not an app-launch or cold-ASR-load acceptance test. One hundred millisecond
frames arrive after their samples have elapsed and flow through production
background ASR, retaining the
normal minimum-recording guard. The actual release timestamp is passed to
`SessionWorker.stop_recording`, which supplies the normal cleanup deadline.

The first checked memory `Ctrl+V` is the release-to-text endpoint. The real
`Inserter` uses its normal 150 ms delays and verifies the current durable History
row before this simulated paste. Completion additionally waits for clipboard
sentinel restoration and worker settlement. Reports retain both endpoints and
the ASR/cleanup/History/insertion stage timings. No History result or simulated
delivery may occur before release.

Capture, focus, keyboard and clipboard adapters are explicit fixtures. This opens
no microphone, enumerates no audio devices and reads no foreground window or
owner clipboard. It does not measure microphone shutdown, Qt frames, physical
key delivery or a target app rendering text. Public fixture transcripts exist
only in the separate QA History databases; JSON reports/journals contain metadata.

## Running the matrix

Lite uses the pinned Whisper base engine with rules cleanup. Standard/Pro use
Parakeet and language identification. All recipes use the pinned Silero bundle.
Standard uses Qwen3.5 0.8B on CPU; Pro uses Qwen3.5 2B on an explicit verified Vulkan
adapter. These are requested measurement recipes, not hardware certification.
The runner never downloads models. The verified small Silero bundle is copied
into each child's private profile so normal production VAD discovery works.
Runtime modules remain available from the parent interpreter's explicit search
paths; application state, temporary files and caches use the private profile.

Use a fresh requirements-only QA environment for comparable measurements.
Parent and child reports retain the Python interpreter hash and installed ASR,
VAD, audio and NumPy package versions. A mismatched child environment is rejected;
a changed environment at the end prevents full-matrix qualification. Source
fingerprints include the runtime requirements and provenance helper. These
records expose dependency differences between runs; they do not retroactively
establish versions for older reports that lack this evidence.

```powershell
python -m tools.bench matrix --tier lite --whisper-dir D:\QA\WhisperBase --vad-dir D:\QA\Silero --isolated --output D:\QA\Latency-Lite-New
python -m tools.bench matrix --tier standard --parakeet-dir D:\QA\Parakeet --lid-dir D:\QA\LanguageID --vad-dir D:\QA\Silero --models-dir D:\QA\Candidates --runtime-dir D:\QA\llama-cpp-b12110-cpu-x64 --isolated --output D:\QA\Latency-Standard-New
python -m tools.bench matrix --tier pro --parakeet-dir D:\QA\Parakeet --lid-dir D:\QA\LanguageID --vad-dir D:\QA\Silero --models-dir D:\QA\Candidates --runtime-dir D:\QA\llama-cpp-b12110-vulkan-x64 --device Vulkan1 --isolated --output D:\QA\Latency-Pro-New
```

Select the adapter for the actual machine. Run recipes serially from a clean,
immutable committed checkout, with no competing local tests/builds/model jobs
or transfers. Full-run output must be outside that checkout and fresh. Real-time
capture alone takes about 89 minutes per recipe, plus startup, arming and delivery.

For an implementation check, add `--debug --repeats 1 --durations 3`. Debug allows
partial/dirty runs and optional WebRTC VAD fallback, but always refuses full
qualification. Never relabel a diagnostic as a full matrix.

The parent Windows kill-on-close job owns each Python trial and its nested native
processes. A trial watchdog bounds failures; an observation timeout never starts
a duplicate. Child shutdown observes native exits independently. Reports are
updated atomically after every pair, with per-case journals flushed after each
utterance. Existing output is preserved. Create `STOP_AFTER_CURRENT` in the run
directory to stop at the next pair boundary; that retained partial run cannot
qualify. A failed pair and its partial evidence remain in its own subdirectory.

## Reading the results

`complete` means all requested pairs completed checked worker delivery and native
teardown. `full_matrix` additionally requires all eight cells, at least twenty
samples each, clean unchanged source, isolation, pinned VAD and no debug mode.
Both source identity and the immutable child reports are fingerprinted.
Each child and case must also report the requested actual ASR model. A Parakeet
case cannot qualify as the written Lite Whisper recipe.

The summary uses nearest-rank p50/p95 and retains maxima and decision counts for
every cell. Lite targets are 600 ms/1.2 s; with-LLM targets are 1.2 s/2.0 s. A
missing or undersized cell cannot pass. `latency_target_met` requires the full
matrix and these budgets, plus actual accepted model replies in both phases for
Standard/Pro. Intentional per-duration budget skips remain visible. An all-rules
fallback run cannot earn with-LLM credit.

`decoder_target_met` separately checks every release's live three-sample decoder
median against 25 tok/s for Standard or 40 tok/s for Pro. Missing calibration
fails this check. `tier_recipe_target_met` requires both the release-latency and
decoder gates. None of these fields establishes owner accuracy or complete
hardware-tier acceptance. Exit code zero means a completed measurement; inspect
the gates because a completed run can miss its targets.

The older [warm 3/8/20-second probe](CLEANUP_LATENCY.md) and
[Whisper baseline](BASELINE.md) retain their original scope and values.

The original `d76d22e` harness incorrectly used Parakeet for every recipe. Its
diagnostics retain that actual model metadata. A subsequent planned full run at
`0ba3d80` was stopped at a pair boundary after 118 cases when this mismatch was
found. Those raw reports remain a partial Parakeet/rules baseline; they establish
no Lite tier or full-matrix acceptance. The corrected Lite recipe uses Whisper
base through the production `WhisperCT2Engine`, with model verification and
preparation before capture.

The [full corrected Lite baseline](../eval/latency/results/2026-11-14-lite-whisper-base/README.md)
at immutable `874a9c4` completes all 160 cases with actual Whisper base/Silero,
clean unchanged source and matching runtime identities. Every pair hash,
journal, process exit and memory-delivery check was independently audited. Its
3-second cold p50/p95 is 1.297/1.357 seconds; warm is 1.270/1.330 seconds. Full
collection passes, while latency targets fail. All 241 raw metadata files remain
unchanged. Standard/Pro, performance targets, physical Windows and deferred owner
accuracy acceptance remain open.
