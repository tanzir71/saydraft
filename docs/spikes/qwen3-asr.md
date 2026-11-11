# Qwen3-ASR 0.6B evaluation spike, 2026-11-12

This is a development experiment. No Qwen model is registered in the app, no
download control is added, and no ship decision is made. The owner's instruction
remains: “Use the bundled fixture now; defer owner accuracy acceptance.” P3.8
therefore remains unchecked until its owner EN/AR evaluation can be accepted.

The [upstream model card](https://huggingface.co/Qwen/Qwen3-ASR-0.6B/tree/5eb144179a02acc5e5ba31e748d22b0cf3e303b0)
identifies the weights as Apache-2.0. The [sherpa conversion documentation](https://k2-fsa.github.io/sherpa/onnx/qwen3-asr/export.html)
links to the official release archive. Its supported languages include English
and Arabic; Bengali is absent from that list. This experiment does not replace
the shared optional All languages model used for Bengali and Arabic in the app.

The int8 conversion is pinned to GitHub release asset **390698077**:

- Name: `sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25.tar.bz2`
- Download: **878,702,423 bytes**
- SHA-256: `393f8a14e2f5fb96746aaab342997a40641001fbd5bf9592a080a8329178ee96`
- [Immutable asset API](https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/assets/390698077)
- Upstream model revision: `5eb144179a02acc5e5ba31e748d22b0cf3e303b0`

`tools.probe_qwen_asr` never downloads. It verifies the complete archive before
writing, then extracts only seven named regular payload files to a fresh
directory. Destination paths are constants, including the tokenizer subdirectory.
Unlisted archive paths and links are never written; declared links, duplicates,
missing payloads and wrong hashes fail. Previous files and partial extraction
directories remain intact. The receipt records every payload's size and checksum.

Inference uses the existing native API with CPU/four threads, greedy decoding,
128 new tokens and a 512-token total limit. NetworkGuard is active and native
telemetry is disabled. No microphone, History write or insertion occurs. Each
clip gets one excluded warmup followed by three timed runs. Native initialization
excludes archive hashing and extraction. Reports include initialization time,
current RSS before/after loading and a process RSS peak sampled every 100 ms.
RSS includes Python and runtime overhead; it is not VRAM or
an exact OS peak. Longer private clips may need different generation limits.

Default inputs are the bundled English `hello.wav` and the licensed FLEURS
Arabic fixture. English has no independently supplied transcript, so its WER
and CER remain null. Arabic has an independent dataset reference, but a score on
one clip is only a smoke observation. Normalization uses NFKC, case folding and
punctuation/symbol stripping, retaining combining marks. An explicit private
reference corpus can use the JSON format from `tools.bench_models`; it is never
required for the current owner-deferred work.

The [pinned sherpa changelog](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/CHANGELOG.md)
records Qwen centered-STFT and silence-with-hints fixes in 1.13.7, and a shared
PRNG race fix in 1.13.8. The app stays pinned to 1.13.4. A separate development
environment evaluates 1.13.8 without changing app dependencies or the global
Python installation. Its sherpa/core wheels are hash-verified; their requirement
receipt stays with the QA environment. The probe imports no Python ONNX Runtime,
so it uses only sherpa's bundled native ORT. A runtime promotion would require
full application regression and packaging checks beyond this spike.

Reproduce using a verified developer archive and new model/report paths:

```powershell
python -m tools.probe_qwen_asr --archive D:\qa\qwen-asr.tar.bz2 --model-dir D:\qa\new-qwen-model --output build/qa/new-qwen-spike.json
```

The seven extracted payloads total **987,015,675 bytes**. On the existing 1.13.4
runtime, native initialization took **4.320 s**, excluding extraction and hashes.
Current process RSS was 60.5 MB before loading and 1,132.4 MB after loading;
the sampled peak during inference was **1,798.7 MB**. Both fixture outputs were
stable across three timed runs, and three seconds of silence returned no words.

| Runtime | English 3 s median | Arabic 8.16 s median | Arabic one-clip WER | Arabic one-clip CER |
|---|---:|---:|---:|---:|
| 1.13.4 | 0.902 s | 3.753 s | 5/15 = 33.3% | 11/85 = 12.9% |
| 1.13.8, isolated | 0.703 s | 2.943 s | 5/15 = 33.3% | 11/85 = 12.9% |

The Arabic output contains Arabic script throughout. Diacritics are retained by
the scoring normalization; no language-specific equivalence folding is applied.
The English WER remains null. On isolated 1.13.8, initialization took **3.970 s**;
loaded RSS was **1,133.2 MB** and sampled inference peak **1,800.0 MB**. It also
produced stable fixture output and no words for silence. This is a single-machine
CPU run (six physical/twelve logical cores), not a timing distribution across
machines. Faster observed decoding does not prove that the runtime fixes caused
the difference. These clips demonstrate no accuracy advantage, and the sampled
peak is above the plan's 1.3 GB default-ASR budget. No model/runtime promotion is
justified by this spike. Owner WER and a ship decision remain deferred.

The isolated environment pins Windows CPython 3.13 `sherpa-onnx==1.13.8`
(wheel SHA-256 `195455d8d6cc49f616e9d459b7d08f10a32daf2ddcbe90d4d479a8ba9aab28bf`)
and `sherpa-onnx-core==1.13.8`
(`5579e80196d516e6dae23c8f629292ce3142ab8869925d32b94612fd86f93733`).
Both use the same pinned model archive. The original app environment remains
1.13.4. Final validation: 535 tests pass, four optional native skips with real
preview/Silero/LID enabled; cleanup evaluation 42/42; Ruff and diff checks pass.
