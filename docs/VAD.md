# Local speech detection

The runtime pins `sherpa-onnx==1.13.4`, including its matching native core. Silero
VAD v5 is an optional 2.3 MB download initiated in Settings → Models. Its model
and full MIT license are pinned to the original Silero Team repository commit
`5cd2ba54db059f961e7545d4f211b44f005a6dfb` with individual SHA-256 checksums.
Inference never fetches a model.

When installed, Silero handles streaming speech detection and leading/trailing
silence trimming. Missing models, missing runtimes or inference failures fall
back to the existing WebRTC/energy detector. Pauses inside an utterance remain
intact. A readiness signal is emitted only after the microphone has opened.
Downloads use a worker thread with Qt progress signals, keeping Settings responsive.

Python ONNX Runtime telemetry and Hugging Face telemetry are disabled before model
use. Sherpa's separate shared ONNX Runtime library is configured through its public
version-1 C API before creating sessions. A disabled environment is retained for
the process lifetime. If this privacy configuration is unavailable, optional Silero
falls back to WebRTC. The API adapter uses the documented initial OrtApi entries;
it is covered by the real pinned-model Windows smoke test.

Sources: [sherpa Silero support](https://k2-fsa.github.io/sherpa/onnx/vad/silero-vad.html),
[Silero v5 and license](https://github.com/snakers4/silero-vad/tree/v5.0),
[ONNX Runtime public C API](https://github.com/microsoft/onnxruntime/blob/v1.23.2/include/onnxruntime/core/session/onnxruntime_c_api.h).

## Verification (2026-11-12)

On this Windows 11 / Python 3.13 machine, the pinned runtime loaded the verified
model in 0.277 s. The bundled three-second speech fixture retained 30,080 of
48,000 samples after outer-silence trimming; three seconds of silence retained
zero samples. NetworkGuard was installed throughout inference. This is a VAD
smoke result, not an ASR accuracy or cold-ASR-load benchmark.

CI downloads the pinned VAD fixture during setup, then runs the native smoke test
with networking blocked. Unit tests isolate user model installations and cover
stream frame sizes, inner pauses, invalid padding, fallback and asynchronous UI
downloads. The build recipe retains WebRTC and collects sherpa's native libraries.
