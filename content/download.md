# Get Saydraft for Windows — Download and Setup

Canonical: https://tanzir71.github.io/saydraft/download/

Download the free Saydraft Windows x64 portable preview. Review the unsigned ZIP, SHA-256 checksum, setup instructions and local speech model sizes.

Facts checked: 2026-11-16

Saydraft is in development. The current Windows preview is available as an unsigned portable ZIP. Models are installed separately during setup.

 

## Saydraft for Windows

0.1.0 · Windows x64 · 157.3 MB

Unsigned development preview · portable ZIP. Extract the whole folder and run Saydraft.exe. Speech models are downloaded explicitly during setup.

[Download for Windows](https://github.com/tanzir71/saydraft/releases/download/v0.1.0-preview.20261116/Saydraft-0.1.0-win-x64.zip)

### Verify SHA-256

`b24ca638e91035c35029b67577b7d62859e22904618a9fa7e982a330ec40901f`

157,308,167 bytes

 

[Release notes, checksums and all assets ↗](https://github.com/tanzir71/saydraft/releases/tag/v0.1.0-preview.20261116)

 

## Start the portable app

 

- Quit an older Saydraft instance from its system-tray menu.
 
- Download the ZIP and extract the whole folder to a location you can write to.
 
- Run Saydraft.exe on Windows 10 or 11 x64. The portable includes its Python runtime.
 
- Choose your microphone, review and install a speech model, then try the private setup practice.

 

Keep all extracted support files together. The preview has no installer; optional AI cleanup is available in the Models setup step and can be left off to use rules.

 

## Set up once. Then go offline.

 

Review the recommended model, size and license, then start its download in setup. Progress and pause/resume are available. Later launches reuse your installed files. The [setup walkthrough](https://tanzir71.github.io/saydraft/docs/getting-started/) covers microphone selection, models, shortcuts and a first practice draft.

 

Arabic, Bengali, Chinese, Hindi, Indonesian, Japanese, Korean, Malay, Thai and Urdu use the optional shared All languages model. Download it once; there are no separate language packs. Portuguese, including Brazilian Portuguese, is also covered by the default model. Review [language and model choices](https://tanzir71.github.io/saydraft/docs/languages/) before choosing a package.

 

## Speech model downloads

 

These transfer sizes come from the pinned app catalog at build time. MB means 1,000,000 bytes. Verified cache entries can reduce what you download; disk use also includes installed files, temporary transfers and optional retained audio.

 

| Model or package | Transfer | License |
| --- | --- | --- |
| [Default: Parakeet v3 + language detector](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8) | 773.4 MB | CC-BY-4.0 + MIT |
| [English max: Parakeet v2](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8) | 661.3 MB | CC-BY-4.0 |
| [Whisper base](https://huggingface.co/Systran/faster-whisper-base) | 147.9 MB | MIT |
| [Whisper small](https://huggingface.co/Systran/faster-whisper-small) | 486.2 MB | MIT |
| [Whisper medium](https://huggingface.co/Systran/faster-whisper-medium) | 1530.6 MB | MIT |
| [All languages: Whisper turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo) | 1621.7 MB | MIT |
| [Optional Silero speech detection](https://github.com/snakers4/silero-vad/tree/v5.0) | 2.3 MB | MIT |
| [Optional GTCRN quiet-speech enhancement](https://github.com/Xiaobin-Rong/gtcrn) | 0.54 MB | MIT |

 

The default package includes its language detector. Optional AI cleanup, live preview and editing features have separate model/runtime requirements. See [local models](https://tanzir71.github.io/saydraft/docs/models/) for those choices and their limits. Selecting a language never starts a transfer.

 

## Run from source

 

For development, you’ll need Windows 10 or 11, 64-bit Python 3.13, Git, a microphone and disk space for your selected models. In PowerShell:

 PowerShell

```
git clone https://github.com/tanzir71/saydraft.git
cd saydraft
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m saydraft
```

 

The repository can move ahead of the published preview. Check the release’s source commit and SHA-256 before comparing builds. There is no winget or Scoop command for this portable preview.

## A few useful answers.

### Is a signed Windows installer available here?

This build is an unsigned Windows x64 portable ZIP. Extract the whole folder and run Saydraft.exe. Windows may show an unknown-publisher or SmartScreen prompt. No signed installer or package-manager command is provided for this preview.

### Will models download automatically?

No. Setup shows the recommendation, size and license before you choose Download / Resume. You can pause; later launches reuse verified installed files.

## Sources and further reading

- [Current setup and release status ↗](https://github.com/tanzir71/saydraft/blob/main/readme.md)

- [Pinned model files, sizes and licenses ↗](https://github.com/tanzir71/saydraft/blob/main/saydraft/models/manifest.json)
