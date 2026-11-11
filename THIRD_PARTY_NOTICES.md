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
| sherpa-onnx | Apache-2.0 | [License](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE) |
| ONNX Runtime | MIT | [License](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) |
| llama.cpp | MIT | [License](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) |

## Model weights (downloaded separately)

No model weights are included in source or installers. Each pinned model entry
must identify its publisher, revision, license, checksum and source URL. A
conversion or quantization must credit the original model and describe changes.

| Model family | License / status | Attribution and source |
|---|---|---|
| Whisper, including large-v3-turbo | MIT | [OpenAI Whisper](https://github.com/openai/whisper/blob/main/LICENSE); [SYSTRAN conversions](https://huggingface.co/Systran) |
| Parakeet TDT 0.6B v3 / v2 (planned) | CC-BY-4.0; attribution required | NVIDIA; [v3 model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), [v2 model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2), [license](https://creativecommons.org/licenses/by/4.0/) |
| Qwen2.5-1.5B-Instruct (manual optional cleanup) | Apache-2.0 | [Qwen model card and license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) |
| Future Qwen, Gemma, Nemotron and diarization models | Not yet selected or shipped | Verify the exact artifact's terms and retain its model card before adding to the manifest. Do not infer a license from a family name. |
| superwhisper/s1-mini | Custom terms; excluded from defaults and redistribution | User-supplied paths only; not a bundled or recommended download. |

The forthcoming Settings → Models and website credits must expose the selected
artifact's actual license and attribution, rather than replacing them with the
application's MIT license.
