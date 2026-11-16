# Saydraft Credits — Models, Libraries and Font Licenses

Canonical: https://tanzir71.github.io/saydraft/credits/

Credits for NVIDIA Parakeet, Whisper, Qwen, local runtimes, adapted dictionary data and the complete OFL notices for Saydraft's self-hosted fonts.

Facts checked: 2026-11-14

Saydraft’s application code is [MIT licensed](https://github.com/tanzir71/saydraft/blob/main/LICENSE). Models, fonts, adapted data and libraries retain their own terms. The complete [third-party notices](https://github.com/tanzir71/saydraft/blob/main/THIRD_PARTY_NOTICES.md) record versions, source links, transformations and full notices.

 

## Speech and editing models

 

- NVIDIA Parakeet TDT 0.6B v3 and v2: original weights by NVIDIA under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The sherpa-onnx project exported ONNX and quantized the catalog versions to int8. Saydraft retains those converted files without further changes. Original cards: [v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) and [v2](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2).
 
- Whisper: original OpenAI models under MIT. SYSTRAN supplies the base/small/medium CTranslate2 conversions; Mobius Labs / Dropbox supplies the [large-v3-turbo conversion](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo). sherpa-onnx supplies the ONNX/int8 tiny language-detector conversion.
 
- Qwen3.5: original weights by Qwen, with Bartowski GGUF quantizations, under Apache-2.0. Optional cleanup and experimental editing are separate tasks.
 
- Nemotron streaming preview: NVIDIA’s optional English preview model uses the NVIDIA Open Model License. Its complete agreement and required attribution remain separate from MIT and are shown for its Labs setup.
 
- GTCRN: Rong Xiaobin’s MIT model, converted to ONNX by sherpa-onnx, is an optional experimental quiet-speech dependency.
 
- Silero VAD: the Silero Team’s MIT speech-detection model. Experimental meeting speakers use CNRS / pyannote segmentation under MIT and Alibaba / ModelScope 3D-Speaker ERes2Net-Base under Apache-2.0, with sherpa conversion attribution retained.

 

See [model choices](https://tanzir71.github.io/saydraft/docs/models/) for roles and download sizes. Being present in the catalog does not enable a model or establish its accuracy. Developer evaluation candidates are not recommendations.

 

## Local software foundations

 

The app builds on Python, Qt / PySide6, NumPy, soundfile / libsndfile, PyAV / FFmpeg, sounddevice / PortAudio, SoundCard, CTranslate2, faster-whisper, sherpa-onnx, ONNX Runtime, WebRTC VAD, comtypes and Metaphone. Optional local cleanup uses llama.cpp / ggml and its separately retained runtime notices.

 

These dependencies have individual terms, including LGPL, BSD, MIT and Apache licenses. The package’s collected component/version/source/hash inventory and complete notices accompany its actual frozen module graph. Refer to the full notices rather than treating this short credit list as a replacement.

 

## Dictionary data and recordings

 

Bundled common-word membership sets adapt wordfreq 3.1.1, copyright 2022 Robyn Speer, under [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/). Source credits include freely available SUBTLEX data by Marc Brysbaert et al., Google Books Ngrams, Leeds, Wikipedia, ParaCrawl and OpenSubtitles. The [dataset notice and changes](https://github.com/tanzir71/saydraft/blob/main/assets/dictionary/frequency/wordfreq-NOTICE.md) and [provenance manifest](https://github.com/tanzir71/saydraft/blob/main/assets/dictionary/frequency/manifest.json) retain the complete credits. These adapted data are separate from the app’s MIT code.

 

Public evaluation recordings retain their own licenses and contributor credits in the repository’s fixture and evaluation records. This site uses a silent, canned visual example rather than recording your voice.

 

## The type on this page

 

The website uses Familjen Grotesk for display text, Geist for body text, Martian Mono for labels and Doto for the instrument readout. Bengali and Arabic use Noto fallbacks. All use SIL Open Font License 1.1. The site self-hosts pinned Fontsource files. The complete original notices are retained below, including Geist Mono and Instrument Serif for the existing desktop/reference assets.

 

- [Familjen Grotesk — full original license](https://tanzir71.github.io/saydraft/licenses/familjen-grotesk-OFL.txt)
 
- [Geist — full original license](https://tanzir71.github.io/saydraft/licenses/geist-OFL.txt)
 
- [Martian Mono — full original license](https://tanzir71.github.io/saydraft/licenses/martian-mono-OFL.txt)
 
- [Doto — full original license](https://tanzir71.github.io/saydraft/licenses/doto-OFL.txt)
 
- [Geist Mono — full original license](https://tanzir71.github.io/saydraft/licenses/geist-mono-OFL.txt)
 
- [Instrument Serif — full original license](https://tanzir71.github.io/saydraft/licenses/instrument-serif-OFL.txt)
 
- [Noto Sans Bengali — full original license](https://tanzir71.github.io/saydraft/licenses/noto-sans-bengali-OFL.txt)
 
- [Noto Sans Arabic — full original license](https://tanzir71.github.io/saydraft/licenses/noto-sans-arabic-OFL.txt)

 

## The website

 

Created by [Tanzir Rahman](https://tanziro.com/). Built with Astro and React, with Storybook for component states. Its inline SVG and text illustrations are original. No competitor logos, stock photos or unverified endorsements are used. Creator and support links appear in the footer.

## A few useful answers.

### Does the app's MIT license cover every model?

No. Saydraft's own code is MIT licensed. Models, libraries, fonts and adapted data retain their separate licenses and attribution requirements, shown in setup and the full third-party notices.

### Does this website load fonts from a CDN?

No. Its pinned Fontsource webfonts and complete original OFL notices are self-hosted. Ordinary credit links request no external assets unless you follow them.

## Sources and further reading

- [Complete third-party notices and provenance ↗](https://github.com/tanzir71/saydraft/blob/main/THIRD_PARTY_NOTICES.md)

- [Pinned model catalog and original cards ↗](https://github.com/tanzir71/saydraft/blob/main/saydraft/models/manifest.json)

- [Adapted frequency data notice ↗](https://github.com/tanzir71/saydraft/blob/main/assets/dictionary/frequency/wordfreq-NOTICE.md)
