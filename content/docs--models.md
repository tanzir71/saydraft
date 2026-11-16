# Saydraft Local Models — Parakeet, Whisper and Cleanup

Canonical: https://tanzir71.github.io/saydraft/docs/models/

Compare Saydraft's local speech and cleanup models, pinned download sizes, licenses, explicit setup, cached reuse and optional quiet-speech enhancement.

Facts checked: 2026-11-14

## Speech and cleanup are separate stages

 

The speech model turns audio into words. Deterministic rules can format those words; an optional text model can make further edits within its time and preservation checks. Choosing an AI cleanup model does not replace the speech model, and better prose does not prove better recognition.

 

## Pick a compatible speech model

 

Fresh profiles recommend Parakeet v3 int8, with its disclosed tiny Whisper language detector. It recognizes 25 European languages, including English, French, German, Spanish and Portuguese. English max uses Parakeet v2.

 

All languages uses the shared Whisper large-v3-turbo model for the other supported language choices. Whisper base, small and medium are alternative local options. Use [language pins and model compatibility](https://tanzir71.github.io/saydraft/docs/languages/) to choose a route for the words you actually dictate.

 

| Speech model or package | Transfer | License |
| --- | --- | --- |
| [Default: Parakeet v3 + language detector](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8) | 773.4 MB | CC-BY-4.0 + MIT |
| [English max: Parakeet v2](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8) | 661.3 MB | CC-BY-4.0 |
| [Whisper base](https://huggingface.co/Systran/faster-whisper-base) | 147.9 MB | MIT |
| [Whisper small](https://huggingface.co/Systran/faster-whisper-small) | 486.2 MB | MIT |
| [Whisper medium](https://huggingface.co/Systran/faster-whisper-medium) | 1530.6 MB | MIT |
| [All languages: Whisper turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo) | 1621.7 MB | MIT |
| [Optional Silero speech detection](https://github.com/snakers4/silero-vad/tree/v5.0) | 2.3 MB | MIT |
| [Optional GTCRN quiet-speech enhancement](https://github.com/Xiaobin-Rong/gtcrn) | 0.54 MB | MIT |

 

Sizes are calculated from the pinned catalog at build time, with dependency deduplication and bundled notices excluded from network transfer. MB means 1,000,000 bytes. Existing verified files and resumable partials can reduce the remaining transfer. Installed disk use and temporary space are separate.

 

## Install explicitly, then reuse offline

 

Setup shows the recommendation, complete package size, source and license before Download / Resume. Pause is available. Downloaded files are verified before they are ready, and later launches reuse the installed models offline. Choosing a language, enabling a feature or starting recognition does not fetch missing files.

 

Settings → Models provides installation/storage status and selected-model performance checks. Existing local Whisper paths have a compatibility route; a successful local load is distinct from catalog checksum verification.

 

## Optional AI cleanup and editing

 

Rules-only cleanup needs no text model. Optional Qwen cleanup weights and a compatible llama.cpp CPU or Vulkan runtime add separate transfers. Command, Translate and Ask share an experimental editing setup with a 4B model; downloading it does not enable any of those features or change ordinary speech settings.

 

| Optional model/runtime | Transfer | License |
| --- | --- | --- |
| [Qwen3.5 0.8B cleanup](https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF) | 579.6 MB | Apache-2.0 |
| [Qwen3.5 2B cleanup](https://huggingface.co/bartowski/Qwen_Qwen3.5-2B-GGUF) | 1396.2 MB | Apache-2.0 |
| [Qwen3.5 4B experimental editing](https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF) | 3013.0 MB | Apache-2.0 |
| [llama.cpp CPU runtime](https://github.com/ggml-org/llama.cpp/releases/tag/b12110) | 46.9 MB | MIT + LLVM OpenMP license notice |
| [llama.cpp Vulkan runtime](https://github.com/ggml-org/llama.cpp/releases/tag/b12110) | 88.9 MB | MIT + LLVM OpenMP license notice |

 

Runtime choice and model preparation affect latency and memory. A capability recommendation is provisional; an installed-model check is a measurement of that test workload, not a promise for every recording. Quality and release-latency qualification remain separate.

 

## Quiet speech and live preview

 

Settings → Microphone has an experimental, default-off Whisper mode for quiet speech: gain, AGC, a more sensitive speech-detection profile and optional local GTCRN enhancement. Its name does not select the Whisper ASR model. GTCRN setup is an explicit reviewed download; gain/AGC can be used without enhancement. The owner whispered-speech accuracy target is still unmeasured.

 

Live preview is another separate Labs model/setup choice. Its current model is English-specific. In quiet-speech mode, live partials keep their original signal while enhanced primary recognition supplies final text.

 

See [styles](https://tanzir71.github.io/saydraft/docs/styles/) for cleanup control and [credits](https://tanzir71.github.io/saydraft/credits/) for the full attribution boundaries.

## A few useful answers.

### Is a larger download always better?

No. Compatibility, accuracy and speed depend on the language, recording and hardware. The larger decoder candidates have not established a universal improvement, and measured release-latency work remains open.

### Are Lite, Standard and Pro subscriptions?

No. They are local hardware/performance profiles in the free, open-source app. Experimental editing needs Pro and its explicitly installed model/runtime.

## Sources and further reading

- [Current model choices and setup behavior ↗](https://github.com/tanzir71/saydraft/blob/main/docs/MODELS.md)

- [Pinned artifact catalog ↗](https://github.com/tanzir71/saydraft/blob/main/saydraft/models/manifest.json)

- [Hardware/performance checks ↗](https://github.com/tanzir71/saydraft/blob/main/docs/HARDWARE.md)
