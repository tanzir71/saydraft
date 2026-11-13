# Full Lite release-latency baseline — 2026-11-14

Immutable source: `874a9c4eec1170708832c286d5e135cc214b77e5`.
The corrected written Lite recipe completes **80 fresh-process pairs / 160
utterances**, twenty cold and twenty warm samples at each duration. Actual ASR
identity is **Whisper base** throughout, with pinned Silero and rules cleanup.
All LLM decisions are disabled as specified for Lite.

The run is complete and satisfies the full-matrix collection gate. **It misses
the 0.600-second p50 / 1.200-second p95 release-to-text targets.** No decoder,
model or threshold was changed to obtain these results.

| Audio | Cold p50 / p95 | Warm p50 / p95 |
|---|---|---|
| 3 s | 1.297 / 1.357 s | 1.270 / 1.330 s |
| 10 s | 1.594 / 1.637 s | 1.599 / 1.656 s |
| 30 s | 1.263 / 1.442 s | 1.264 / 1.498 s |
| 90 s | 1.615 / 2.128 s | 1.626 / 1.843 s |

The endpoint is the first checked memory paste through the real Inserter,
including its ordinary pre-paste delay. History is durable before each paste;
no delivery happens before release, and every memory clipboard sentinel is
restored. Cold means the first utterance in a fresh worker/ASR process; ASR
prepares before capture, and OS caches may already be warm. Arming/model loading
and clipboard restoration/settlement are recorded separately. These are not
app-launch, physical key, microphone-shutdown or target-window rendering timings.

The requirements-only runtime records Python 3.13.17, faster-whisper 1.2.1,
CTranslate2 4.9.0, sherpa-onnx/core 1.13.4, ONNX Runtime 1.32.0, NumPy 2.5.4,
soundfile 0.14.0 and webrtcvad-wheels 2.0.14. Parent/child environment equality,
final environment equality, unchanged clean source and interpreter identity pass.
The isolated run used real-time public-fixture frames and opened no owner
microphone/device, foreground field or clipboard. No competing local test/build,
native-model job or model transfer ran during collection; small source/metadata
work and remote CI continued.

All **241 raw metadata files** are copied unchanged: parent report, 80 pair
reports, 80 two-case journals and 80 process receipts. Private QA History
databases, audio and request paths are excluded. `validation.json` records an
independent audit of every pair hash, journal/case equality, zero process exit,
all duration/repeat combinations, History/paste/restore checks, source fingerprint
and runtime/request equality. It retains hashes of the privately checked request
files. `index.json` hashes all delivered raw metadata and that audit.

`complete`, `full_matrix` and actual-model-use gates pass; `latency_target_met`
and `tier_recipe_target_met` are false. Lite has no LLM decoder-rate requirement.
No owner accuracy, Standard/Pro, physical Windows or overall parity acceptance
follows. Earlier Parakeet-as-Lite diagnostics and the deliberately stopped
118-case run remain unqualified historical measurements. See
[the method](../../../../docs/LATENCY_MATRIX.md).
