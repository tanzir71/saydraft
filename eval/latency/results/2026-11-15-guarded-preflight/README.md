# Guarded Standard / Pro preflights: acceptance remains open

Clean guard source `86168e1213f7b17b80c8d8c21f8ed56da71973fc` passes 73 related
checks in 11.68 s, with no skips. Fresh children verify owned-process memory
accounting, real inference-runtime telemetry disabling, default GPU refusal,
explicit System32-only Vulkan metadata permission and continued refusal of audio
SDKs, native foreground ports, unrelated DLLs/callers and driver lookup paths.
The app tree is unchanged from the verified `bd6c22a` portable.

The owner explicitly approves read-only GPU identification and the local Pro
benchmark. `--allow-gpu-metadata` is Pro-only, forwards to every trial and must
match its terminal guard receipt. Default refusal remains. The guard's historical
`device_enumeration` field denotes barred owner/audio-device ports; permitted GPU
DLL calls have separate explicit fields. No microphone, owner clipboard, native
input or foreground window is accessed.

| Diagnostic | Source | Cases | Actual model replies | Observed native exits | Result |
| --- | --- | ---: | ---: | ---: | --- |
| Standard r1 | `bd6c22a` | 0 | 0 | 0 | Guard refuses NativeMeter's psapi DLL before measurement. |
| Standard r2 | `1761f1b` | 0 | 0 | 1 | Guard refuses production telemetry adapter's exact ONNX Runtime DLL during arming. |
| Standard r3 | `9bba8f4` | 4 | 0 | 2 | Complete; 2 prompt-warming and 2 budget fallbacks. |
| Pro r1 | `9bba8f4` | 2 partial | 0 | 0 | GPU metadata refused; no complete parent pair. |
| Pro r2 | `86168e1` | 4 | 4 | 4 | Complete with explicit GPU permission; ten-second samples exceed 1.2 s. |

Successful diagnostics use one fresh process per duration (3 / 10 seconds), each
with cold/warm worker utterances. Standard's release-to-paste values are
0.559 / 0.495 s and 0.805 / 0.939 s. Its rules fallbacks earn no model-use gate.
Pro's values are 0.420 / 0.694 s and 1.439 / 1.376 s; the latter contain roughly
0.56–0.60 s final ASR and 0.51–0.52 s cleanup. Pro's live decoder target passes;
Standard's does not. These are individual diagnostic samples, not medians or
percentiles qualified by a full matrix. All debug/full-matrix/latency acceptance
flags retain their actual false values. No thresholds or references change.

Both completed parents retain clean source/runtime, checked History-before-paste,
clipboard sentinel restoration, exact samples/model identity, guard/Python-PID
matching, real loopback model use or honest fallback, and observed native exits.
All original setup failures, intermediate 61/63/64-test logs, final working/clean
73-test logs, clean fresh-child refusal receipts, requests, journals and producer
sources remain. Audio, models, History databases and private profiles are excluded.

The first archive verifier rejects a Git-LF versus checkout-CRLF source mismatch.
It is corrected to preserve separate Git-blob and native-checkout expectations,
allowing only the exact LF→CRLF transformation permitted by that commit's text/eol
attributes. Actual Windows `core.autocrlf=true` and equivalent source bytes are
observed. Raw reports/fingerprints stay unchanged. The first verifier and failure
receipt remain; this conversion applies only to source provenance.

Verify retained bytes, Git objects, pairs/journals/guards and summary arithmetic:

```powershell
python eval/latency/results/2026-11-15-guarded-preflight/scripts/verify.py.txt --repo .
```

Full unchanged 3/10/30/90-second × 20 cold/warm Standard/Pro matrices, current
model-quality gates, physical Windows/privacy acceptance and full-goal delivery
remain open. The failed Pro median result from 14 November remains historical.
