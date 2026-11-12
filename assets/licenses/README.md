# Optional model notices

Bundled dictionary frequency data has separate CC-BY-SA-4.0 terms, Robyn Speer
and SUBTLEX author credits, original wordfreq copyright/license, and a full CC
license text under `assets/dictionary/frequency/`. Its manifest records every
notice's exact bytes and hash. See `docs/DICTIONARY_LEARNING.md`; these data files
are separate from Saydraft's MIT code and optional model weights.

`nvidia-open-model-license-2025-10-24.pdf` is the unchanged October 24, 2025
agreement linked by NVIDIA's model card and license page:

https://www.nvidia.com/content/dam/en-zz/Solutions/license-agreements/enterprise-software/nvidia-open-model-license-agreements-24-10-2025.pdf

SHA-256: `4d2fb590aa9b30c47f2058bff17291df7fa2aa0c1bd775a20703da9bb267cfab`
Size: 79,005 bytes. Copyright and terms remain NVIDIA's.

`nemotron-NOTICE.txt` contains the required NVIDIA attribution and describes the
unchanged sherpa-onnx ONNX/int8 conversion. Text notices use LF line endings so
their pinned checksums survive Windows checkouts. The archive installer copies
verified bundled notices alongside the optional model before publishing it.
Including these notices does not include or automatically download the weights.

Cleanup evaluation candidates retain two additional complete texts:

- `qwen35-Apache-2.0.txt`: unchanged Qwen license, including Alibaba copyright,
  from `Qwen/Qwen3.5-0.8B` commit `2fc06364715b967f1860aea9cf38778875588b17`.
  Size 11,544; SHA-256 `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a`.
  Its upstream CRLF bytes are preserved by an explicit `-text` Git attribute.
- `Apache-2.0.txt`: standard text from `https://www.apache.org/licenses/LICENSE-2.0.txt`.
  Size 11,358; SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
  Google/ggml-org attribution remains in the retained model card and catalog.

The explicit developer transfer copies the verified text beside each candidate.
Candidate weights are neither bundled nor selected for the app here.
