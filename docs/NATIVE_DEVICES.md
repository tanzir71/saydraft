# Native Vulkan device inventory

Windows adapter enumeration and llama.cpp device IDs are independent. Use the
verified pinned Vulkan runtime's `--offline --list-devices` output, then match
device descriptions to current Vulkan API names/types. Never derive `Vulkan0`
or `Vulkan1` from Windows array positions. The pinned runtime prints the native
ID, description, total MiB and free MiB; its implementation is the
[primary format reference](https://github.com/ggml-org/llama.cpp/blob/cd959bae99ff4bed22bef2604f45241c09bbb8c8/common/arg.cpp#L1046).

The inventory process is hidden and belongs to a kill-on-close Job Object from
creation. It loads no model weights, performs no inference and receives no app
credentials, proxy variables or user text. A bounded anonymous pipe captures
only its metadata output. Inference retains NUL-only standard I/O. Both modes
inherit only their explicit standard handles, never the job or unrelated handles.

Capture retains at most 64 KiB and terminates a flooding probe. Startup/adoption
failures close pipe/job handles, including failure after the reader starts.
Process waits release the ownership lock between polls so output-limit and close
threads can terminate the job. Closing a stuck probe unblocks its reader. Probe
execution has a five-second deadline and observes cancellation before returning.

The parser refuses malformed/repeated headers, duplicate IDs, unsupported Vulkan
rows, invalid memory metadata and oversized output. Selection matches names to
Windows Vulkan types and prefers discrete, then virtual/integrated devices with
enough free memory. Unknown/ambiguous mappings cannot claim acceleration. The
native memory figures, rather than Windows array order, determine available space.

The developer probe verifies the installed runtime and records independent native
exit observations, Windows/native inventories and the selected device. It writes
only a new artifact directory and changes no app setting:

```powershell
python -m tools.probe_native_devices --runtime-dir D:\QA\llama-cpp-b12110-vulkan-x64 --output D:\QA\New-Device-Report
```

Initial native verification matches the integrated AMD device to `Vulkan0` and
the RTX 3060 to `Vulkan1` on this machine, and selects the discrete RTX despite
the integrated device's larger shared-memory budget. The owned process exits.
These IDs are machine-specific. Production sidecar selection and cleanup/tier
benchmark integration follow separately; this foundation selects no model default.

Validation: 1442 tests pass with four optional native skips; rules 432/432,
authored adversarial checks 100/100, and Ruff/diff checks pass. Native tests cover
bounded output, stuck probes, handle cleanup, reader adoption failure and unchanged
inference I/O. Selection tests cover reversed Windows order, shared memory, missing
or ambiguous matches, malformed inventories, cancellation and deadlines.

The clean immutable `9748bb5` probe also passes, with an independently observed
native exit, no weights/inference/settings changes, and the expected name/type
match. Its original report bytes and digest are retained in
`eval/hardware/results/2026-11-12-native-devices/`.

## Sidecar integration

Vulkan startup now performs this selection before loading model weights and passes
one explicit native `--device` ID. Automatic selection reserves the GGUF's byte
size plus 1 GiB when comparing free-memory budgets; the runtime still performs
its own auto-fit checks. CPU startup does not discover GPUs. An explicit developer
device override must exist in the current native inventory and cannot silently
fall through to a different device.

The inventory probe shares the process-wide admission slot with inference. Its
lease retires the probe and observes its exit before a model process can start.
Busy admission backs off; missing/ambiguous/invalid device selection keeps rules
available without starting a model. Closing during selection refuses a late launch.
Idle unload/restart performs fresh discovery and does not reuse Windows ordinals.

Native quality/release probes now pass explicit overrides through configuration
and retain the selected-device metadata. Their independent observer tracks both
inventory and inference exits. An initial normal-path run with no device override
selects RTX Vulkan1, accepts both short neutral/formal replies in 171/167 ms,
performs the three expected need/expiry skips, and observes both native exits.
This verifies device selection and short cleanup, not broader tier latency or
model-default acceptance. Cleanup benchmark callback integration remains pending.

Integrated validation: 1459 tests pass with four optional native skips; rules
432/432, authored adversarial checks 100/100 and Ruff/diff checks pass. This also
includes a reproduced download-owner lifetime fix discovered during full-suite
verification; see [download lifetime](DOWNLOAD_LIFETIME.md).
