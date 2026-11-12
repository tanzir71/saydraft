# Cleanup evaluation candidates

`eval/cleanup/candidates.json` is a developer-only catalog for P4.4, separate
from the application picker. Every candidate is `unselected`. No app default,
onboarding transfer, installation requirement or quality claim changes here.

| Candidate | Conversion | Weight bytes | Revision |
| --- | --- | ---: | --- |
| Qwen3.5 0.8B | Bartowski Q4_K_M | 579,615,840 | `f36b1ea49a332ede8fe5f389bbf5b3575ef71f48` |
| Qwen3.5 2B | Bartowski Q4_K_M | 1,396,198,496 | `7d26695454df6de5fbcce2e58681e62dae06ce43` |
| Qwen3.5 4B | Bartowski Q4_K_M | 3,013,027,808 | `4168f45a16a1290d65a4ec0fa312ae917a4c15d6` |
| Gemma 4 E2B it | ggml-org Q4_0 | 2,841,481,184 | `63f6c6f23b3e9e5f9737708daec2f88c9ac2e921` |
| Gemma 4 E4B it | ggml-org Q4_0 | 4,590,807,392 | `27cd6836f8e2a6e5e6b57ea0e77fa72490706985` |

All conversions and original cards declare Apache-2.0. The catalog records
original source/revision, publisher/converter, quantization, license URL, pinned
weight/card sizes and SHA-256, and a bundled license notice. The original Qwen
license and standard Apache text are retained unchanged. No local quantization,
projector or MTP draft is included. These compare
exact artifacts; different quantizations need not have identical error or speed.
Actual Gemma downloads exceed the earlier estimates.

Sources: [Qwen conversion](https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF),
[Qwen original](https://huggingface.co/Qwen/Qwen3.5-0.8B),
[Gemma conversion](https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF),
[Google original](https://huggingface.co/google/gemma-4-E2B-it).
Exact commits/URLs for all five are in the catalog. Metadata and cards were
verified through the public Hub API on 2026-11-12.

```powershell
python -m tools.download_cleanup_candidate --list
python -m tools.download_cleanup_candidate --candidate qwen35-08b-q4-k-m --directory D:\Saydraft-Evaluation
```

The second command is an explicit developer transfer. Candidate and root are
required; there is no default path or transfer on import. Existing resumable,
pinned-host, SHA-256 download code is reused. Each version lives under
`<root>/<id>/<revision>/`, with its card and verified `LICENSE.txt`. Cache reuse
rehashes all three. Changed installed licenses fail without being overwritten;
old versions are never removed. Inference tools must call `candidate_weight`
before evaluation. Session downloads target D:, preserving owner app/model paths.

P4.4/P4.7 remain unchecked. Evaluation must record model use, refusals, timeouts
and rules fallback, then separately measure isolated CPU/Vulkan latency and
memory. A rules-only pass or tiny-model lifecycle probe cannot select a winner.
This machine has six physical cores, AVX2, about 64 GB RAM and an RTX 3060 visible
to Vulkan; it does not represent every hardware tier. Concurrent transfer
timings are not benchmark results.

Foundation validation: 1278 tests pass, four optional native skips, with real
local Silero/preview/language-ID fixtures; golden 432/432; adversarial 100/100;
Ruff/diff pass. Candidate downloads are still in progress; no candidate inference
or selection is claimed by those regression results.

## Initial 0.8B compatibility probes

With networking blocked during inference, the real 0.8B artifact completed two
curated-text requests on CPU and on explicit `Vulkan1` (RTX 3060). All native
children had signalled exit after closure, observed through independent Windows
handles. This is protocol/lifecycle compatibility, not golden-set acceptance.

The default Vulkan probe and first explicit RTX probe each hit a 30 s request
deadline and returned intact rules output. An extended 120 s developer debug
budget then completed its first RTX request in 16.241 s and its cached-prefix
successor in 0.111 s. CPU observed 4.018/0.653 s. Downloads were concurrent,
so none is an isolated tier/latency result, and the app's 800 ms timeout was not
changed. Accepted outputs added a final period relative to the strict rules
oracle; the full bake-off must measure those differences rather than count
timeouts/rules fallback as model success. Warm/cold and changed-prefix cases need
separate reporting before any default or hardware-tier decision.

Local reports/logs are retained at `build/qa/cleanup-qwen08-initial-probe/`,
`build/qa/cleanup-qwen08-discrete-probe/` and
`build/qa/cleanup-qwen08-discrete-long-probe/`. The other four transfers remain
in progress. No quality, parity-latency or winner acceptance is claimed.
