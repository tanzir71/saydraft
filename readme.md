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
There is no published installer release yet; signing and
clean-machine validation remain on the [roadmap](WISPR_OFFLINE_PARITY_PLAN.md).
The [packaging pipeline](docs/PACKAGING.md) produces a 104.0 MB unsigned installer
that passes resource, dependency-notice and install/uninstall checks. Its
[retained verification](eval/packaging/results/2026-11-14-notices/README.md)
covers 38 components and 506 notice files.
The [tag-to-draft release workflow](eval/packaging/results/2026-11-14-draft/README.md)
has also passed its real dry run; signing and publication remain separate.

[App update checks](docs/UPDATES.md) are off by default. Enable and save them in
Settings → Privacy for startup/daily notices and a release-page link. Install
updates manually from GitHub.

Packaged builds also offer an optional [Windows Firewall block](docs/VERIFY_OFFLINE.md)
in Settings → Privacy. Confirm the installation path, then approve Windows UAC.
Remove the rule before downloading models or checking for updates. The rule
covers that `Saydraft.exe`; separate helper executables need their own coverage.
Source Python is never blocked by these controls.

Core dictation and the Hub are available from source. Owner accuracy acceptance
is deferred. Implementation and remaining
qualification are tracked separately:

| Available from source | Still in progress |
|---|---|
| Local dictation, rules cleanup, optional local AI cleanup | Current-model quality and release latency qualification |
| Hub, History, Dictionary, Snippets, Style, Scratchpad and Notes | Command, Translate, Ask, Notetaker |
| Six-page setup, verified downloads, model performance check | Fresh-profile and physical Windows acceptance |
| Public website, setup guide, verified unsigned builds and opt-in update notices | Signing and release publication |

Command Mode's selection guard, local edit client, replacement checks and separate
Copy recovery windows are implemented. The experimental model now has separate
Pro admission and exclusive ownership, preserving cleanup defaults. The
experimental Labs setup and held instruction route are connected for readable
selections. Read-only results are offered for Copy. The
[held-flow verification](eval/commands/results/2026-11-14-held-recording/README.md)
includes full CI/package checks, controlled native worker scenarios and both-theme
setup/recovery renders. A separate Labs opt-in now connects
[clipboard-copy fallback](docs/COMMAND_CLIPBOARD.md) for unsupported safe fields;
Windows clipboard history/sync settings apply. It offers Copy when the original
selection cannot be verified for replacement. Full Command acceptance remains open;
see the [implementation status](docs/COMMAND_MODE.md).

See the [documentation index](docs/README.md) for individual features and the
[parity plan](WISPR_OFFLINE_PARITY_PLAN.md) for the complete acceptance status.

The latest [cleanup measurements](docs/CLEANUP_EVIDENCE.md) retain all ten
CPU/RTX model comparisons, complete policy replays, and the earlier CPU failure.
The CPU policy replay keeps rules throughout, so combined hybrid qualification
remains open. Benchmark completion alone does not establish app latency or a
model default.

The [release-latency matrix](docs/LATENCY_MATRIX.md) now covers the specified
3/10/30/90-second cold/warm runs through the actual worker, History and checked
simulated paste, using Whisper base for Lite and Parakeet for Standard/Pro.
The [full Lite baseline](eval/latency/results/2026-11-14-lite-whisper-base/README.md)
completes all 160 cases, but misses the latency targets: 3-second warm p50/p95
is 1.270/1.330 seconds. Standard/Pro and performance qualification remain open;
the earlier warm fixture results retain their original scope.

## What works today

- **Local dictation:** Parakeet or Whisper recognition, hold-to-talk and
  hands-free capture, a floating Bar, cancellation, and History before delivery.
- **Cleanup and style:** rules for fillers, repetitions, self-corrections,
  punctuation, and lists; per-app styles; optional local AI cleanup with
  validation and rules fallback. Normal AI cleanup also checks content-word
  identity and order after rules; [validation details](docs/VALIDATOR_V2.md)
  describe the allowed edits and the broader Polished setting.
- **One Hub:** Home statistics and recent dictations; searchable History with
  raw/cleaned changes, Markdown/CSV export, and retry when audio was retained.
- **Scratchpad and Notes:** a floating plain-text draft with local autosave,
  searchable notes, and revision conflict recovery. A shortcut also opens the
  last dictation's changes. See the [Notes guide](docs/NOTES.md).
- **Personal vocabulary:** searchable Dictionary terms, protected terms, and
  replacement pairs; Snippets with date/clipboard variables and import/export.
- **Guided first launch:** microphone selection and a level-only test, focused
  shortcut learning, chat/email dictation practice with before/after review,
  and a Style quick pick before opening Home.
- **Explicit model setup:** provisional PC recommendations, disclosed
  sizes/licenses, resumable downloads with per-file verification progress,
  tier overrides, and model storage controls.
- **Local data controls:** no telemetry, audio retention off by default,
  optional retention limits, a read-only firewall-rule check, and explicit
  firewall controls for packaged installations.

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
   **Check microphone privacy** reads Windows permission status without opening
   an input; it provides guidance when access is blocked or unknown.
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
   **Finish** rechecks the selected model, saves changed choices, and opens Home
   after setup work has stopped.
   Existing intensity and AI settings stay unchanged. **Cancel** preserves saved
   preferences; completed downloads and resumable partials remain separate.

In **Set up models**, **Next** requires a ready speech model. Catalog packages
must pass their file checks; an existing local Whisper model needs a successful offline load check
through **Check model performance**. **Finish** checks the current model again
before saving. Cancel, hiding setup, or going Back revokes a pending Finish.
Capability recommendations and measured speed remain distinct. Fresh-profile
manual acceptance is still open. See the [first-run guide](docs/ONBOARDING.md).

### Set up once, then go offline

At least one compatible speech model is required to dictate. Model weights
are downloaded during explicit setup rather than bundled with the source.
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
do not enable or download AI cleanup. Rules-only dictation needs no cleanup
model. See [model details](docs/MODELS.md),
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
| Win + Alt + S | Open Scratchpad |
| Ctrl + Win + D | View the last dictation's changes |
| F10 | Capture to History without foreground insertion |
| Esc | Cancel the current recording |

Two short taps of a recording shortcut also lock hands-free mode; a single
short tap does not. The default recording cap is **20 minutes**, with a warning
at **19 minutes**. Saved custom limits stay unchanged. See
[shortcut behavior](docs/HOTKEYS.md) and [recording limits](docs/RECORDING_LIMITS.md).

## Privacy and local files

The dictation path is microphone → local recognition → cleanup → History →
delivery. Models are fetched only through explicit setup actions. Python
network access is restricted to loopback, requested model downloads and saved
opt-in GitHub update checks. Packaged firewall controls add an OS rule for that
executable, including its native libraries. Effective Windows policy and separate
helper processes have their own verification limits. See
[the privacy boundary](docs/PRIVACY.md) and [Verify offline](docs/VERIFY_OFFLINE.md).

| Data | Default location |
|---|---|
| Configuration | `%LOCALAPPDATA%\Saydraft\config.json` |
| History and Notes | `%LOCALAPPDATA%\Saydraft\history.db` |
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
- **Next is unavailable in Set up models:** finish installing the selected
  package and its dependencies. For an existing local Whisper model, run
  **Check model performance**. If files change later, return to this step and
  check them again before finishing setup.
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
- **AI cleanup kept the rules result:** check that AI cleanup is enabled and
  its model/runtime are ready. Low-need text, insufficient time, or a rejected
  model reply can all keep rules output. See the [cleanup gate](docs/CLEANUP_GATE.md)
  and [validator](docs/VALIDATOR_V2.md) before treating fallback as a failure.

For development setup and checks, read [CONTRIBUTING.md](CONTRIBUTING.md).
[Documentation](docs/README.md) links to implementation notes, evaluation
methods, Windows acceptance checks, and the website workflow.
Report reproducible problems in [GitHub Issues](https://github.com/tanzir71/saydraft/issues)
with redacted logs and your source version; keep private recordings and transcripts out
of public reports.

The automated gates cover the offline test suite, **556 cleanup golden cases**,
and **100 authored adversarial validator cases**. These are distinct from native
model measurements and owner accuracy acceptance. The retained
[native baseline](eval/cleanup/results/2026-11-13-baseline/README.md) exposed a
word-substitution regression that is now guarded; it predates that fix and is
not current qualification. See [cleanup evidence](docs/CLEANUP_EVIDENCE.md) for
the source and corpus checks required of replacement reports.

Saydraft's code is licensed under [MIT](LICENSE). Built by
[Tanzir Rahman](https://tanziro.com). You can
[support Saydraft](https://buymeacoffee.com/tanzir).
