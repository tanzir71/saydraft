# Third-party notices

Saydraft's own code is covered by [MIT](LICENSE). Dependencies and model weights
keep their own licenses. This inventory was checked on 2026-11-12; release
packaging must retain each distributed dependency's complete copyright and
license files, including transitive dependencies and native libraries.

Frozen packages collect the supplied notices from their actual module graph
into `third_party_licenses/`, with a component/version/source/hash index. Pinned
[upstream supplements](assets/licenses/packaged/README.md) cover omitted wheel
texts and native notices. Explicit package verification checks this inventory;
ordinary startup does not restrict replacing dynamically linked libraries.

## Application dependencies

| Component | License | Source |
|---|---|---|
| PySide6, Shiboken6, Qt | LGPL-3.0 (open-source distribution; some Qt components have other terms) | [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html) |
| faster-whisper | MIT | [License](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) |
| CTranslate2 | MIT | [License](https://github.com/OpenNMT/CTranslate2/blob/master/LICENSE) |
| sherpa-onnx | Apache-2.0 | [License](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE) |
| ONNX Runtime | MIT | [License](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) |
| sounddevice / PortAudio | MIT | [Licenses](https://python-sounddevice.readthedocs.io/en/latest/about.html) |
| SoundCard 0.4.6 (meeting desktop capture) | BSD-3-Clause | [Source and license](https://github.com/bastibe/SoundCard), pinned PyPI wheel; capture is explicit and the Notetaker app flow remains in development |
| NumPy | BSD-3-Clause; bundled native components retain additional notices | [License](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| soundfile / libsndfile | BSD-3-Clause / LGPL-2.1-or-later | [Source and notices](https://github.com/bastibe/python-soundfile) |
| webrtcvad-wheels | MIT; WebRTC components retain their BSD notices | [License](https://github.com/daanzu/py-webrtcvad-wheels/blob/master/LICENSE) |
| pyperclip | BSD-3-Clause | [License](https://github.com/asweigart/pyperclip/blob/master/LICENSE.txt) |
| keyboard (historical; no longer required or imported) | MIT | [Historical license](https://github.com/boppreh/keyboard/blob/master/LICENSE.txt) |
| PyInstaller (build tool) | GPL-2.0-or-later with bootloader exception | [License and exception](https://pyinstaller.org/en/stable/license.html) |
| Python runtime | PSF and included dependency terms | [License](https://docs.python.org/3.13/license.html) |
| PyAV / FFmpeg and bundled codecs | PyAV BSD; FFmpeg/native components retain their individual terms | [PyAV sources](https://github.com/PyAV-Org/PyAV), [FFmpeg license and source information](https://ffmpeg.org/legal.html), pinned notices above |
| Intel OpenMP runtime supplied with CTranslate2 | Intel Developer Tools agreement retained unchanged | [Pinned runtime distribution](https://pypi.org/project/intel-openmp/2025.3.0/), pinned notices above |
| Inno Setup installer | Inno Setup license | [Upstream license](https://github.com/jrsoftware/issrc/blob/main/license.txt); the build retains the installed compiler's text |

Qt and PySide6 are dynamically linked in the one-folder distribution. Keep the
Qt/PySide6 shared libraries replaceable, retain their notices and LGPL/GPL texts,
and provide the corresponding source or source-access information required by
their licenses. Do not restrict debugging or modification of these libraries.
Any modifications to the libraries require their corresponding modified source.

## Optional downloaded runtimes

These components are not installed by `requirements.txt`. Explicit cleanup
setup can download a pinned CPU or Vulkan llama.cpp package, retaining its full
notices beside the verified payloads. See [runtime details](docs/CLEANUP_RUNTIME.md)
and [combined setup](docs/CLEANUP_SETUP.md). Release packaging must retain those
notices whenever it distributes a runtime.

| Component | License | Source |
|---|---|---|
| llama.cpp / ggml | MIT; bundled OpenMP retains its separate notice | [Pinned license](assets/licenses/llama-cpp-MIT.txt); exact runtime payloads/notices in `saydraft/models/manifest.json` |

## Bundled fonts

Eight unchanged TTF files are bundled under **SIL Open Font License 1.1**. Their
full copyright/license texts and original publisher metadata are retained under
`assets/fonts/`, separately from Saydraft's MIT license. Font names and binary
contents are unchanged; fonts are not sold on their own.

| Families | Role | Complete notice |
|---|---|---|
| Geist, Geist Mono | Body and code; upright/italic | [Geist](assets/fonts/geist/OFL.txt), [Geist Mono](assets/fonts/geistmono/OFL.txt) |
| Instrument Serif | Display; regular/italic | [Instrument Serif](assets/fonts/instrumentserif/OFL.txt) |
| Noto Sans Bengali | Bengali script fallback | [Noto Bengali](assets/fonts/notosansbengali/OFL.txt) |
| Noto Sans Arabic | Arabic script fallback | [Noto Arabic](assets/fonts/notosansarabic/OFL.txt) |

Source: [Google Fonts at the pinned revision](https://github.com/google/fonts/tree/2e5fa2e951237b6ae65f705693d12ca76a7f78c8/ofl).
The [font manifest](assets/fonts/manifest.json) records per-file immutable URLs,
sizes, Git blob identities and SHA-256 hashes. No Windows system font is bundled.

The website self-hosts WOFF/WOFF2 versions from the five Fontsource **5.3.0**
packages pinned with integrity hashes in `site/package-lock.json`. Their complete
original OFL notices are also served unchanged from `site/public/licenses/`.
Publisher attribution and links appear on the website's Credits page. These
webfont packages are separate from the pinned original desktop TTF files above.

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
| Qwen2.5-1.5B-Instruct (legacy user-supplied cleanup path; not a current recommended download) | Apache-2.0 | [Qwen model card and license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) |
| Nemotron Speech Streaming English 0.6B, 160 ms ONNX/int8 preview candidate | NVIDIA Open Model License; optional Labs preview | Original model by [NVIDIA](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b); ONNX/int8 conversion by sherpa-onnx, release asset `405279013`. The [complete agreement](assets/licenses/nvidia-open-model-license-2025-10-24.pdf) and [required attribution](assets/licenses/nemotron-NOTICE.txt) are retained for installation alongside the optional weights. No weights are bundled. |
| Qwen3.5 0.8B / 2B optional cleanup; 4B developer candidate | Apache-2.0 | Original weights by [Qwen](https://huggingface.co/Qwen/Qwen3.5-0.8B), GGUF Q4_K_M quantizations by [Bartowski](https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF). Explicit setup retains the original cards and [license](assets/licenses/qwen35-Apache-2.0.txt) beside the verified weights. App pins and conditional Standard/Pro defaults are in `saydraft/models/manifest.json`; all five measurement recipes remain in `eval/cleanup/candidates.json`. No weights are bundled with the application. |
| Gemma 4 E2B / E4B it cleanup candidates | Apache-2.0; developer evaluation only, unselected | Original weights by [Google](https://huggingface.co/google/gemma-4-E2B-it), converted to GGUF Q4_0 by [ggml-org](https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF). Retained unchanged with cards and [complete license text](assets/licenses/Apache-2.0.txt); no projector/MTP weights. Exact revisions/hashes are in the separate developer catalog. |
| Future diarization models | Not yet selected or shipped | Verify exact artifact terms and retain its card before adding to the manifest; do not infer a license from its family name. |
| superwhisper/s1-mini | Custom terms; excluded from defaults and redistribution | User-supplied paths only; not a bundled or recommended download. |

Settings and setup display the selected artifact's license, attribution and size
before an explicit download. The model card is retained with each Parakeet
installation. Website credits must retain this distinction from the application's
MIT license.

## Windows UI Automation binding

[comtypes 1.4.16](https://pypi.org/project/comtypes/1.4.16/) is used under MIT,
copyright Thomas Heller and Comtypes Developers. The complete bundled notice is
[comtypes-1.4.16-MIT.txt](assets/licenses/comtypes-1.4.16-MIT.txt).
The Windows UI Automation type library is supplied by Windows; generated binding
metadata stays in RAM and includes no field content.

## Bundled frequency data

Common-word membership sets are adapted from **wordfreq 3.1.1**, copyright 2022
**Robyn Speer**, under **CC-BY-SA-4.0**. They are separate from Saydraft's MIT
code. Sources include freely available SUBTLEX data by **Marc Brysbaert et al.**,
Google Books Ngrams, Leeds, Wikipedia, ParaCrawl and OpenSubtitles. All source
credits, citations and changes are retained in the [dataset notice](assets/dictionary/frequency/wordfreq-NOTICE.md),
[provenance manifest](assets/dictionary/frequency/manifest.json) and
[implementation notes](docs/DICTIONARY_LEARNING.md). Complete
[CC-BY-SA-4.0](assets/dictionary/frequency/CC-BY-SA-4.0.txt),
[wordfreq copyright/license](assets/dictionary/frequency/wordfreq-LICENSE.txt) and
[Apache-2.0](assets/licenses/Apache-2.0.txt) texts are bundled. No wordfreq Python
code is imported at runtime.

## Test recordings

The Bengali and Arabic FLEURS smoke recordings and reference transcripts are by
the [Google FLEURS contributors](https://huggingface.co/datasets/google/fleurs),
licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
Audio is retained unchanged and renamed locally. Attribution, original filenames,
sources and checksums are in [the fixture notes](tests/fixtures/FLEURS.md) and JSON
sidecars. These assets are separate from the application's MIT-licensed code.
