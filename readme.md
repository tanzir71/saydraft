# Saydraft

**Speak messy. Paste polished.**

[![CI](https://github.com/tanzir71/saydraft/actions/workflows/ci.yml/badge.svg)](https://github.com/tanzir71/saydraft/actions/workflows/ci.yml)
[![Site checks](https://github.com/tanzir71/saydraft/actions/workflows/site.yml/badge.svg)](https://github.com/tanzir71/saydraft/actions/workflows/site.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Saydraft is an open-source Windows tray app for local voice dictation. Hold a
shortcut, speak, and release to transcribe, clean up, and insert text into the
focused app. Speech recognition, cleanup, and History run on your computer;
dictation has no cloud fallback or subscription.

[Website](https://tanzir71.github.io/saydraft/) ·
[Getting started](https://tanzir71.github.io/saydraft/docs/getting-started/) ·
[Documentation](docs/README.md) · [Contributing](CONTRIBUTING.md)

[Install from source](#run-from-source) · [First launch](#first-launch) ·
[Models and languages](#set-up-once-then-go-offline) · [Daily use](#daily-use) ·
[Troubleshooting](#troubleshooting-and-development)

## Current status

Saydraft is in active development. Run from source using the steps below.
There is no published installer release yet; installer, signing, updates, and
clean-machine validation remain on the [roadmap](WISPR_OFFLINE_PARITY_PLAN.md).
The existing `tools/build.ps1` is a legacy helper awaiting that work, not the
supported installation path.

The Hub, dictation Bar, local models, and core editing tools are implemented.
Accuracy acceptance, performance targets, native Windows interaction checks,
and several planned features remain open. Notes is currently a placeholder;
Command, Translate, Ask, Scratchpad, and Notetaker are roadmap work. A passing
test suite does not establish full product parity or accuracy on your voice.

## What works today

- **Local dictation:** Parakeet or Whisper recognition, hold-to-talk and
  hands-free capture, a floating Bar, cancellation, and History before delivery.
- **Cleanup and style:** rules for fillers, repetitions, self-corrections,
  punctuation, and lists; per-app styles; optional local AI cleanup with
  validation and rules fallback.
- **One Hub:** Home statistics and recent dictations; searchable History with
  raw/cleaned changes, Markdown/CSV export, and retry when audio was retained.
- **Personal vocabulary:** searchable Dictionary terms, protected terms, and
  replacement pairs; Snippets with date/clipboard variables and import/export.
- **Guided first launch:** microphone selection and a level-only test, focused
  shortcut learning, chat/email dictation practice with before/after review,
  and a Style quick pick before opening Home.
- **Explicit model setup:** provisional PC recommendations, disclosed
  sizes/licenses, resumable downloads with per-file verification progress,
  tier overrides, and model storage controls.
- **Local data controls:** no telemetry, audio retention off by default,
  optional retention limits, and a separate read-only firewall-rule check.

## Run from source

Use Windows 10 or 11, 64-bit Python 3.13, Git, a microphone, and enough free disk
space for your selected models. In PowerShell:

```powershell
git clone https://github.com/tanzir71/saydraft.git
cd saydraft
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m saydraft
```

Keep the console available while diagnosing startup problems. The current
[download page](https://tanzir71.github.io/saydraft/download/) also links to
[GitHub Releases](https://github.com/tanzir71/saydraft/releases), where packaged
artifacts will appear when available.

### First launch

The setup wizard has six pages: Welcome, Microphone, Set up models, Shortcut,
Try it, and Style quick pick.

1. In **Microphone**, choose Default Windows input or select **Refresh inputs**
   to find a named device. **Test input** runs a ten-second, level-only check;
   it does not transcribe or save a recording.
2. In **Set up models**, optionally select **Check this PC**, then **Use speech
   recommendation**. This is a provisional capability recommendation, not a
   measured performance tier. It does not start a download or enable AI cleanup.
3. Review the speech model, size, and licenses, then select **Download / Resume**.
   Setup shows package progress and individual file transfer/checksum phases.
   Installed-file checks run in the background, including pinned dependencies.
   After installation, **Check model performance** measures the selected speech
   model using bundled audio. It opens no microphone, downloads nothing, and
   keeps successful measurements separately from saved setup preferences.
4. In **Shortcut**, keep the preset, enter a binding, or choose **Learn shortcut**
   and press/release your keys. Review any conflicts before continuing.
5. In **Try it**, practice in the window's own chat or email field. Preparation
   opens no microphone. Hold your shortcut or choose **Record**, then release or
   choose **Stop and preview** to review the transcript, cleaned text, and edit
   chips. Each practice recording is limited to one minute. Audio stays in memory;
   practice creates no History entries and uses no external paste or clipboard.
   You can continue without recording.
6. In **Style quick pick**, choose Casual or Formal for Messages and Email.
   The rules preview uses your last practice transcript or a labeled example.
   **Finish** saves changed choices and opens Home after practice has stopped.
   Existing intensity and AI settings stay unchanged. **Cancel** preserves saved
   preferences; completed downloads and resumable partials remain separate.

Finish currently saves settings even if model installation is incomplete; a
compatible installed speech model is required for dictation. Strict readiness
gating and fresh-profile manual acceptance remain in development. Capability
recommendations and actual model measurements are distinct; unavailable cleanup
measurements stay unmeasured. See the [first-run guide](docs/ONBOARDING.md).

### Set up once, then go offline

Review the recommended speech model, its download size, and its license, then
select **Download**. Progress and pause/resume are available. Later launches
reuse installed files. Choosing a language or model never starts a download
by itself; you need an installed compatible model before dictating.

| Speech option | Approximate download | Purpose |
|---|---:|---|
| Default: Parakeet v3 int8 + language detector | 773.4 MB | Recognition in 25 European languages |
| Parakeet v2 int8, English max | 661.3 MB | English recognition |
| All languages · Whisper large-v3-turbo | 1,621.7 MB | Multilingual recognition, including Bengali and Arabic |
| Whisper base / small / medium | Shown in setup | Alternative multilingual models |

Bengali and Arabic share the optional **All languages** model. Download it
once for both; there are no separate language packs or language-specific
download buttons. Installed models can be selected through language pins and
automatic routing; [routing details](docs/ASR_ROUTING.md) explain its limits.

Optional AI cleanup is disabled by default. Explicit setup offers pinned
Qwen3.5 0.8B or 2B Q4_K_M weights with a local llama.cpp CPU or Vulkan runtime.
Recommendations depend on the selected tier and available measurements; they
do not enable or download AI cleanup. See [model details](docs/MODELS.md),
[cleanup setup](docs/CLEANUP_SETUP.md), and [storage controls](docs/MODEL_STORAGE.md).
Model weights and dependencies retain their [own licenses](THIRD_PARTY_NOTICES.md).

## Daily use

1. Click the field where you want text.
2. Hold **Ctrl + Win**, speak, then release.
3. Saydraft transcribes and cleans locally, saves History, and attempts delivery
   into the original target. Review History if delivery is skipped or fails.

Fresh profiles use these shortcuts. Existing custom bindings are preserved;
change them in **Hub → Settings → Shortcuts**.

| Shortcut | Action |
|---|---|
| Ctrl + Win | Hold to dictate |
| F9 | Alternate hold-to-talk shortcut |
| XButton1 | Configurable mouse hold-to-talk shortcut |
| Ctrl + Win + Space | Toggle hands-free dictation |
| Shift + Alt + Z | Paste the last dictation |
| F10 | Capture to History without foreground insertion |
| Esc | Cancel the current recording |

Two short taps of a recording shortcut also lock hands-free mode; a single
short tap does not. The default recording cap is **20 minutes**, with a warning
at **19 minutes**. Saved custom limits stay unchanged. See
[shortcut behavior](docs/HOTKEYS.md) and [recording limits](docs/RECORDING_LIMITS.md).

## Privacy and local files

The dictation path is microphone → local recognition → cleanup → History →
delivery. Models are fetched only through explicit setup actions. Python
network access is restricted outside authorized downloads and loopback;
complete native-library and helper-process firewall enforcement remains
release work. See [the privacy boundary](docs/PRIVACY.md).

| Data | Default location |
|---|---|
| Configuration | `%LOCALAPPDATA%\Saydraft\config.json` |
| History | `%LOCALAPPDATA%\Saydraft\history.db` |
| Logs | `%LOCALAPPDATA%\Saydraft\logs\saydraft.log` |
| Audio, only when retention is enabled | `%LOCALAPPDATA%\Saydraft\audio` |
| New model installations | `%LOCALAPPDATA%\Saydraft\models\<id>\<version>` |

Audio retention is **off by default**. You can enable Keep forever or Keep N
days; expiry preserves History text and statistics. Retry needs retained audio.
Compatible legacy model installations remain readable in place. See
[audio retention](docs/AUDIO_RETENTION.md) and [data migration](docs/DATA_MIGRATION.md).

## Troubleshooting and development

- **No input:** check Windows microphone permissions, then open
  Settings → Microphone, refresh inputs, and run Test input. A missing saved
  microphone does not silently switch to another device.
- **Practice is unavailable:** return to Set up models to install the selected
  speech model, or to Microphone to check the input. After an app stop or Settings
  change, choose **Prepare practice** to start again. If setup cannot confirm
  that practice stopped, cancel setup and restart Saydraft as prompted.
- **Shortcut conflict:** review Settings → Shortcuts and rebind conflicting
  combinations. Another dictation app may use Ctrl + Win.
- **Text did not insert:** open History to review/copy the saved result.
  Focus changes, protected fields, and elevated targets can prevent delivery;
  see [delivery behavior](docs/DELIVERY.md).
- **Slow setup or recognition:** review the model size and installed files in
  Settings → Models, and use the performance check before selecting a tier.

For development setup and checks, read [CONTRIBUTING.md](CONTRIBUTING.md).
[Documentation](docs/README.md) links to implementation notes, evaluation
methods, Windows acceptance checks, and the website workflow.
Report reproducible problems in [GitHub Issues](https://github.com/tanzir71/saydraft/issues)
with redacted logs and your source version; keep private recordings and transcripts out
of public reports.

Saydraft's code is licensed under [MIT](LICENSE). Built by
[Tanzir Rahman](https://tanziro.com). You can
[support Saydraft](https://buymeacoffee.com/tanzir).
