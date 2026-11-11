# Parakeet startup investigation, 2026-11-12

P3.2's complete fresh-process preparation target remains open. The reproducible
baseline is 3.087 s for v3 and 3.353 s for v2, including pinned-file SHA-256 checks.
Owner accuracy acceptance is separately deferred. See [MODELS.md](../MODELS.md).

This investigation used the bundled `hello.wav`, CPU/four threads, sherpa-onnx
1.13.4 and ONNX Runtime 1.27.0. Python and sherpa used matching ORT versions.
NetworkGuard was installed. All source weights were retained unchanged; generated
graphs and reports remain in ignored QA storage on D:.

| Experiment | Native constructor only | Fixture recognition | Observation |
|---|---:|---:|---|
| Saved optimized ONNX, all optimizations | 2.144 s | 0.232 s | Adds about 670 MB; excludes source/cache hashing and imports |
| Source ONNX, optimization disabled | 7.540 s | 0.248 s | First read from relocated QA storage; I/O and caching confound comparison |
| Source ONNX, basic optimization | 3.040 s | 0.313 s | Constructor alone exceeds the complete-load target |
| Source ONNX, extended optimization | 2.629 s | 0.256 s | Does not establish a complete load under 3 s |
| Saved ORT-format graphs, native `.ort` paths | 3.397 s | 0.290 s | No demonstrated startup improvement |

These are exploratory single runs, not controlled distributions or accuracy
results. Some outputs differed in spacing/punctuation around the synthetic product
name. No independent reference was used, so this does not establish a WER change.

The ORT-format prototype failed when passed as `.onnx` paths (`Protobuf parsing
failed`); matching `.ort` paths loaded. The pinned sherpa provider configuration
accepts a config-file path (`cpu:<path>`) with `GraphOptimizationLevel` values.
Saved graphs also need runtime/hardware compatibility checks and their own
integrity receipts. The extra storage and validation cost are not justified by
these results, so no cache or optimization-level change is enabled in the app.

Next work should measure complete preparation in controlled fresh processes,
separate I/O, integrity verification, imports and native initialization, and retain
the original artifact as fallback. Do not count a constructor-only result as the
complete-load acceptance.

Primary references: [ORT graph optimization](https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html),
[ORT serialized format](https://onnxruntime.ai/docs/performance/model-optimizations/ort-format-models.html),
[pinned sherpa session configuration](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/csrc/session.cc).
