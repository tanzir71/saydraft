# Hardware probing and measured tiers

`saydraft.models.hardware` separates device facts, benchmark measurements and
recommendations. Importing it performs no probe, inference, network request or
file write. Probing uses native Windows APIs and no shell subprocesses:

- Logical CPU count plus physical cores from processor topology; AVX2/AVX-512F
  from `IsProcessorFeaturePresent`.
- Physical RAM from `GlobalMemoryStatusEx`.
- DXGI adapter descriptions, dedicated VRAM and shared-memory limits. Software
  adapters are excluded. Adapter entries are not a physical GPU count.
- Vulkan 1.0 instance/device enumeration, excluding CPU implementations.
- CUDA driver initialization/device enumeration. No model or device context is
  created. A vendor name or installed DLL alone does not establish acceleration.

Missing drivers or unsupported APIs remain unknown, with a per-probe error code;
other probes continue. DXGI interfaces and the Vulkan instance are released on
both success and failure. The app does not install or update any driver.

## Tier decisions

The pure `assess_tier` function accepts measured time for an eight-second ASR
fixture and optional 0.8B/2B generation rates. It rejects invalid measurements.

| Evidence | Recommendation |
|---|---|
| RAM below 8 GiB, or ASR over 1.2 s | Lite |
| RAM/ASR measurements missing | Pending |
| ASR within budget and a GPU enumerated through Vulkan/CUDA | Pro, as specified in §7.2 |
| ASR within budget and 2B generation at least 40 tokens/s | Pro |
| ASR within budget and 0.8B generation at least 25 tokens/s | Standard |
| ASR within budget but required cleanup measurements missing | Pending |
| Measured 0.8B generation below 25 tokens/s | Lite |

Low RAM or slow ASR takes priority over GPU availability. A recommendation does
not enable AI cleanup, download a model, change the selected recognizer or prove
an unmeasured cleanup speed. GPU availability and measured token rates are
reported separately. LLM generation measurements depend on the P4 sidecar/model
work; missing rates are explicitly shown as unmeasured.

The first setup cannot benchmark weights that have not been downloaded. Its
capability probe can guide a provisional recommendation; actual model timings
follow the explicit verified download. An unavailable model must leave the
benchmark pending rather than initiate a hidden transfer.

Setup now provides **Check model performance** for its staged speech selection.
It uses this same fixture/matrix on the serial worker, forces offline loading and
measures enabled installed cleanup without changing AI settings or a manual tier.
Stop requests wait for observed native retirement; failed/cancelled setup checks
keep the previous successful report. Successful setup reports carry
`source: onboarding` and live beside an explicitly selected configuration under
`hardware-benchmarks`. See the [setup measurement flow](ONBOARDING.md#selected-model-performance).

Snapshots are appended atomically under
`%LOCALAPPDATA%\Saydraft\hardware-benchmarks`. Previous JSON files and interrupted
writes are retained. A corrupt latest JSON is skipped in favor of a valid older
snapshot. Reports contain device/benchmark metadata and no recordings or text.

## Native verification, 2026-11-12

An offline probe on the development machine found six physical/twelve logical
cores, AVX2 available, AVX-512F unavailable, and 64,312,434,688 bytes usable
physical RAM. DXGI reported AMD Radeon graphics and NVIDIA RTX 3060 adapters;
Vulkan enumerated both GPU families, and CUDA enumerated the RTX 3060. Every
probe succeeded. Since no eight-second model benchmark was passed into this
snapshot, its assessment correctly remained `pending`.

Deterministic tests cover threshold equality, low-memory/slow-ASR precedence,
GPU evidence, both LLM rates, unknown measurements, partial probe failure and
append-only persistence. A Windows-native test checks serialization offline.

```powershell
python -m tools.probe_hardware --output-dir build/qa/new-hardware-snapshots
```

Primary API sources: [processor features](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-isprocessorfeaturepresent),
[physical memory](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex),
[DXGI enumeration](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgifactory1-enumadapters1),
[DXGI fields](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1),
[Vulkan instance lifecycle](https://docs.vulkan.org/refpages/latest/refpages/source/vkCreateInstance.html),
[Vulkan properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceProperties.html).

## Speech benchmark and Settings

Settings → Performance offers an explicit check using the currently applied
speech model. It runs on the existing serial session worker, reuses loaded
recognition weights, and waits until dictation or History retry has finished.
Dictation remains unavailable during the check. No microphone, insertion or
dictation-history operation occurs. Model selection, AI cleanup and downloads
remain explicit user choices.

The bundled eight-second PCM16 asset repeats the existing smoke recording;
source and output hashes are in `assets/audio/README.md`. The existing assets
packaging rule includes it. This is a throughput fixture, not an independently
labeled accuracy corpus. The benchmark records preparation separately, warms
recognition once, then takes the median of three complete recognitions, including
Auto language detection when enabled. It stores metadata and timings, never the
recognized words. Missing or failed models keep the result pending and provide
Settings guidance. Previous snapshots survive failures.

The cleanup callback now uses the currently enabled installed model through the
owned P4 sidecar. Disabled cleanup returns no samples and does not construct a
runtime. No check enables cleanup, changes model selection or downloads weights.
It waits for startup preparation to settle, then runs three fresh 60-token raw
generations after the ASR check has loaded speech weights. A single 60-second
request lease bounds all three generations; fixed garden text is discarded.

Model size comes from the live `/v1/models` metadata, never a path or filename.
Missing/malformed metadata and instance replacement refuse a measurement. Only
numeric size, token-count and timing fields enter the persisted cleanup rows.
The median of three rates informs the tier matrix. Nominal 0.8B/2B classes allow
±10% actual parameter counts; other sizes show measured throughput but establish
neither matrix rate. This class is a performance comparison, not model-quality
approval. Partial triples, invalid values and duplicate classes are rejected
atomically, with no partial rate retained.

Explicit checks refresh generation calibration even when startup cached a result;
normal dictation keeps the cached per-instance behavior. Raw generation invalidates
the chat prefix before running, including failure paths. Background readiness is
invalidated too, and fixed neutral preparation is requested afterward. Interactive
cleanup keeps rules until its captured context is prepared again. The page shows
the cleanup median/sample count and provides guidance when measurement fails.

A native offline Auto/Parakeet check with the language detector loaded recorded
0.945, 0.870 and 0.996 s for the eight-second fixture: median 0.945 s. Other tests
ran concurrently, so this is not a controlled performance distribution. The
GPU-plus-ASR rule recommends Pro on this machine; cleanup speed remains
unmeasured. It does not establish general release-to-text parity. Both the page
and complete Settings dialog were rendered offscreen for layout review; the QA
renderer explicitly registered the local Segoe UI font.

Validation passes 459 tests with four optional native skips, cleanup eval 42/42
and Ruff. Tests cover exact fixture samples, warmup/excluded preparation, persisted
metrics without transcripts, missing models, incomplete cleanup output, serial
capture exclusion, failed/unqueued work, explicit UI actions and Qt result wiring.

```powershell
python -m tools.bench_hardware --parakeet-dir C:\path\to\verified\parakeet-v3 --lid-dir C:\path\to\verified\language-detector --output-dir build/qa/new-hardware-benchmarks
```

`tools.probe_hardware_cleanup` exercises the same installed-model callback with
native ASR/LID and independently observes inventory/inference exits. It requires
explicit verified candidate/runtime paths, writes a new artifact directory,
restores prefix readiness and never captures, inserts or writes History. Initial
development verification selects RTX automatically, measures 1.068 s speech and
135.9 tokens/s median for the actual 1.943B model, and observes both exits.
Immutable-source verification follows separately; neither this repeated fixture
nor its recommendation establishes owner accuracy or general tier latency.

Integrated validation: 1483 tests pass with four optional native skips; rules
432/432, authored adversarial checks 100/100, Ruff and diff checks pass. The
Performance page was rendered and reviewed with the native report. Tests cover
fresh versus cached calibration, live metadata validation, instance replacement,
background exclusion, prefix invalidation/recovery, numeric-only snapshots,
three-sample/two-model medians, atomic failures and the default serial callback.

Clean immutable `078644c` verification passes for both backends. RTX is selected
automatically; the GPU run measures 1.000 s speech and 125.1 tokens/s cleanup
(actual 1.943B parameters), recommending Pro. The co-loaded CPU run measures
1.536 s speech and 21.2 tokens/s cleanup (actual 0.773B), correctly recommending
Lite: speech exceeds 1.2 s and cleanup is below the 25 tokens/s Standard target.
Startup preparation may compete with ASR, as in the app; cleanup samples are
fresh after ASR loading. Neither check is general release latency acceptance.
Both restore the static prefix and independently observe all native exits.
Original report bytes and digests are retained under
`eval/hardware/results/2026-11-12-cleanup-performance/`.

Settings → Models now supports a saved Auto/Lite/Standard/Pro override. Auto uses
these measured reports; a manual choice never rewrites their recommendation or
proves speed acceptance. The Home chip and feature gates use the selected tier.
Use tier defaults stages speech/cleanup choices before Save and starts no
downloads. See `docs/MODEL_STORAGE.md` for the choice matrix and storage controls.
