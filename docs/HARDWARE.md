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
reported separately. Full fixture benchmarking and Settings integration follow
this probe foundation; LLM generation depends on the P4 sidecar/model work.

The first setup cannot benchmark weights that have not been downloaded. Its
capability probe can guide a provisional recommendation; actual model timings
follow the explicit verified download. An unavailable model must leave the
benchmark pending rather than initiate a hidden transfer.

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
