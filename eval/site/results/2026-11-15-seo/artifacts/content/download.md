# Get Saydraft for Windows — Download and Setup

Canonical: https://tanzir71.github.io/saydraft/download/

Run Saydraft offline dictation on Windows 10 or 11. Check development status, source instructions, local model sizes and setup requirements.

Facts checked: 2026-11-14

Saydraft is in development. A signed installer and package-manager releases are being prepared. You can run the current code from source today.

 

## Run from source

 

You’ll need Windows 10 or 11, 64-bit Python 3.13, Git, a microphone and disk space for your selected models. In PowerShell:

 PowerShell

```
git clone https://github.com/tanzir71/saydraft.git
cd saydraft
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m saydraft
```

 

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

 

## Looking for a packaged build?

 

## Saydraft for Windows

A packaged release is being prepared. Run the current code from source and review setup first.

[View the source](https://github.com/tanzir71/saydraft)

 

Check [GitHub Releases](https://github.com/tanzir71/saydraft/releases) for published artifacts. The older unsigned verification pre-release at `v0.1.0-dry-run.20261114` predates this source; its package is not current-source qualification. Current installer checksums, signing details and winget/Scoop commands will appear here when the corresponding releases are available.

## A few useful answers.

### Is a signed Windows installer available here?

Saydraft is in development. Use the current source instructions and check GitHub Releases for published artifacts. This page does not advertise an unpublished installer or package-manager command.

### Will models download automatically?

No. Setup shows the recommendation, size and license before you choose Download / Resume. You can pause; later launches reuse verified installed files.

## Sources and further reading

- [Current setup and release status ↗](https://github.com/tanzir71/saydraft/blob/main/readme.md)

- [Pinned model files, sizes and licenses ↗](https://github.com/tanzir71/saydraft/blob/main/saydraft/models/manifest.json)
