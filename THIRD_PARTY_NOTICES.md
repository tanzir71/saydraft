# Third-party notices

Saydraft's own code is covered by [MIT](LICENSE). Dependencies and model weights
keep their own licenses. This inventory was checked on 2026-11-12; release
packaging must retain each distributed dependency's complete copyright and
license files, including transitive dependencies and native libraries.

## Application dependencies

| Component | License | Source |
|---|---|---|
| PySide6, Shiboken6, Qt | LGPL-3.0 (open-source distribution; some Qt components have other terms) | [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html) |
| faster-whisper | MIT | [License](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) |
| CTranslate2 | MIT | [License](https://github.com/OpenNMT/CTranslate2/blob/master/LICENSE) |
| sherpa-onnx | Apache-2.0 | [License](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE) |
| ONNX Runtime | MIT | [License](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) |
| sounddevice / PortAudio | MIT | [Licenses](https://python-sounddevice.readthedocs.io/en/latest/about.html) |
| NumPy | BSD-3-Clause; bundled native components retain additional notices | [License](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| soundfile / libsndfile | BSD-3-Clause / LGPL-2.1-or-later | [Source and notices](https://github.com/bastibe/python-soundfile) |
| webrtcvad-wheels | MIT; WebRTC components retain their BSD notices | [License](https://github.com/daanzu/py-webrtcvad-wheels/blob/master/LICENSE) |
| pyperclip | BSD-3-Clause | [License](https://github.com/asweigart/pyperclip/blob/master/LICENSE.txt) |
| keyboard (pending replacement) | MIT | [License](https://github.com/boppreh/keyboard/blob/master/LICENSE.txt) |
| PyInstaller (build tool) | GPL-2.0-or-later with bootloader exception | [License and exception](https://pyinstaller.org/en/stable/license.html) |

Qt and PySide6 are dynamically linked in the one-folder distribution. Keep the
Qt/PySide6 shared libraries replaceable, retain their notices and LGPL/GPL texts,
and provide the corresponding source or source-access information required by
their licenses. Do not restrict debugging or modification of these libraries.
Any modifications to the libraries require their corresponding modified source.

## Planned optional runtimes

These components are not installed by the current requirements. Before enabling
them, add their full notices to the installer and model-download UI.

| Component | License | Source |
|---|---|---|
| llama.cpp | MIT | [License](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) |

## Model weights (downloaded separately)

No model weights are included in source or installers. Each pinned model entry
must identify its publisher, revision, license, checksum and source URL. A
conversion or quantization must credit the original model and describe changes.

| Model family | License / status | Attribution and source |
|---|---|---|
| Whisper, including large-v3-turbo | MIT | [OpenAI Whisper](https://github.com/openai/whisper/blob/main/LICENSE); [SYSTRAN conversions](https://huggingface.co/Systran); [Mobius Labs / Dropbox turbo conversion](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo), stored FP16 and loaded with int8 CPU compute. Saydraft retains the converted artifacts unchanged. |
| Whisper tiny language detector | MIT | Original weights by [OpenAI](https://github.com/openai/whisper/blob/main/LICENSE), exported to ONNX and quantized to int8 by sherpa-onnx. [Converted artifacts](https://huggingface.co/csukuangfj/sherpa-onnx-whisper-tiny), revision `65176e2deb88badc814a94058666cadccc29b61c`. Saydraft retains the artifacts unchanged; both files are downloaded as a disclosed dependency of the default setup package. |
| Silero VAD v5 | MIT; downloaded with its full license | [Silero Team model and license](https://github.com/snakers4/silero-vad/tree/v5.0) |
| Parakeet TDT 0.6B v3 / v2 | CC-BY-4.0; attribution required | Original weights by NVIDIA; exported to ONNX and quantized to int8 by the sherpa-onnx project. [v3 original](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), [v2 original](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2), [v3 conversion](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8), [v2 conversion](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8), [license](https://creativecommons.org/licenses/by/4.0/). Saydraft does not further modify the downloaded weights. |
| Qwen2.5-1.5B-Instruct (manual optional cleanup) | Apache-2.0 | [Qwen model card and license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) |
| Nemotron Speech Streaming English 0.6B, 160 ms ONNX/int8 preview candidate | NVIDIA Open Model License; Labs integration pending | Original model by [NVIDIA](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b); ONNX/int8 conversion by sherpa-onnx, release asset `405279013`. The [complete agreement](assets/licenses/nvidia-open-model-license-2025-10-24.pdf) and [required attribution](assets/licenses/nemotron-NOTICE.txt) are retained for installation alongside the optional weights. No weights are bundled. |
| Future Qwen, Gemma and diarization models | Not yet selected or shipped | Verify the exact artifact's terms and retain its model card before adding to the manifest. Do not infer a license from a family name. |
| superwhisper/s1-mini | Custom terms; excluded from defaults and redistribution | User-supplied paths only; not a bundled or recommended download. |

Settings and setup display the selected artifact's license, attribution and size
before an explicit download. The model card is retained with each Parakeet
installation. Website credits must retain this distinction from the application's
MIT license.

## Test recordings

The Bengali and Arabic FLEURS smoke recordings and reference transcripts are by
the [Google FLEURS contributors](https://huggingface.co/datasets/google/fleurs),
licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
Audio is retained unchanged and renamed locally. Attribution, original filenames,
sources and checksums are in [the fixture notes](tests/fixtures/FLEURS.md) and JSON
sidecars. These assets are separate from the application's MIT-licensed code.
