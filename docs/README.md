# Saydraft documentation

Start with the [project README](../readme.md),
[setup guide](https://tanzir71.github.io/saydraft/docs/getting-started/), or
[contributor guide](../CONTRIBUTING.md).

The active roadmap is [WISPR_OFFLINE_PARITY_PLAN.md](../WISPR_OFFLINE_PARITY_PLAN.md).
Its Loop State distinguishes implementation, acceptance, remaining decisions,
and dated evidence. Installer/signing, onboarding permission/manual acceptance,
Notetaker, several power features, and native/manual acceptance remain open.
Use the plan for the complete status; an implemented component is not full
milestone acceptance.

The latest cleanup change adds a content-word identity/order check to normal
post-rules AI cleanup (intensities 1–3). See the [validator](VALIDATOR_V2.md) for
allowed grammar edits, Polished/translation scope, and conservative fallback.
The [retained native baseline](../eval/cleanup/results/2026-11-13-baseline/README.md)
documents the regression that prompted it. Fresh forced-model and production-policy
qualification remains open; older reports describe their original source.

For a first source launch, follow the [six-page walkthrough](ONBOARDING.md#current-setup-walkthrough).
If setup cannot advance or finish, review [model readiness](ONBOARDING.md#readiness-and-saving).
If practice cannot prepare a model or input, use the
[setup recovery guide](ONBOARDING.md#practice-recovery).
Contributors can run the [focused setup checks](../CONTRIBUTING.md#first-run-setup-checks),
including the optional public-audio recognizer smoke.

## Using the app

| Guide | Contents |
|---|---|
| [Hub](HUB.md) | Home, global History search/export/retry, Dictionary, Snippets, Style, and Settings |
| [Shortcuts](HOTKEYS.md) | Native chords, hands-free double-tap, paste-last, and outstanding Windows checks |
| [Dictation Bar](BAR.md) | Recording/processing states and controls |
| [Microphone](MICROPHONE.md) | Device selection, read-only Windows privacy check, level-only test, missing-input behavior |
| [First-run setup](ONBOARDING.md) | Six-page walkthrough, microphone test, model setup, shortcut learning, owned practice, Style quick pick, and remaining acceptance |
| [Recording limits](RECORDING_LIMITS.md) | 19-minute warning, 20-minute default cap, saved overrides |
| [Styles](STYLES.md) | Per-app tone, intensity, and preview behavior |
| [Snippets](SNIPPETS.md) | Triggers, variables, import/export, and SQLite adoption |
| [Dictionary learning](DICTIONARY_LEARNING.md) | Vocabulary, correction learning, and Undo |
| [Delivery](DELIVERY.md) | Focus checks, protected/elevated targets, and insertion fallbacks |
| [Scratchpad and Notes](NOTES.md) | Local autosave, search/reopen, conflict recovery, and the last-diff shortcut |

## Models, privacy, and data

| Guide | Contents |
|---|---|
| [Models](MODELS.md) | Pinned speech/cleanup choices, bundle sizes, licenses, and dated measurements |
| [ASR routing](ASR_ROUTING.md) | Language pins, shared optional All languages model, retry limits |
| [Model storage](MODEL_STORAGE.md) | Tiers, staged defaults, inventory, protected models, confirmed removal |
| [Model packages](MODEL_PACKAGES.md) | Verified archive handling and installation |
| [Cleanup setup](CLEANUP_SETUP.md) | Explicit Qwen3.5 plus llama.cpp installation and recommendations |
| [Cleanup runtime](CLEANUP_RUNTIME.md) | Pinned CPU/Vulkan sidecars, requirements, and process lifecycle |
| [Cleanup gate](CLEANUP_GATE.md) | Need scoring, preparation, deadlines, and rules fallback |
| [Cleanup validator](VALIDATOR_V2.md) | Protected details, content-word checks, permitted edits, and limits |
| [Privacy boundary](PRIVACY.md) | Python network policy, explicit downloads, firewall inspection, remaining native enforcement |
| [Audio retention](AUDIO_RETENTION.md) | Default-off storage, expiry, retry leases, and recovery |
| [Data migration](DATA_MIGRATION.md) | Compatibility, backups, and preserved legacy data |
| [Database](DATABASE.md) | Local SQLite behavior and qualification limits |
| [Third-party notices](../THIRD_PARTY_NOTICES.md) | Dependency, font, data, runtime, and model licenses |

## Development and verification

- [Test checklist](TEST_CHECKLIST.md): automated gates and manual Windows acceptance.
- [Evaluation](EVALUATION.md): cleanup harness, exact outputs, and action cases.
- [Cleanup evidence](CLEANUP_EVIDENCE.md): source/corpus fingerprints and native evidence.
- [Baseline](BASELINE.md): local latency/memory measurements and their limits.
- [Hardware](HARDWARE.md): measurements and tier recommendations.
- [Core refactor](CORE_REFACTOR.md): application boundaries and injected ports.
- [Theme](THEME.md) and [fonts](FONTS.md): shared tokens, Qt rendering, and bundled typefaces.
- [Website](SITE.md): Astro, Storybook, Playwright, Lighthouse, and GitHub Pages.

Dated benchmark sections and `eval/` reports describe the source and corpus
used in those runs. They are not automatically current-source, owner-accuracy,
or release acceptance. Keep original reports intact and record new evidence
alongside them. Never commit private dictations, recordings, or user databases.

The [M0–M6 handoff](history/CODEX_HANDOFF_v1.md) is retained as historical context
and is superseded by the root parity plan. The old root website and demo are
also retained pending the P9 transition; the live site is built from `site/`.
