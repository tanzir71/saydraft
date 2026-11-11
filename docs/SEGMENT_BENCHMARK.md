# Background recognition latency

Measured on 2026-11-12 (Dhaka), using Windows 11, Python 3.13, the cached Whisper
base CPU/int8 model and the same 12-logical-CPU machine as the initial baseline.

`python -m tools.bench_segments --output build/qa/p2-segments/report.json`
feeds a 60-second fixture at real-time speed. It repeats the bundled speech clip
with pauses and leaves a voiced final segment unfinished at release. No microphone,
foreground insertion or model download is involved. NetworkGuard remains installed.

| Measurement | Result |
|---|---:|
| Fixture duration | 60 s |
| Segments completed before release | 14 |
| Total segments | 15 |
| Final segment duration | 2.31 s |
| Release → raw text | 0.841 s |
| Separate warm ASR of only the final segment | 0.825 s |
| P2.3 limit (1.3 × final-segment reference) | 1.073 s |
| Acceptance | Pass (1.02 × reference) |

This verifies the P2.3 latency relationship on one repeated fixture. It is not an
owner-clip accuracy evaluation, a p50/p95 study, a cold-load claim or proof of the
final parity budgets. Continuous speech without a pause stays in one segment and
can still incur full recognition at release. Segment failures trigger whole-clip
fallback; partial words and the failed recording remain available if that also fails.

The real-time callback now copies PortAudio buffers before retaining them. VAD and
ASR run on a background thread; the callback only queues owned chunks. Tests cover
buffer reuse, silence, continuous speech, ordered segments, cancellation, whole-clip
fallback, disabled background mode and a deterministic 60-second fixture.
