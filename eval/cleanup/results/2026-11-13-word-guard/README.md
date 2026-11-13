# Native cleanup after the word guard — 2026-11-13

All ten jobs completed at immutable source
`4a1e69a277867edcd7681ee1fa87fb8588a03b34`: five candidates, each on CPU and
explicit RTX 3060 `Vulkan1`. Each job used 556 golden and 100 runtime adversarial
inputs, four CPU threads, context 4096, temperature zero and verified llama.cpp
b12110 runtimes/weights/cards/licenses. Jobs ran serially without competing
benchmarks or model transfers. Native exits were independently observed before
the next job. No microphone, owner recordings, clipboard or live input was used.

| Candidate | Backend | Exact golden | Accepted exact / cleanup calls | 60-token median tok/s | Peak native host GiB |
|---|---|---:|---:|---:|---:|
| Qwen3.5 0.8B Q4_K_M | RTX | 555/556 | 385/404 | 159.17 | 0.82 |
| Qwen3.5 2B Q4_K_M | RTX | 553/556 | 390/404 | 132.29 | 1.55 |
| Qwen3.5 4B Q4_K_M | RTX | 505/556 | 312/404 | 71.95 | 3.13 |
| Gemma 4 E2B Q4_0 | RTX | 552/556 | 362/404 | 104.88 | 1.72 |
| Gemma 4 E4B Q4_0 | RTX | 527/556 | 325/404 | 74.28 | 3.23 |
| Qwen3.5 0.8B Q4_K_M | CPU | 555/556 | 384/404 | 25.89 | 0.96 |
| Qwen3.5 2B Q4_K_M | CPU | 553/556 | 389/404 | 12.67 | 2.02 |
| Qwen3.5 4B Q4_K_M | CPU | 502/556 | 308/404 | 7.26 | 4.48 |
| Gemma 4 E2B Q4_0 | CPU | 552/556 | 360/404 | 9.51 | 2.67 |
| Gemma 4 E4B Q4_0 | CPU | 527/556 | 326/404 | 4.91 | 5.34 |

Golden totals include rules bypass/fallback. Accepted exact counts require actual
model replies and use all cleanup calls as their denominator. Every job completed
all 100 adversarial generations with token-counted replies and no finite
preservation-guard failures. Each completed three exact 60-token decode samples.
The 120-second developer quality deadline does not change the app's 800 ms cap.
Decode speed excludes prompt processing and ASR; host working set is not VRAM.
These measurements do not qualify a hardware tier or release-to-text latency.

Review of all final output differences found six distinct golden word-sequence
edits in Polished/intensity-4 backtrack cases; the remaining golden differences
were punctuation. Those edits remain strict exact failures. The adversarial
`25 dollars` → `$25` conversion is already present in deterministic rules.
The earlier French spelling substitution is now refused by the normal
post-rules word guard. Finite checks and this review are not semantic proof.

The ten JSON reports retain their original bytes. `matrix-index.json` pins all
report and private case-journal SHA-256 values. `index.json` selects only the
CPU 0.8B / RTX 2B pair expected by the evidence checker; it makes no winner
selection. Journals use public synthetic fixtures and stay in the private QA
store. Historical [pre-guard reports](../2026-11-13-baseline/README.md) remain
unchanged.

Separate [production-policy diagnostics](../2026-11-13-policy/README.md) contain
a complete RTX run and a failed partial CPU run. Combined qualification remains
open, as do co-loaded ASR, hardware-tier, cold/warm release latency and owner
accuracy acceptance.
