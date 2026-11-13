# Native cleanup baseline — 2026-11-13

Immutable source `0ebd41f3c59e692997af11fb2bfc09639efd62c4`; 556 golden and
100 runtime adversarial inputs per completed run, four CPU threads, context 4096,
temperature zero, pinned llama.cpp b12110 CPU/Vulkan runtimes and verified
candidate weights/cards/licenses. Vulkan1 was explicitly verified as the RTX 3060.
Runs were serial with no competing model transfer/benchmark. Each native process
exit was observed before the next run. These reports retain their original bytes;
`index.json` pins their SHA-256 values.

| Candidate | Backend | Exact golden | Accepted exact / cleanup calls | 60-token median tok/s |
|---|---|---:|---:|---:|
| qwen35-08b-q4-k-m | vulkan | 555/556 | 385/404 | 192.80 |
| qwen35-2b-q4-k-m | vulkan | 553/556 | 390/404 | 148.11 |
| qwen35-4b-q4-k-m | vulkan | 505/556 | 312/404 | 73.29 |
| gemma4-e2b-q4-0 | vulkan | 552/556 | 362/404 | 121.95 |
| gemma4-e4b-q4-0 | vulkan | 527/556 | 325/404 | 73.99 |
| qwen35-08b-q4-k-m | cpu | 555/556 | 384/404 | 25.22 |

Exact golden scores include rules bypass/fallback. Accepted exact counts require
actual model replies and exclude fallback; the denominator is all cleanup calls.
Each run generated all 100 adversarial inputs, kept finite preservation checks
passing and completed three exact 60-token throughput samples. Decode rates are
not prompt processing, ASR or release-to-text latency, and host working set is not
VRAM. This machine does not establish performance for every hardware tier.

Review found a real validation gap despite those finite checks: Qwen 0.8B on
both CPU and Vulkan accepted `Envoyez` → `Envélez` in public `language-08`.
Qwen 4B added an Arabic vowel mark in another runtime case. Gemma E4B's ten
runtime differences were added commas with the source words retained. All source
journals remain in the private QA store; only metadata reports are published here.

The planned ten-job matrix stopped after the current CPU 0.8B run exited, leaving
four CPU candidates unmeasured at this source. A post-rules word-fidelity guard
was then added for normal cleanup, with bounded agreement/contraction edits and
separate polished/translation behavior. These pre-fix reports are baseline data;
they cannot qualify the updated guard or a model default. Fresh full CPU/Vulkan
measurements, real production-policy checks and release-latency acceptance remain
open. No owner recordings, microphone, clipboard or live input were used.
