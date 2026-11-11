# Streaming preview validation, 2026-11-12

The 160 ms English Nemotron conversion passes standalone native callback cadence
on this CPU. No Labs toggle, app preview integration or new runtime download is
enabled by this spike. P3.7 remains unchecked until those pieces are verified.

## Exact artifact and license

The selected package is sherpa-onnx's
`sherpa-onnx-nemotron-speech-streaming-en-0.6b-160ms-int8-2026-04-25.tar.bz2`.
GitHub release asset ID: `405279013`; archive size: 463,945,198 bytes; SHA-256:
`0ae73a41cd51599dc7cac9ac083d9d35de53d762ca45923505fde47a3751814b`.
The unchanged archive and extracted files are retained in private QA storage.
Extracted model/card/token files total 661,919,574 bytes. Keeping both requires
about 1.13 GB, before any staging overhead.

Original weights are NVIDIA's English Nemotron Speech Streaming 0.6B, exported
to ONNX/int8 by sherpa-onnx. The
[upstream model card](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b)
and pinned January branch `c0acae9cc4163ab0d45cd403fbecbcb0635ee685` identify the
[NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/).
This is separate from the app's MIT license. The eventual explicit Labs download
must display those terms, include the agreement and required NVIDIA attribution,
and credit the ONNX/int8 conversion. No weights are redistributed in this PR.

The older Hugging Face conversion at revision
`f13b0c6a48186fdd9fdd8d203b9527b0b709b09f` reports a `chunk_shift` of 112 feature
frames in a ranged encoder metadata read, corresponding to 1.12 s. That cadence
cannot supply four native updates per second. The
[official streaming documentation](https://k2-fsa.github.io/sherpa/onnx/nemo/nemotron-streaming.html)
provides 80/160/560/1120 ms packages. The 160 ms package was explicitly downloaded
and SHA-256 verified for this developer probe; it is not silently installed by
the application.

Verification after this spike: 463 tests passed, four optional native checks
skipped with real Silero and language detection enabled; cleanup evaluation
remains 42/42 and Ruff passes. Native streaming measurements above ran separately
under NetworkGuard with no final-ASR contention.

## Native results

Windows 11, six physical/twelve logical CPU cores, CPU provider/four inference
threads, sherpa-onnx 1.13.4. NetworkGuard was active and native telemetry disabled
before loading. The eight-second repeated bundled fixture was fed in real time
in 160 ms blocks; a 0.66 s zero tail and end-of-input flushed recognition.

| Measurement | Result |
|---|---:|
| Native constructor, excluding verification/imports | 3.185 s |
| Decode/result callbacks | 49 over 8.003 s |
| Callback rate | 6.12/s |
| Minimum callbacks in steady one-second windows | 5 |
| Callback interval p95 | 0.183 s |
| Feed/decode step median / maximum | 0.110 / 0.271 s |
| Actual text changes | 6, or 0.75/s |
| Final flush | 0.590 s |

The four-update target is interpreted as preview result refresh cadence. Distinct
word changes depend on speech and are reported separately; repeated text is not
counted as newly recognized words. This probe does not establish accuracy, a
latency distribution, microphone capture behavior or cadence while the default
final recognizer runs concurrently. The
[pinned native binding](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/python/csrc/online-recognizer.cc)
releases the GIL during readiness checks and decoding.

## Reproduction and remaining integration

`tools.probe_streaming` performs no network requests. It verifies the exact
archive before extracting only five declared regular files into a new directory.
It never follows archive links or writes unlisted/traversal paths. Existing
directories/reports are refused and retained. Security tests cover all these
boundaries.

```powershell
python -m tools.probe_streaming --archive D:\qa\nemotron-160ms.tar.bz2 --model-dir D:\qa\new-nemotron-model --output build/qa/new-streaming-report.json
```

Next: add a pinned resumable archive installer with safe extraction and retained
license/notice files, an opt-in Labs control, a callback/queue adapter and the Bar
preview strip. Decoder initialization belongs before capture; PortAudio must only
queue owned audio. Preview failure/overload must preserve the normal final-ASR
path. Parakeet remains the final recognizer unless the user explicitly selects
the streaming result. Measure cadence again with both recognizers active before
checking off P3.7. Bengali/Arabic still use the shared optional All languages
transcription model; this English preview is a separate Labs feature.
