# Production background-ASR release replay

Immutable source 0dbf024 completes twenty real-time captures each at 3/8/20
seconds using native Parakeet/LID and RTX 2B cleanup policy, SQLite History and
checked stub insertion. The normal minimum-duration guard remains active, all
samples flow through the production background-ASR queue, and no delivery occurs
before release. No microphone, hooks or OS keys are used; networking is blocked.

| Audio duration | Release p50 | Release p95 | Maximum | Decisions |
| --- | ---: | ---: | ---: | --- |
| 3 s | 0.506 s | 0.834 s | 0.914 s | 20 accepted model replies |
| 8 s | 1.077 s | 1.276 s | 1.290 s | 20 accepted model replies |
| 20 s | 0.427 s | 0.696 s | 0.850 s | 20 budget skips |

All three groups meet the stated with-LLM p50 ≤1.2 s / p95 ≤2.0 s targets for
these repeated warm fixtures. The owned native process exits, and the index pins
the unmodified report and retained local journal digests. The local QA History
database remains retained. The adjacent whole-clip baseline remains unchanged.

This proves the measured background path on this explicit RTX device. It does
not establish owner accuracy, diverse speakers, Standard/rules-only background
latency, live-device/real-application paste behavior or general tier acceptance.
Initialization/static preparation is excluded before release. No default is selected.
